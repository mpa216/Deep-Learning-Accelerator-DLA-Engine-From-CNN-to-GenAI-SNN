"""Turn the GAN chip's metric registers into the loss graph and a metrics report.

The chip computes the losses itself (gan_metrics.v + gan_nlog.v); this script only
reads them out and draws them, the same way the MATLAB reference
(UAS_VLSI_Kelompok05_modified/UAS_VLSI/LSI_Contest_simple_gan_3x3_improved.m) plotted
its loss_G_log / loss_D_log at the end of training.

Two input modes:

  --csv tb/data/gan_chip/gan_loss_series.csv
      the per-sample sweep written by `gen_gan_chip_assets.py --sweep N`
      (the golden model, i.e. what the chip is expected to produce)

  --dump tb/data/gan_chip/gan_met_rtl.txt
      "<name> <value>" lines captured from real chip / RTL metric reads; see
      dump_template() for the exact format the bring-up host should emit

Outputs (PNG if matplotlib is available, always an ASCII plot + a text report):
  tb/data/gan_chip/gan_loss_curve.png
  tb/data/gan_chip/gan_metrics_report.txt
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "tb" / "data" / "gan_chip"
Q = 4096.0                      # Q4.12 / Q12.12 scale


def dump_template() -> str:
    return (
        "# One 'NAME VALUE' pair per line, values as read from the chip (decimal).\n"
        "# Read them with the serial RD_MET command; names match rtl/gan_defs.vh.\n"
        "Y_FAKE 3958\nY_REAL 3928\nLOSS_G 141\nLOSS_D 14062\n"
        "ACC_LOSS_G 141\nACC_LOSS_D 14062\nN_SAMPLES 1\nN_FOOLED 1\nN_REAL_OK 1\n"
        "ACC_Y_FAKE 3958\nACC_Y_REAL 3928\nINK 45113\nSAT_PRE 75\nSAT_OUT 0\n"
        "CYCLES 440252\nLOGIT 13682\n"
    )


def ascii_plot(series: dict[str, list[float]], width: int = 64, height: int = 16) -> str:
    """A dependency-free line plot, so the loss curve is readable over ssh too."""
    keys = list(series)
    allv = [v for k in keys for v in series[k]]
    if not allv:
        return "(no data)"
    lo, hi = min(allv), max(allv)
    if hi - lo < 1e-9:
        hi = lo + 1.0
    n = max(len(series[k]) for k in keys)
    grid = [[" "] * width for _ in range(height)]
    marks = "*o+x"
    for ki, k in enumerate(keys):
        vals = series[k]
        for i, v in enumerate(vals):
            col = 0 if n == 1 else int(i * (width - 1) / (n - 1))
            row = int((hi - v) * (height - 1) / (hi - lo))
            grid[row][col] = marks[ki % len(marks)]
    lines = [f"  {hi:7.3f} |" + "".join(grid[0])]
    for r in range(1, height - 1):
        lines.append("          |" + "".join(grid[r]))
    lines.append(f"  {lo:7.3f} |" + "".join(grid[-1]))
    lines.append("          +" + "-" * width)
    lines.append("           sample ->    " +
                 "   ".join(f"{marks[i % len(marks)]} {k}" for i, k in enumerate(keys)))
    return "\n".join(lines)


def try_png(series: dict[str, list[float]], path: Path) -> str:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return "matplotlib not available -- skipped PNG (ASCII plot above is complete)"

    fig, ax = plt.subplots(figsize=(7.5, 4.0), dpi=140)
    colors = {"loss_G": "#2563eb", "loss_D": "#dc2626",
              "y_fake": "#059669", "y_real": "#d97706"}
    for k, v in series.items():
        ax.plot(range(len(v)), v, marker="o", markersize=3, linewidth=1.4,
                label=k, color=colors.get(k))
    ax.set_xlabel("sample")
    ax.set_ylabel("nats")
    ax.set_title("GAN chip BCE losses (computed on chip, read from MET_LOSS_*)")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return f"wrote {path}"


def report_from_dump(vals: dict[str, int]) -> str:
    def g(k, d=0):
        return vals.get(k, d)

    n = max(1, g("N_SAMPLES"))
    lines = [
        "GAN chip metric report",
        "=" * 58,
        f"  D(generated)      y_fake      {g('Y_FAKE'):8d}  = {g('Y_FAKE')/Q:.4f}",
        f"  D(real)           y_real      {g('Y_REAL'):8d}  = {g('Y_REAL')/Q:.4f}",
        f"  verdict                       "
        f"{'REAL - the generator fooled D' if g('Y_FAKE') > 2048 else 'FAKE'}",
        "",
        f"  loss_G = -ln y_fake           {g('LOSS_G'):8d}  = {g('LOSS_G')/Q:.4f} nats",
        f"  loss_D = -ln y_real",
        f"           -ln(1 - y_fake)      {g('LOSS_D'):8d}  = {g('LOSS_D')/Q:.4f} nats",
        f"  mean loss_G over {n:4d} samples          "
        f"= {g('ACC_LOSS_G')/Q/n:.4f} nats",
        f"  mean loss_D over {n:4d} samples          "
        f"= {g('ACC_LOSS_D')/Q/n:.4f} nats",
        "",
        f"  fooled D            {g('N_FOOLED'):5d} / {n:<5d}  "
        f"({100.0*g('N_FOOLED')/n:.1f}%)",
        f"  real accepted       {g('N_REAL_OK'):5d} / {n:<5d}",
        f"  mean y_fake                   = {g('ACC_Y_FAKE')/Q/n:.4f}",
        f"  D logit (pre-sigmoid)         = {g('LOGIT')/Q:+.4f}",
        "",
        "  quantisation health",
        f"    pre-activation clamps       {g('SAT_PRE'):8d}   "
        "(harmless in the tanh/sigmoid layers, a warning in a ReLU layer)",
        f"    output-quantiser clamps     {g('SAT_OUT'):8d}   "
        "(non-zero means a layer's MH/SH scale is too aggressive)",
        "",
        "  throughput",
        f"    image ink (sum of gray)     {g('INK'):8d}   "
        f"(mean pixel {g('INK')/784.0:.1f}/255)",
        f"    compute cycles              {g('CYCLES'):8d}   "
        f"= {g('CYCLES') * 60e-9 * 1e3:.1f} ms at the 60 ns target clock",
    ]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", default=str(OUT_DIR / "gan_loss_series.csv"),
                    help="per-sample sweep CSV (gen_gan_chip_assets.py --sweep N)")
    ap.add_argument("--dump", default=None,
                    help="'NAME VALUE' metric dump read back from the chip")
    ap.add_argument("--print-template", action="store_true",
                    help="print the expected --dump file format and exit")
    args = ap.parse_args()

    if args.print_template:
        print(dump_template())
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report_parts = []

    if args.dump:
        vals = {}
        for line in Path(args.dump).read_text().splitlines():
            line = line.split("#")[0].strip()
            if line:
                k, v = line.split()
                vals[k] = int(v)
        report_parts.append(report_from_dump(vals))

    csv_path = Path(args.csv)
    if csv_path.exists():
        rows = list(csv.DictReader(csv_path.open()))
        series = {
            "loss_G": [float(r["loss_g_f"]) for r in rows],
            "loss_D": [float(r["loss_d_f"]) for r in rows],
        }
        plot = ascii_plot(series)
        png = try_png(series, OUT_DIR / "gan_loss_curve.png")
        fooled = sum(int(r["fooled"]) for r in rows)
        report_parts.append(
            "\n".join([
                f"Per-sample loss curve ({len(rows)} samples from {csv_path.name})",
                "=" * 58,
                plot,
                "",
                f"  mean loss_G = {sum(series['loss_G'])/len(rows):.4f} nats",
                f"  mean loss_D = {sum(series['loss_D'])/len(rows):.4f} nats",
                f"  generator fooled D on {fooled}/{len(rows)} samples",
                f"  {png}",
            ]))
    elif not args.dump:
        raise SystemExit(f"no data: {csv_path} does not exist and no --dump given.\n"
                         f"Run: python3 scripts/gen_gan_chip_assets.py --sweep 10")

    text = "\n\n".join(report_parts)
    (OUT_DIR / "gan_metrics_report.txt").write_text(text + "\n")
    print(text)
    print(f"\nwrote {OUT_DIR / 'gan_metrics_report.txt'}")


if __name__ == "__main__":
    main()
