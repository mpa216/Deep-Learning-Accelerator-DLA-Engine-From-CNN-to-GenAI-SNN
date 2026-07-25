"""Generate the config-register image, inputs and golden outputs for the GAN chip.

Runs `scripts/gan_golden.py`'s bit-exact model of `rtl/gan_engine_top.v` and writes
everything `tb/gan_engine_top_tb.sv` needs to check the RTL:

  rtl/gan_pwl_tables.vh                     PWL constants compiled into the RTL
  tb/data/gan_chip/gan_cfg.memh             16 config registers x 6 layers
  tb/data/gan_chip/gan_zq.memh              int8 latent (64)
  tb/data/gan_chip/gan_real_img.memh        int8 "real" digit fed to the discriminator
  tb/data/gan_chip/gan_img_expected.memh    golden generated image (784 int8)
  tb/data/gan_chip/gan_met_expected.memh    golden metric register file
  tb/data/gan_chip/gan_expected.txt         human-readable summary
  tb/data/gan_chip/gan_loss_series.csv      --sweep: per-sample losses for the graph

Usage
-----
  python3 scripts/gen_gan_chip_assets.py --seed 4
  python3 scripts/gen_gan_chip_assets.py --seed 4 --d-hidden relu
  python3 scripts/gen_gan_chip_assets.py --sweep 16       # loss series over 16 latents
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

from gan_golden import (
    FUNC_LRELU, FUNC_RELU, FUNC_NAMES, GanChip, Metrics, Q_ONE, ROOT,
    emit_pwl_tables_vh, pwl_accuracy_report, to_hex_signed,
)

OUT_DIR = ROOT / "tb" / "data" / "gan_chip"

# ---- config register map (must match rtl/gan_defs.vh) ----------------------
CFG_MA, CFG_MB, CFG_S, CFG_MH, CFG_SH, CFG_FUNC = 0, 1, 2, 3, 4, 5
CFG_B0, CFG_B1, CFG_B2, CFG_B3 = 6, 7, 8, 9
CFG_DST_PTR, CFG_DST_SEL, CFG_NOUT = 10, 11, 12
CFG_N = 16

DST_ACT, DST_IMG, DST_SCORE_FAKE, DST_SCORE_REAL = 0, 1, 2, 3

# ---- metric register map (must match rtl/gan_defs.vh) ----------------------
MET_NAMES = [
    "STATUS", "Y_FAKE", "Y_REAL", "LOSS_G", "LOSS_D", "ACC_LOSS_G", "ACC_LOSS_D",
    "N_SAMPLES", "N_FOOLED", "N_REAL_OK", "Y_FAKE_MIN", "Y_FAKE_MAX",
    "ACC_Y_FAKE", "ACC_Y_REAL", "INK", "SAT_PRE", "SAT_OUT", "CYCLES", "LOGIT",
    "LAST_ACC",
]
MET_N = 32


def load_latent(seed: int | None, latent_txt: str | None) -> list[float]:
    if latent_txt:
        return [float(x) for x in Path(latent_txt).read_text().split()]
    for cand in (ROOT / "tb" / "data" / "g300_samples" / f"seed_{seed}" / f"g300_output{seed}_latent.txt",
                 ROOT / "tb" / "data" / "g300_samples" / f"g300_output{seed}_latent.txt"):
        if cand.exists():
            return [float(x) for x in cand.read_text().split()]
    raise FileNotFoundError(f"no latent for seed {seed}")


def synth_real_digit() -> list[int]:
    """A clean, thick '0' stroke on a 28x28 canvas, as int8 with the chip's image scale.

    NOTE: this repository ships no MNIST dataset, so this procedurally drawn digit
    stands in for a real sample when exercising the discriminator's D(real) path and
    the loss arithmetic.  Pass --real-img to score an actual MNIST PNG instead; the
    hardware is indifferent -- it scores whatever the host loads into the image buffer.
    """
    px = []
    for r in range(28):
        for c in range(28):
            dy = (r - 13.5) / 9.0
            dx = (c - 13.5) / 6.5
            rad = math.hypot(dx, dy)
            v = math.exp(-((rad - 1.0) ** 2) / 0.06)       # ring, soft edges
            px.append(max(-127, min(127, round((2.0 * v - 1.0) * 127))))
    return px


def load_real_img(path: str) -> list[int]:
    from PIL import Image                                   # optional dependency

    im = Image.open(path).convert("L").resize((28, 28))
    return [max(-127, min(127, round((p / 255.0 * 2.0 - 1.0) * 127))) for p in im.getdata()]


def emit_unit_vectors(out_dir: Path) -> tuple[int, int]:
    """Directed vectors for tb/gan_pwl_act_tb.sv (PWL) and the -ln() unit.

    Packed so $readmemh can load them:
        pwl  : {1'b0, func[2:0], x[15:0], y[15:0]}      36 bits
        nlog : {3'b0, y[12:0], nlog[23:0]}              40 bits
    """
    from gan_golden import FUNC_IDENT, FUNC_LOG2M, PWL_TABLE, nlog_q12, pwl

    pv = []
    for func in sorted(PWL_TABLE):
        thr = PWL_TABLE[func][0]
        xs = set()
        for t in thr:                       # both sides of every breakpoint
            xs.update((t - 1, t, t + 1))
        if func == FUNC_LOG2M:
            xs.update(range(4096, 8192, 37))
        else:
            xs.update(range(-32768, 32768, 313))
        xs.update((-32768, -1, 0, 1, 32767))
        for x in sorted(v for v in xs if -32768 <= v <= 32767):
            pv.append((func << 32) | ((x & 0xFFFF) << 16) | (pwl(func, x) & 0xFFFF))
    (out_dir / "gan_pwl_vectors.memh").write_text(
        "\n".join(f"{v:09x}" for v in pv) + "\n")

    nv = []
    ys = set(range(0, 4097, 7)) | {0, 1, 2, 3, 4095, 4096} | {1 << i for i in range(13)}
    for y in sorted(ys):
        nv.append((y << 24) | (nlog_q12(y) & 0xFFFFFF))
    (out_dir / "gan_nlog_vectors.memh").write_text(
        "\n".join(f"{v:010x}" for v in nv) + "\n")
    return len(pv), len(nv)


def cfg_words(cfg, biases4, dst_ptr, dst_sel, nout) -> list[int]:
    """One layer's 16-entry config register image."""
    w = [0] * CFG_N
    w[CFG_MA], w[CFG_MB], w[CFG_S] = cfg.MA, cfg.MB, cfg.S
    w[CFG_MH], w[CFG_SH], w[CFG_FUNC] = cfg.MH, cfg.SH, cfg.func
    for i in range(4):
        w[CFG_B0 + i] = biases4[i] if i < len(biases4) else 0
    w[CFG_DST_PTR], w[CFG_DST_SEL], w[CFG_NOUT] = dst_ptr, dst_sel, nout
    return w


def render_pgm(pixels: list[int], path: Path, w: int = 28, h: int = 28) -> None:
    """Write the image as an ASCII PGM (no external dependency needed to view it)."""
    lines = [f"P2\n{w} {h}\n255"]
    for r in range(h):
        lines.append(" ".join(str(max(0, min(255, pixels[r * w + c] + 128))) for c in range(w)))
    path.write_text("\n".join(lines) + "\n")


def ascii_art(pixels: list[int], w: int = 28, h: int = 28) -> str:
    ramp = " .:-=+*#%@"
    rows = []
    for r in range(h):
        rows.append("".join(ramp[min(9, max(0, (pixels[r * w + c] + 128) * 10 // 256))]
                            for c in range(w)))
    return "\n".join(rows)


def run_one(chip: GanChip, z_real: list[float], real_img: list[int], hidden_func: int):
    """Full G -> image -> D(fake) / D(real) pass; returns everything the TB needs."""
    s_z = max(abs(v) for v in z_real) / 127.0
    zq = [max(-127, min(127, round(v / s_z))) for v in z_real]

    g_cfgs = chip.calibrate_generator(zq, s_z)
    img, g_stats = chip.run_generator(zq, g_cfgs)

    # One discriminator configuration is used for BOTH inputs, so it is calibrated
    # over the union of their activation ranges -- exactly what silicon must do.
    d_cfgs = chip.calibrate_discriminator_pair(img, real_img, hidden_func=hidden_func)
    y_fake, d_stats_f = chip.run_discriminator(img, d_cfgs)
    y_real, d_stats_r = chip.run_discriminator(real_img, d_cfgs)

    met = Metrics()
    met.score(y_fake, is_real=False)
    met.score(y_real, is_real=True)
    met.latch_loss()
    met.ink = sum(p + 128 for p in img)
    met.sat_pre = g_stats["sat_pre"] + d_stats_f["sat_pre"] + d_stats_r["sat_pre"]
    met.sat_out = g_stats["sat_out"] + d_stats_f["sat_out"] + d_stats_r["sat_out"]
    met.logit = d_stats_r["logit"]        # the chip keeps the LAST score's logit
    per_layer = g_stats["per_layer"] + d_stats_f["per_layer"]
    return zq, s_z, g_cfgs, d_cfgs, img, y_fake, y_real, met, per_layer


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=4, help="latent seed (see CLAUDE.md digit map)")
    ap.add_argument("--latent-txt", default=None, help="custom 64-value latent file")
    ap.add_argument("--real-img", default=None, help="PNG/JPG to use as the real digit")
    ap.add_argument("--d-hidden", choices=("relu", "lrelu"), default="relu",
                    help="discriminator hidden activation (a config register on chip). "
                         "relu is the default: the checkpoints store no activation "
                         "metadata, and relu is the setting under which D produces "
                         "sane, unsaturated scores on this G's output (see README)")
    ap.add_argument("--sweep", type=int, default=0,
                    help="also sweep N latent seeds and write the loss series CSV")
    args = ap.parse_args()

    hidden_func = FUNC_LRELU if args.d_hidden == "lrelu" else FUNC_RELU
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    emit_pwl_tables_vh(ROOT / "rtl" / "gan_pwl_tables.vh")
    npwl, nnlog = emit_unit_vectors(OUT_DIR)
    print(f"unit vectors: {npwl} PWL, {nnlog} nlog")
    print("PWL fit quality:")
    print(pwl_accuracy_report())

    chip = GanChip()
    real_img = load_real_img(args.real_img) if args.real_img else synth_real_digit()
    z_real = load_latent(args.seed, args.latent_txt)
    if len(z_real) != 64:
        raise ValueError(f"expected 64 latent values, got {len(z_real)}")

    zq, s_z, g_cfgs, d_cfgs, img, y_fake, y_real, met, per_layer = run_one(
        chip, z_real, real_img, hidden_func)

    # ---- config register images, one 16-word block per layer ----------------
    # The host reprograms these 16 registers before each of the six layers.
    blocks = []
    layer_specs = [
        (g_cfgs[0], chip.b["G0"], DST_ACT, 4), (g_cfgs[1], chip.b["G2"], DST_ACT, 4),
        (g_cfgs[2], chip.b["G4"], DST_IMG, 4), (d_cfgs[0], chip.b["D0"], DST_ACT, 4),
        (d_cfgs[1], chip.b["D2"], DST_ACT, 4), (d_cfgs[2], chip.b["D4"], DST_SCORE_FAKE, 1),
    ]
    for cfg, _bias, dst_sel, nout in layer_specs:
        blocks.append(cfg_words(cfg, [0, 0, 0, 0], 0, dst_sel, nout))

    (OUT_DIR / "gan_cfg.memh").write_text(
        "\n".join(to_hex_signed(v, 24) for blk in blocks for v in blk) + "\n")

    # ---- data assets --------------------------------------------------------
    (OUT_DIR / "gan_zq.memh").write_text(
        "\n".join(to_hex_signed(v, 8) for v in zq) + "\n")
    (OUT_DIR / "gan_real_img.memh").write_text(
        "\n".join(to_hex_signed(v, 8) for v in real_img) + "\n")
    (OUT_DIR / "gan_img_expected.memh").write_text(
        "\n".join(to_hex_signed(v, 8) for v in img) + "\n")

    m = met.as_dict()
    met_words = [0] * MET_N
    for i, nm in enumerate(MET_NAMES):
        key = nm.lower()
        met_words[i] = {
            "status": 0, "y_fake": m["y_fake"], "y_real": m["y_real"],
            "loss_g": m["loss_g"], "loss_d": m["loss_d"],
            "acc_loss_g": m["acc_loss_g"], "acc_loss_d": m["acc_loss_d"],
            "n_samples": m["n_samples"], "n_fooled": m["n_fooled"],
            "n_real_ok": m["n_real_ok"], "y_fake_min": m["y_fake_min"],
            "y_fake_max": m["y_fake_max"], "acc_y_fake": m["acc_y_fake"],
            "acc_y_real": m["acc_y_real"], "ink": m["ink"],
            "sat_pre": m["sat_pre"], "sat_out": m["sat_out"],
            "cycles": 0, "logit": m["logit"], "last_acc": 0,
        }[key]
    (OUT_DIR / "gan_met_expected.memh").write_text(
        "\n".join(to_hex_signed(v, 24) for v in met_words) + "\n")

    render_pgm(img, OUT_DIR / "gan_img_expected.pgm")
    render_pgm(real_img, OUT_DIR / "gan_real_img.pgm")

    # ---- float reference, for an accuracy statement -------------------------
    ref_notes = []
    ref_path = ROOT / "tb" / "data" / "g300_samples" / f"g300_output{args.seed}_pixels.txt"
    if ref_path.exists():
        ref = [int(v) for v in ref_path.read_text().split()]
        if len(ref) == 784:
            d = [abs((img[i] + 128) - ref[i]) for i in range(784)]
            ref_notes.append(f"vs float (unquantised) generator : mean |dgray| = "
                             f"{sum(d)/784:5.2f}, max = {max(d):3d} (of 255)")
    old = ROOT / "tb" / "data" / "g300_int8" / "g300_int8_expected.memh"
    if old.exists():
        from gan_golden import read_memh_signed
        prev = read_memh_signed(old, 8)
        if len(prev) == 784:
            d = [abs(img[i] - prev[i]) for i in range(784)]
            ref_notes.append(f"vs main-branch int8 pipeline (Q20 tanh LUT) : mean |dgray| = "
                             f"{sum(d)/784:5.2f}, max = {max(d):3d} (of 255)")
    ref_note = "\n".join(ref_notes)

    summary = [
        "GAN chip golden reference",
        "=" * 60,
        f"latent seed          : {args.seed}   (s_z = {s_z:.6g})",
        f"D hidden activation  : {FUNC_NAMES[hidden_func]}",
        "",
        "Generator layer configs (host writes these 6 registers per layer):",
    ]
    for c in g_cfgs + d_cfgs:
        summary.append(f"  {c!r}")
    summary += [
        "",
        f"image int8 range     : [{min(img)}, {max(img)}]   ink = {m['ink']}",
        ref_note,
        "",
        f"y_fake  = {y_fake:5d}  ({y_fake / Q_ONE:.4f})   "
        f"verdict {'REAL(fooled D)' if y_fake > Q_ONE // 2 else 'FAKE'}",
        f"y_real  = {y_real:5d}  ({y_real / Q_ONE:.4f})   "
        f"verdict {'REAL' if y_real > Q_ONE // 2 else 'FAKE(D wrong)'}",
        f"loss_G  = {m['loss_g']:7d}  ({m['loss_g'] / Q_ONE:.4f} nats)",
        f"loss_D  = {m['loss_d']:7d}  ({m['loss_d'] / Q_ONE:.4f} nats)",
        f"saturation (Q4.12 pre-activation clamp / int8 output clamp), per layer:",
        *[f"    {k:3s} {n:4d} neurons : pre {sp:4d}  out {so:4d}" for k, n, sp, so in per_layer],
        "    (pre-clamps in the tanh/sigmoid layers are harmless -- both functions are",
        "     already flat beyond +-8.0; clamps in a ReLU layer would mean the host",
        "     picked too small a gain)",
        "",
        "Generated digit:",
        ascii_art(img),
    ]
    text = "\n".join(s for s in summary if s is not None)
    (OUT_DIR / "gan_expected.txt").write_text(text + "\n")
    print()
    print(text)

    # ---- optional multi-sample sweep for the loss graph ---------------------
    if args.sweep:
        rows = []
        for s in range(args.sweep):
            try:
                z = load_latent(s % 10, None)
            except FileNotFoundError:
                continue
            _zq, _sz, _gc, _dc, im, yf, yr, mm, _pl = run_one(chip, z, real_img, hidden_func)
            d = mm.as_dict()
            rows.append({
                "sample": s, "seed": s % 10,
                "y_fake": yf, "y_fake_f": yf / Q_ONE,
                "y_real": yr, "y_real_f": yr / Q_ONE,
                "loss_g": d["loss_g"], "loss_g_f": d["loss_g"] / Q_ONE,
                "loss_d": d["loss_d"], "loss_d_f": d["loss_d"] / Q_ONE,
                "ink": sum(p + 128 for p in im),
                "fooled": int(yf > Q_ONE // 2),
            })
        with (OUT_DIR / "gan_loss_series.csv").open("w", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            wr.writeheader()
            wr.writerows(rows)
        mean_g = sum(r["loss_g_f"] for r in rows) / len(rows)
        mean_d = sum(r["loss_d_f"] for r in rows) / len(rows)
        print(f"\nsweep: {len(rows)} samples -> gan_loss_series.csv   "
              f"mean loss_G = {mean_g:.4f}, mean loss_D = {mean_d:.4f}, "
              f"fooled {sum(r['fooled'] for r in rows)}/{len(rows)}")

    print(f"\nWrote assets to {OUT_DIR} and rtl/gan_pwl_tables.vh")


if __name__ == "__main__":
    main()
