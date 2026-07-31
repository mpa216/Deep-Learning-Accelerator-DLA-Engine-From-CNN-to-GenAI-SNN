"""Why INT8: measured accuracy, silicon area and link time against other operand widths.

Answers the reviewer request to "justify the motivation for selecting INT8 quantization
... instead of other numerical formats, such as INT4, INT16, or FP16, to explain the
corresponding trade-offs regarding computational efficiency, hardware cost, and inference
accuracy."  Three axes, all measured rather than argued:

  accuracy      Re-quantise the FP32 checkpoint to W bits (weights AND activations) and
                render the digit through the bit-exact chip model, scoring mean and max
                |delta gray| against the FP32 generator.  The float weights come from
                scripts/torch_ckpt.py, which reads the legacy .ckpt without PyTorch.
  hardware      Synthesise the real `dla_pe_array` at DATA_W = W with Yosys against the
                3.3 V standard-cell library and report cell area.  This is the same
                library and the same RTL the tapeout used, so the ratios are the ones
                the chip would actually have seen.
  link time     This design is bandwidth-bound: 1.01 weight bytes cross the serial link
                per MAC, and end-to-end latency is ~99% weight streaming
                (scripts/analyze_latency.py).  Operand width therefore multiplies the
                dominant term almost exactly, which is the argument that settles it.

Usage:
    python3 scripts/quant_tradeoff_study.py                 # accuracy only (stdlib)
    python3 scripts/quant_tradeoff_study.py --synth         # + Yosys area (container)
    python3 scripts/quant_tradeoff_study.py --synth --latex APIC_Paper/tab_quant.tex

FP16 is not synthesised: a correct FP16 MAC is a different datapath (exponent add,
alignment shift, normalise, round), not a parameter change to this one, and building a
half-verified one would produce a misleading number.  What IS reported is its mantissa
multiplier measured as an integer multiplier of the same width, which is a hard lower
bound on the arithmetic cost before any exponent handling.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gan_golden import (                                            # noqa: E402
    FUNC_RELU, FUNC_TANH, GanChip, Q_ONE, ROOT, make_layer_cfg,
)
from gen_gan_chip_assets import load_latent                          # noqa: E402
from torch_ckpt import load_state_dict                               # noqa: E402

WEIGHTS = ROOT / "weights" / "mnist_gan_mlp"
G_SPEC = [("0", 256, 64, "relu"), ("2", 256, 256, "relu"), ("4", 784, 256, "tanh")]

# Widths worth reporting. 8 is the design point; 4 and 16 are the reviewer's alternatives;
# the rest map out where the accuracy cliff actually is.
WIDTHS = [2, 3, 4, 5, 6, 8, 10, 12, 16]


# ---------------------------------------------------------------------------
# Float reference
# ---------------------------------------------------------------------------
def load_float_g() -> dict:
    sd = load_state_dict(WEIGHTS / "G--300.ckpt")
    return {k: v for k, v in sd.items()}


def float_generator(fw: dict, z: list[float]) -> list[float]:
    """The FP32 generator, in real units. Output is tanh in [-1, 1]."""
    x = list(z)
    for li, out_d, in_d, act in G_SPEC:
        shape, W = fw[f"{li}.weight"]
        _, b = fw[f"{li}.bias"]
        y = []
        for j in range(out_d):
            base = j * in_d
            s = b[j]
            for k in range(in_d):
                s += W[base + k] * x[k]
            y.append(s)
        x = [max(0.0, v) for v in y] if act == "relu" else [math.tanh(v) for v in y]
    return x


def quantize(vals: list[float], qmax: int) -> tuple[list[int], float]:
    m = max(abs(v) for v in vals)
    scale = (m / qmax) if m > 0 else 1.0
    return [max(-qmax - 1, min(qmax, round(v / scale))) for v in vals], scale


# ---------------------------------------------------------------------------
# Accuracy sweep
# ---------------------------------------------------------------------------
def accuracy_sweep(seed: int, widths: list[int]) -> list[dict]:
    fw = load_float_g()
    z = load_latent(seed, None)
    ref = float_generator(fw, z)
    ref_gray = [max(0, min(255, round((v + 1.0) * 127.5))) for v in ref]

    chip = GanChip()
    rows = []
    for W in widths:
        qmax = (1 << (W - 1)) - 1
        # Latent and every tensor re-quantised to W bits, symmetric per tensor.
        zq, s_z = quantize(z, qmax)
        for li, _o, _i, _a in G_SPEC:
            wq, s_w = quantize(fw[f"{li}.weight"][1], qmax)
            bq, s_b = quantize(fw[f"{li}.bias"][1], qmax)
            chip.set_weights(f"G{li}", wq, s_w, bq, s_b)

        # Calibrate exactly as the host does, but for a W-bit activation range.
        cfgs, x, s_x = [], [v * s_z for v in zq], s_z
        for li, out_d, in_d, act in G_SPEC:
            pre, post = chip._float_layer(x, f"G{li}", s_x, act)
            func = FUNC_TANH if act == "tanh" else FUNC_RELU
            s_out = (1.0 / qmax) if act == "tanh" else max(
                max(abs(v) for v in post) / qmax, 1e-12)
            cfgs.append(make_layer_cfg(f"G{li}", chip.scale[f"G300_{li}_weight"], s_x,
                                       chip.scale[f"G300_{li}_bias"], s_out, func,
                                       max(abs(v) for v in pre)))
            x, s_x = post, s_out

        # Run the chip model with a W-bit activation clamp and an accumulator wide
        # enough for it: K=256 products of two W-bit operands need 2W + log2(256) bits.
        # The taped-out chip has 24, i.e. exactly INT8 -- this is why the C buffer is
        # three byte-planes of SRAM, and why a wider operand costs C macros too.
        acc_bits = 2 * W + 8
        xq = zq
        sat_pre = sat_out = 0
        for i, (li, out_d, in_d, _a) in enumerate(G_SPEC):
            xq, acts, _p, sp, so = chip.layer(xq, f"G{li}", cfgs[i], out_d, in_d,
                                              qmax=qmax, acc_bits=acc_bits)
            sat_pre += sp
            sat_out += so
        # The terminal layer's output scale is 1/qmax, so gray = (q/qmax + 1) * 127.5
        gray = [max(0, min(255, round((v / qmax + 1.0) * 127.5))) for v in xq]

        d = [abs(gray[i] - ref_gray[i]) for i in range(784)]
        rows.append({"bits": W, "mean": sum(d) / 784.0, "max": max(d),
                     "sat_pre": sat_pre, "sat_out": sat_out, "acc_bits": acc_bits,
                     "c_planes": -(-acc_bits // 8), "bytes_per_img": None})
    return rows


# ---------------------------------------------------------------------------
# Silicon cost: synthesise the real PE array at each width
# ---------------------------------------------------------------------------
YOSYS_LIB = ("3V3lib/gf180mcu_as_sc_mcu7t3v3-main/pdk/libs.ref/"
             "gf180mcu_as_sc_mcu7t3v3/lib/gf180mcu_as_sc_mcu7t3v3__tt_025C_3v30.lib")


def synth_area(width: int, acc_w: int, top: str = "dla_pe_array") -> float | None:
    """Cell area of the N=4 PE array at DATA_W=width, from Yosys + the 3.3 V library.

    Parameters are applied through a generated wrapper rather than `hierarchy -chparam`,
    which asserts inside Yosys 0.64 when the top module already carries defaults.
    """
    wrap = (f"module pe_array_wrap (\n"
            f"  input clk, input rst_n, input clear, input en,\n"
            f"  input signed [(4*{width})-1:0] a_bus,\n"
            f"  input signed [(4*{width})-1:0] b_bus,\n"
            f"  output signed [(16*{acc_w})-1:0] c_bus);\n"
            f"  dla_pe_array #(.N(4), .DATA_W({width}), .ACC_W({acc_w})) u (\n"
            f"    .clk(clk), .rst_n(rst_n), .clear(clear), .en(en),\n"
            f"    .a_bus(a_bus), .b_bus(b_bus), .c_bus(c_bus));\n"
            f"endmodule\n")
    script = (f"read_verilog -sv rtl/dla_pe.v rtl/dla_pe_array.v /tmp/_quant_wrap.v\n"
              f"synth -top pe_array_wrap -flatten\n"
              f"dfflibmap -liberty {YOSYS_LIB}\n"
              f"abc -liberty {YOSYS_LIB}\n"
              f"opt_clean\n"
              f"stat -liberty {YOSYS_LIB}\n")
    sp = Path("/tmp/_quant_synth.ys")
    cmd = (f"cd /foss/designs && cat > /tmp/_quant_wrap.v <<'EOW'\n{wrap}EOW\n"
           f"cat > {sp} <<'EOS'\n{script}EOS\n"
           f"yosys -s {sp} 2>&1 | grep -E 'Chip area'")
    try:
        out = subprocess.run(["docker", "exec", "apic_headless", "bash", "-lc", cmd],
                             capture_output=True, text=True, timeout=900).stdout
    except Exception as exc:                                    # pragma: no cover
        print(f"  (synthesis for {width} bits failed: {exc})")
        return None
    for line in out.splitlines():
        if "Chip area" in line:
            return float(line.split(":")[-1].strip())
    return None


# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=4, help="latent seed (digit '0')")
    ap.add_argument("--synth", action="store_true",
                    help="also synthesise the PE array at each width (needs the container)")
    ap.add_argument("--widths", default=",".join(str(w) for w in WIDTHS))
    ap.add_argument("--latex", default=None)
    args = ap.parse_args()

    widths = [int(w) for w in args.widths.split(",")]

    print("=" * 74)
    print("Operand-width trade-off for the GF180MCU GAN accelerator")
    print("=" * 74)
    print("accuracy: FP32 checkpoint re-quantised to W bits (weights AND activations),")
    print(f"          rendered through the bit-exact chip model, seed {args.seed},")
    print("          scored against the FP32 generator in gray levels of 255")
    print()

    rows = accuracy_sweep(args.seed, widths)

    # Link cost: weight bytes scale with ceil(W/8) bytes per operand, and the link is
    # ~99% of end-to-end latency, so this is very nearly the end-to-end multiplier.
    base_bytes = 282624                       # tight weight bytes for one image, INT8
    for r in rows:
        r["bytes_per_img"] = base_bytes * math.ceil(r["bits"] / 8)

    areas = {}
    if args.synth:
        print("synthesising dla_pe_array (16 PEs) at each width ...")
        for W in widths:
            a = synth_area(W, 2 * W + 8)
            areas[W] = a
            if a:
                print(f"  DATA_W={W:2d}  ACC_W={2*W+8:2d}  cell area {a:10.2f} um2")
        print()

    hdr = f"{'bits':>5s} {'mean |dgray|':>13s} {'max':>5s} {'acc':>4s} {'C mac':>6s} " \
          f"{'weight B/img':>13s} {'link time':>10s}"
    if areas:
        hdr += f" {'PE array um2':>13s} {'vs INT8':>8s}"
    print(hdr)
    a8 = areas.get(8)
    for r in rows:
        # 20 edges per byte, one edge per 4 clocks at 40 ns  ->  3.2 us per byte
        t = r["bytes_per_img"] * 20 * 4 * 40e-9
        line = (f"{r['bits']:5d} {r['mean']:13.2f} {r['max']:5d} {r['acc_bits']:4d} "
                f"{r['c_planes']:6d} {r['bytes_per_img']:13,d} {t:9.3f}s")
        if areas:
            a = areas.get(r["bits"])
            line += (f" {a:13.0f} {a/a8:7.2f}x" if a and a8 else f" {'--':>13s} {'--':>8s}")
        print(line)

    print()
    print("Reading:")
    r8 = next(r for r in rows if r["bits"] == 8)
    r4 = next((r for r in rows if r["bits"] == 4), None)
    r16 = next((r for r in rows if r["bits"] == 16), None)
    print(f"  INT8 costs {r8['mean']:.2f} gray levels of 255 mean error against FP32.")
    if r4:
        print(f"  INT4 costs {r4['mean']:.2f} ({r4['mean']/max(r8['mean'],1e-9):.1f}x worse) "
              f"and still needs a whole byte per operand in a x8 SRAM, so it buys no link")
        print("  time -- the term that actually sets end-to-end latency here.")
    if r16:
        print(f"  INT16 improves the mean error by only {r8['mean'] - r16['mean']:.2f} gray "
              f"levels while DOUBLING the weight bytes, i.e. doubling the ~99%-dominant")
        print(f"  link term: {r8['bytes_per_img']*20*4*40e-9:.2f}s -> "
              f"{r16['bytes_per_img']*20*4*40e-9:.2f}s per image.")
    print("  FP16: the mantissa multiply alone is an 11x11 array (see the INT12 row as a")
    print("  lower bound) before exponent add, alignment, normalisation and rounding; the")
    print("  open PDK ships no FP macro, and the workload's dynamic range is already")
    print("  handled by the per-tensor scale plus the Q4.12 requantisation.")

    if args.latex:
        out = Path(args.latex)
        lines = [
            "% generated by scripts/quant_tradeoff_study.py -- do not edit by hand",
            r"\begin{table}[h]",
            r"\caption{Operand-width trade-off. Accuracy is the mean absolute gray-level "
            r"error of the rendered $28\times28$ digit against the FP32 generator; PE "
            r"array area is Yosys cell area for the 16-PE array in the 3.3~V library; "
            r"link time is the weight-streaming term that dominates end-to-end latency.}",
            r"\label{tab:quant}",
            r"\centering",
            r"\renewcommand{\arraystretch}{1.08}",
            r"\begin{tabular}{@{}crrrr@{}}",
            r"\toprule",
            r"Width & Mean err. & Max err. & PE area ($\mu$m$^2$) & Link time \\",
            r"\midrule",
        ]
        for r in rows:
            if r["bits"] not in (4, 8, 16):
                continue
            a = areas.get(r["bits"])
            astr = f"{a:,.0f}" if a else "---"
            t = r["bytes_per_img"] * 20 * 4 * 40e-9
            bold = r"\textbf" if r["bits"] == 8 else None
            cells = [f"INT{r['bits']}", f"{r['mean']:.2f}", f"{r['max']:d}", astr,
                     f"{t:.2f}~s"]
            if bold:
                cells = [f"{bold}{{{c}}}" for c in cells]
            lines.append(" & ".join(cells) + r" \\")
        lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
        out.write_text("\n".join(lines) + "\n")
        print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
