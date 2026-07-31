"""Per-stage latency breakdown and end-to-end time for both accelerator variants.

Written to answer three reviewer requests on the APSIPA paper:

  * "A more detailed breakdown of the processing time is recommended. The authors
     should report the latency of each major stage."
  * "...include an estimated total end-to-end latency (including serial link
     transmission overhead at a nominal serial clock rate)."
  * (indirectly) the INT8 justification, since this design is link-bound and the
     operand width multiplies the dominant term directly -- see
     scripts/quant_tradeoff_study.py, which consumes the bytes-per-image figure here.

Nothing here is a hand count of FSM states.  The per-tile cycle costs are MEASURED by
`tb/dla_latency_tb.sv` and read from `tb/data/dla_latency.txt`; the tile schedule is read
off the RTL (`rtl/g300_pipeline_top.v` for the main chip, `rtl/gan_sequencer.v` +
`tb/gan_batch4_flow_tb.sv` for the experimental one); the serial-link frame widths come
from the two bridges.  Run the testbench first:

    iverilog -g2012 -I rtl -s dla_latency_tb -o sim/results/dla_latency_tb.vvp \\
      rtl/dla_*.v rtl/gf180_sram_1rw_256x8.v rtl/gan_sram_1rw.v tb/dla_latency_tb.sv
    vvp sim/results/dla_latency_tb.vvp
    python3 scripts/analyze_latency.py --latex APIC_Paper/tab_latency.tex

The headline result: on both chips the serial link dominates end to end by more than two
orders of magnitude, so "peak GOPS" and "compute time" describe a small fraction of the
real latency.  That is a property of the workload, not a bug -- a matrix-VECTOR product
reuses no weight, so 1.01 weight bytes cross the link per MAC (scripts/analyze_memory).
"""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAT_FILE = ROOT / "tb" / "data" / "dla_latency.txt"

# Measured fallbacks, used only if the testbench has not been run.  Keep in step with
# tb/data/dla_latency.txt; the script says which source it used.
DEFAULT_PRIMS = {"N": 4, "K": 256, "T_AWRITE": 1026, "T_BWRITE": 258,
                 "T_START": 260, "T_WB": 278, "T_CREAD": 2}

# Measured sequencer cycle counts for the experimental chip, printed by MET_CYCLES in
# tb/gan_engine_top_tb.sv and tb/gan_batch4_flow_tb.sv.  These count every busy cycle --
# the LOADB copies, the zeroing passes and the flushes as well as the MAC tiles -- so
# they are used in preference to a tiles-only estimate, which undercounts by ~1.5x.
GAN_CYCLES_MEASURED = {1: 440252, 4: 413592}    # batch -> cycles for the whole pass


# ---------------------------------------------------------------------------
# Link models (frame widths in SCLK edges, straight from the two bridges)
# ---------------------------------------------------------------------------
class Link:
    """A serial bridge's cost model.

    Both bridges shift one bit per SCLK edge behind a double-flop synchroniser, which
    caps SCLK at clk/8 -- i.e. one edge every 4 core clocks.  `edge_clks` makes that
    explicit so the assumption is visible rather than baked into a constant.
    """

    def __init__(self, name, hdr, data_bits, read_bits, exec_bits, edge_clks=4,
                 burst_hdr=None, burst_bits_per_byte=None):
        self.name = name
        self.hdr = hdr                                  # CMD + ADDR, in edges
        self.data_bits = data_bits                      # payload of a byte write
        self.read_bits = read_bits                      # payload of a read
        self.exec_bits = exec_bits                      # payload of START / EXEC
        self.edge_clks = edge_clks
        self.burst_hdr = burst_hdr
        self.burst_bits_per_byte = burst_bits_per_byte

    def write_edges(self, nbytes, mode="single"):
        if mode == "single" or self.burst_hdr is None:
            return nbytes * (self.hdr + self.data_bits)
        # One header, then the payload auto-increments to the end of the block.
        return self.burst_hdr + nbytes * self.burst_bits_per_byte

    def read_edges(self, nwords):
        return nwords * (self.hdr + self.read_bits)

    def exec_edges(self, n):
        return n * (self.hdr + self.exec_bits)


# rtl/dla_serial_bridge.v : CMD[1:0] + ADDR[9:0] = 12, then 8 data / 24 read / 0 exec
LINK_MAIN = Link("4-wire serial", hdr=12, data_bits=8, read_bits=24, exec_bits=0)

# rtl/gan_serial_bridge.v : CMD[3:0] + ADDR[11:0] = 16, then 8 / 24 / 0.
# WR_BURST sends the header once and auto-increments (8 edges per byte); WR_BURST8 moves
# a whole byte per edge off the 8-bit parallel bus on bidir[8..15].
LINK_GAN = Link("4-wire serial", hdr=16, data_bits=8, read_bits=24, exec_bits=0)
LINK_GAN_BURST = Link("serial burst", hdr=16, data_bits=8, read_bits=24, exec_bits=0,
                      burst_hdr=16, burst_bits_per_byte=8)
LINK_GAN_BURST8 = Link("parallel burst", hdr=16, data_bits=8, read_bits=24, exec_bits=0,
                       burst_hdr=16, burst_bits_per_byte=1)


# ---------------------------------------------------------------------------
# Layer schedules
# ---------------------------------------------------------------------------
class Layer:
    """One dense layer's mapping onto the 4x4 array.

    `a_tight` is the weight bytes the model actually contains; `a_padded` is what the
    RTL streams, because `g300_pipeline_top` always writes the full K=256 depth and
    zero-pads.  The gap is entirely layer L0 (64 inputs padded to 256) and a host is
    free to close it by zeroing the pad once -- both numbers are reported.
    """

    def __init__(self, name, out_dim, in_dim, nout=4, k_native=256):
        self.name = name
        self.out_dim, self.in_dim, self.nout = out_dim, in_dim, nout
        self.k_tiles = max(1, -(-in_dim // k_native))
        self.tiles = -(-out_dim // nout)
        self.tile_ops = self.tiles * self.k_tiles
        self.a_padded = self.tile_ops * 4 * k_native
        self.a_tight = self.tiles * 4 * in_dim
        self.c_reads = self.tiles * nout


G_LAYERS = [Layer("G L0", 256, 64), Layer("G L2", 256, 256), Layer("G L4", 784, 256)]
D_LAYERS = [Layer("D L0", 256, 784), Layer("D L2", 256, 256), Layer("D L4", 1, 256, nout=1)]


def fmt_t(seconds: float) -> str:
    if seconds >= 1.0:
        return f"{seconds:8.3f} s "
    if seconds >= 1e-3:
        return f"{seconds * 1e3:8.3f} ms"
    return f"{seconds * 1e6:8.3f} us"


# ---------------------------------------------------------------------------
def analyse_main(prims, clk_ns, tight, link=LINK_MAIN):
    """The taped-out chip: generator only, host does requantisation and activation."""
    rows, tot = [], {"tiles": 0, "cyc": 0, "abytes": 0, "bbytes": 0, "creads": 0}
    for L in G_LAYERS:
        a = L.a_tight if tight else L.a_padded
        b = 256                                  # B is loaded once per layer, full depth
        cyc = L.tile_ops * prims["T_WB"]
        rows.append({"name": L.name, "tiles": L.tile_ops, "cyc": cyc,
                     "abytes": a, "bbytes": b, "creads": L.c_reads})
        tot["tiles"] += L.tile_ops
        tot["cyc"] += cyc
        tot["abytes"] += a
        tot["bbytes"] += b
        tot["creads"] += L.c_reads

    t_edge = link.edge_clks * clk_ns * 1e-9
    stages = [
        ("weight stream (A)", link.write_edges(tot["abytes"]), tot["abytes"]),
        ("input vector (B)", link.write_edges(tot["bbytes"]), tot["bbytes"]),
        ("START commands", link.exec_edges(tot["tiles"]), 0),
        ("result read (C)", link.read_edges(tot["creads"]), tot["creads"] * 3),
    ]
    link_edges = sum(s[1] for s in stages)
    return rows, tot, stages, link_edges, t_edge


def analyse_gan(prims, clk_ns, batch, link, drain=True, tight=False):
    """The experimental chip: G and D on chip, four lanes off one weight stream.

    At batch 4 the host must also feed D's 784-wide input back per K-tile (four digits do
    not fit on chip), which is why batching is 2.44x on total bytes and not 4x.
    """
    n_img = batch
    a_bytes = b_bytes = rd_words = 0
    tile_ops = 0
    execs = 0

    for L in G_LAYERS:                                    # generator, once per weight stream
        a_bytes += L.a_tight if tight else L.a_padded
        tile_ops += L.tile_ops
        execs += L.tiles * 2 + L.tile_ops                 # CLR_ACC + FLUSH + TILE
    b_bytes += 256 * batch                                # the latents, once
    execs += 2                                            # LOADB_ACT for L2 and L4

    for _pass in range(2):                                # D on the fakes, then on the real
        for L in D_LAYERS:
            a_bytes += L.a_tight if tight else L.a_padded
            tile_ops += L.tile_ops
            execs += L.tiles * 2 + L.tile_ops
            if L.in_dim == 784:                           # host feeds the pixels back
                b_bytes += L.tile_ops * 256 * batch
        execs += 2

    img_reads = 784 * batch if drain else 0               # the generated digits
    met_reads = 8 + 4

    t_edge = link.edge_clks * clk_ns * 1e-9
    stages = [
        ("weight stream (A)", link.write_edges(a_bytes, "burst"), a_bytes),
        ("input / pixel feed (B)", link.write_edges(b_bytes, "burst"), b_bytes),
        ("opcodes (EXEC)", link.exec_edges(execs), 0),
        ("image drain (IMG)", link.read_edges(img_reads), img_reads),
        ("metric reads", link.read_edges(met_reads), met_reads * 3),
    ]
    link_edges = sum(s[1] for s in stages)
    cyc = GAN_CYCLES_MEASURED.get(batch, tile_ops * prims["T_WB"])
    return {"tile_ops": tile_ops, "cyc": cyc, "abytes": a_bytes, "bbytes": b_bytes,
            "stages": stages, "edges": link_edges, "t_edge": t_edge, "n_img": n_img}


# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--clk-main", type=float, default=40.0, help="main chip period, ns")
    ap.add_argument("--clk-gan", type=float, default=60.0, help="experimental period, ns")
    ap.add_argument("--sclk-edge-clks", type=int, default=4,
                    help="core clocks per SCLK edge. The bridges double-flop and "
                         "edge-detect SCLK, needing each level stable for >=3 clocks; "
                         "SCLK = clk/8 in FREQUENCY therefore means one edge every 4 "
                         "clocks, which is the default. Pass 8 to reproduce the more "
                         "conservative figures quoted in CHANGES_EXPLAINED.md")
    ap.add_argument("--tight", action="store_true",
                    help="count only the weight bytes the model contains, assuming the "
                         "host zero-pads L0 once instead of every tile")
    ap.add_argument("--latex", default=None, help="also write a LaTeX table here")
    args = ap.parse_args()

    for lk in (LINK_MAIN, LINK_GAN, LINK_GAN_BURST, LINK_GAN_BURST8):
        lk.edge_clks = args.sclk_edge_clks

    prims, src = dict(DEFAULT_PRIMS), "built-in defaults (run tb/dla_latency_tb.sv!)"
    if LAT_FILE.exists():
        prims = dict(DEFAULT_PRIMS)
        for line in LAT_FILE.read_text().splitlines():
            if line.startswith("#") or not line.strip():
                continue
            k, v = line.split()
            prims[k] = int(v)
        src = str(LAT_FILE.relative_to(ROOT))

    print("=" * 78)
    print("Per-stage latency, taped-out chip (dla_engine_top + dla_serial_bridge)")
    print("=" * 78)
    print(f"measured per-tile costs from: {src}")
    print(f"  T_WB = {prims['T_WB']} cycles per tile "
          f"(K={prims['K']} accumulate + {prims['T_WB'] - prims['K']} controller/writeback)")
    print(f"  clock {args.clk_main:.0f} ns ({1e3/args.clk_main:.1f} MHz), "
          f"SCLK = clk/8 -> one edge per {LINK_MAIN.edge_clks} clocks "
          f"({LINK_MAIN.edge_clks * args.clk_main:.0f} ns)")
    print()

    rows, tot, stages, edges, t_edge = analyse_main(prims, args.clk_main, args.tight)
    print(f"{'layer':8s} {'tiles':>6s} {'compute cyc':>12s} {'compute':>11s} "
          f"{'A bytes':>10s} {'C reads':>8s}")
    for r in rows:
        print(f"{r['name']:8s} {r['tiles']:6d} {r['cyc']:12,d} "
              f"{fmt_t(r['cyc'] * args.clk_main * 1e-9):>11s} {r['abytes']:10,d} "
              f"{r['creads']:8,d}")
    t_compute = tot["cyc"] * args.clk_main * 1e-9
    print(f"{'TOTAL':8s} {tot['tiles']:6d} {tot['cyc']:12,d} {fmt_t(t_compute):>11s} "
          f"{tot['abytes']:10,d} {tot['creads']:8,d}")
    print()

    print("end-to-end, one 28x28 image over the serial link:")
    print(f"  {'stage':24s} {'edges':>12s} {'bytes':>10s} {'time':>11s}   share")
    for name, e, b in stages:
        t = e * t_edge
        print(f"  {name:24s} {e:12,d} {b:10,d} {fmt_t(t):>11s}   "
              f"{100.0 * e / edges:5.1f}%")
    t_link = edges * t_edge
    print(f"  {'LINK TOTAL':24s} {edges:12,d} {'':10s} {fmt_t(t_link):>11s}   100.0%")
    print()
    print(f"  pure compute (array busy)          {fmt_t(t_compute)}   "
          f"{100.0 * t_compute / (t_link + t_compute):5.2f}% of end to end")
    print(f"  END TO END per image               {fmt_t(t_link + t_compute)}")
    print(f"  link / compute ratio               {t_link / t_compute:.0f}x")
    print(f"  throughput                         "
          f"{1.0 / (t_link + t_compute):.3f} images/s")
    peak_gops = 2 * 16 / (args.clk_main * 1e-9) / 1e9
    eff_gops = 2 * tot["tiles"] * 4 * prims["K"] / (t_link + t_compute) / 1e9
    print(f"  peak {peak_gops:.2f} GOPS (16 MACs/cycle) vs effective "
          f"{eff_gops * 1e3:.2f} MOPS end to end")
    print()

    # ---- normalised efficiency, for the comparison table --------------------
    # Both figures come from librelane/runs/as3v3_k256_d63/final/metrics.json:
    # design__core__area = 2.32591 mm^2, power__total = 0.16167 W at the tt corner.
    area_mm2, power_w = 2.32591, 0.16167
    print("  efficiency metrics (Stage-1 macro, tool-reported at 25 MHz):")
    print(f"    core area              {area_mm2:.3f} mm2")
    print(f"    power                  {power_w * 1e3:.0f} mW")
    print(f"    peak density           {peak_gops / area_mm2:.3f} GOPS/mm2")
    print(f"    peak efficiency        {peak_gops / power_w:.2f} GOPS/W")
    print(f"    compute energy/image   {power_w * t_compute * 1e3:.3f} mJ "
          f"(array busy only)")
    for node in (65, 40):
        s = (node / 180.0) ** 2
        print(f"    area scaled to {node} nm    {area_mm2 * s:.3f} mm2 "
              f"(ideal (L/L0)^2 scaling, quote with care)")
    print()
    print("  CAUTION: the chip-level run reports power__total = 0.268 mW, which is the")
    print("  padring and glue only -- the hardened accelerator is a black box in that")
    print("  run and its internal switching is not modelled. 162 mW is the figure to")
    print("  quote for the accelerator; 0.268 mW must not be presented as chip total.")
    print()

    # ---- the experimental chip ---------------------------------------------
    print("=" * 78)
    print("Experimental full-GAN chip (gan_engine_top + gan_serial_bridge)")
    print("=" * 78)
    print(f"  clock {args.clk_gan:.0f} ns, G + D(fake) + D(real) per pass")
    print()
    print(f"  {'configuration':34s} {'edges/pass':>12s} {'per image':>11s} {'speed-up':>9s}")
    base = None
    for batch, link in ((1, LINK_GAN), (1, LINK_GAN_BURST), (1, LINK_GAN_BURST8),
                        (4, LINK_GAN_BURST8)):
        r = analyse_gan(prims, args.clk_gan, batch, link, tight=args.tight)
        t = r["edges"] * r["t_edge"] + r["cyc"] * args.clk_gan * 1e-9
        per = t / r["n_img"]
        if base is None:
            base = per
        print(f"  batch {batch}, {link.name:20s} {r['edges']:12,d} "
              f"{fmt_t(per):>11s} {base / per:8.2f}x")
    r4 = analyse_gan(prims, args.clk_gan, 4, LINK_GAN_BURST8, tight=args.tight)
    print()
    print(f"  batch-4 compute {r4['cyc']:,} cycles for 4 images = "
          f"{r4['cyc'] // 4:,} per image "
          f"({fmt_t(r4['cyc'] * args.clk_gan * 1e-9 / 4)} each)")
    print(f"  batch-4 weight bytes {r4['abytes']:,}, pixel feed-back {r4['bbytes']:,}")
    print()
    print("  Note: batching amortises the WEIGHT stream 4x but not the total bytes -- at")
    print("  batch 4 the host must feed D's 784-wide input back per K-tile, because four")
    print("  digits (3,136 B) do not fit in the 1 KiB image buffer.")
    print()
    # ---- would it be better to run D on the host? -------------------------
    # D costs no silicon (it is the same datapath as G, selected by CFG_DST_SEL), so this
    # is purely a traffic question -- and the host already holds every D weight, because
    # it is the thing streaming them.
    g_w = sum(L.a_tight for L in G_LAYERS)
    d_w = 2 * sum(L.a_tight for L in D_LAYERS)          # fake pass + real pass
    d_refeed = 2 * (D_LAYERS[0].tile_ops * 256)         # D-only: the 784-wide input
    total_w = g_w + d_w + d_refeed + 256
    print("  running D on the HOST instead (no RTL change -- just stop issuing the ops):")
    print(f"    G weights {g_w:9,d} | D weights {d_w:9,d} | D pixel re-feed "
          f"{d_refeed:9,d}")
    print(f"    D is {100.0 * (d_w + d_refeed) / total_w:.1f}% of link traffic -> moving "
          f"it off chip is {total_w / (g_w + 256):.2f}x end to end")
    print()
    r1 = analyse_gan(prims, args.clk_gan, 1, LINK_GAN, tight=args.tight)
    print(f"  D's pixel re-feed costs {r1['bbytes']:,} B at batch 1 against the 3,136 B")
    print("  strictly needed: the host must reload B for every (output tile, K-tile) pair")
    print("  because only 16 accumulators exist, so the input vector cannot be held while")
    print("  the output tiles sweep. An accumulator bank sized to a whole output layer")
    print("  would remove it -- the largest single traffic saving still on the table.")
    print()
    print(f"  Serial-rate convention: one SCLK edge per {args.sclk_edge_clks} core clocks.")
    print("  The bridges double-flop and edge-detect SCLK and need each level stable for")
    print("  >=3 clocks, so SCLK = clk/8 in frequency permits one edge every 4 clocks.")
    print("  CHANGES_EXPLAINED.md's 9.448 s / 0.161 s figures assume one edge every 8")
    print("  clocks AND count weight bytes only (no opcode, pixel-refeed or drain")
    print("  traffic), so they are optimistic on traffic and pessimistic on rate by 2x;")
    print("  the two errors partly cancel. The figures above count every byte.")

    if args.latex:
        out = Path(args.latex)
        lines = [
            "% generated by scripts/analyze_latency.py -- do not edit by hand",
            r"\begin{table}[h]",
            r"\caption{End-to-end latency breakdown for one $28\times28$ image "
            r"(40~ns clock, serial clock at \texttt{clk}/8).}",
            r"\label{tab:latency}",
            r"\centering",
            r"\renewcommand{\arraystretch}{1.08}",
            r"\begin{tabular}{@{}lrrr@{}}",
            r"\toprule",
            r"Stage & Bytes & SCLK edges & Time \\",
            r"\midrule",
        ]
        for name, e, b in stages:
            bs = f"{b:,}" if b else "---"
            lines.append(f"{name} & {bs} & {e:,} & "
                         f"{fmt_t(e * t_edge).strip()} \\\\")
        lines += [
            r"\midrule",
            f"Serial link total & --- & {edges:,} & {fmt_t(t_link).strip()} \\\\",
            f"PE array compute & --- & --- & {fmt_t(t_compute).strip()} \\\\",
            r"\midrule",
            f"\\textbf{{End to end}} & --- & --- & "
            f"\\textbf{{{fmt_t(t_link + t_compute).strip()}}} \\\\",
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{table}",
        ]
        out.write_text("\n".join(lines) + "\n")
        print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
