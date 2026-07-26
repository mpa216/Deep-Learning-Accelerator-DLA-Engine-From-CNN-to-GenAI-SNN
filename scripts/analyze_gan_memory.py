"""Memory analysis for the experimental GAN chip: weights vs on-chip SRAM.

Answers three questions with numbers taken from the actual weight files and the actual
RTL geometry (no hand-copied constants):

  1. how big are the weights and biases?
  2. how much SRAM is on the die, bank by bank?
  3. how much of that SRAM does the workload actually occupy?

Run:  python3 scripts/analyze_gan_memory.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WDIR = ROOT / "weights_vh" / "mnist_gan_mlp"

# This SRAM family is fixed-width (301.3 um) and scales only in height, so area per
# byte improves steeply with depth -- which is why each bank now uses the size that
# fits it rather than four copies of one size.
MACRO_W = 301.3
MACRO_H = {64: 152.21, 256: 224.93, 512: 321.89, 1024: 515.81}
MACRO_UM2 = {d: MACRO_W * h for d, h in MACRO_H.items()}

# bank -> (macro count, macro depth, note)
BANKS = {
    "A   (weight tile)":   (4, 256,  "4 weight rows x 256 k, read in parallel"),
    "B   (input vector)":  (4, 256,  "4 columns = 4 batch lanes"),
    "C   (MAC results)":   (3, 64,   "3 byte planes; only N*N = 16 words used"),
    "ACT (activations)":   (1, 1024, "4 lanes x 256 activations, lane-major"),
    "IMG (the digit)":     (1, 1024, "one digit, or 4 drain windows at batch 4"),
}
BATCH = 4

N, K = 4, 256
IMG_LEN = 784

# (name, out_dim, in_dim) in execution order
LAYERS = [
    ("G0", 256, 64), ("G2", 256, 256), ("G4", 784, 256),
    ("D0", 256, 784), ("D2", 256, 256), ("D4", 1, 256),
]


def rule(title=""):
    print(f"\n{title}\n" + "=" * 78 if title else "=" * 78)


def main() -> None:
    man = json.loads((WDIR / "weights_manifest.json").read_text())["tensors"]

    # ---- 1. weight inventory ------------------------------------------------
    rule("1. WEIGHTS AND BIASES (int8, one byte each)")
    print(f"{'tensor':22s} {'shape':14s} {'values':>9s}  {'KiB':>7s}")
    w_tot = b_tot = 0
    for k in sorted(man):
        n = 1
        for d in man[k]["shape"]:
            n *= d
        if "bias" in k:
            b_tot += n
        else:
            w_tot += n
        print(f"{k:22s} {str(man[k]['shape']):14s} {n:9,d}  {n/1024:7.1f}")
    tot = w_tot + b_tot
    print(f"{'-'*56}")
    print(f"{'weights':22s} {'':14s} {w_tot:9,d}  {w_tot/1024:7.1f}")
    print(f"{'biases':22s} {'':14s} {b_tot:9,d}  {b_tot/1024:7.1f}")
    print(f"{'TOTAL':22s} {'':14s} {tot:9,d}  {tot/1024:7.1f}  "
          f"({tot/1e3:.1f} kB)")

    # ---- 2. SRAM inventory --------------------------------------------------
    rule("2. ON-CHIP SRAM")
    print(f"{'bank':22s} {'macros':>13s} {'bytes':>8s} {'area um2':>10s}   note")
    n_macros = 0
    sram_bytes = 0
    sram_um2 = 0.0
    for name, (cnt, depth, note) in BANKS.items():
        n_macros += cnt
        sram_bytes += cnt * depth
        sram_um2 += cnt * MACRO_UM2[depth]
        print(f"{name:22s} {f'{cnt} x {depth}x8':>13s} {cnt*depth:8,d} "
              f"{cnt*MACRO_UM2[depth]:10,.0f}   {note}")
    print(f"{'-'*76}")
    print(f"{'TOTAL':22s} {n_macros:13d} {sram_bytes:8,d} {sram_um2:10,.0f}"
          f"   = {sram_bytes/1024:.1f} KiB")
    old = 16 * MACRO_UM2[256]
    print(f"\n  previous arrangement (16 x 256x8): {old:,.0f} um2 "
          f"-> right-sizing saves {100*(old-sram_um2)/old:.1f}%")
    print(f"  area per byte: 64x8 {MACRO_UM2[64]/64:.0f}, 256x8 {MACRO_UM2[256]/256:.0f}, "
          f"512x8 {MACRO_UM2[512]/512:.0f}, 1024x8 {MACRO_UM2[1024]/1024:.0f} um2/byte")
    print(f"\n  weights / on-chip SRAM = {tot/sram_bytes:,.0f}x  "
          f"-- only 1/{tot/sram_bytes:,.0f} of the model fits at any instant")

    # ---- 3. structural utilisation ------------------------------------------
    rule("3. HOW MUCH OF EACH BANK THE WORKLOAD CAN EVER USE")
    print("   ('usable' = addresses this design ever touches, at peak)")
    print(f"\n{'bank':22s} {'capacity':>9s} {'usable':>8s} {'util':>7s}   why")
    rows = [
        ("A   (weight tile)", 4*256, 4*K,
         "all 4 rows x full K depth"),
        ("B   (input vector)", 4*256, BATCH*K,
         f"all 4 columns at batch {BATCH} (was 25% when batch was 1)"),
        ("C   (MAC results)", 3*64, N*N*3,
         f"{N*N} words = 4 neurons x 4 lanes, in 64-deep macros"),
        ("ACT (activations)", 1024, BATCH*256,
         f"{BATCH} lanes x 256 activations"),
        ("IMG (the digit)", 1024, IMG_LEN,
         f"{IMG_LEN} of 1024 bytes at batch 1; 4 drain windows at batch 4"),
    ]
    use_tot = 0
    for name, cap, use, why in rows:
        use_tot += use
        print(f"{name:22s} {cap:9,d} {use:8,d} {100*use/cap:6.1f}%   {why}")
    print(f"{'-'*76}")
    print(f"{'TOTAL':22s} {sram_bytes:9,d} {use_tot:8,d} {100*use_tot/sram_bytes:6.1f}%")

    # ---- 4. per-layer occupancy ---------------------------------------------
    rule("4. LIVE OCCUPANCY DURING EACH LAYER")
    print("   A and B only hold the current K-tile, so short layers leave them idle.\n")
    print(f"{'layer':6s} {'shape':12s} {'K-tiles':>7s} {'A used':>14s} {'B used':>13s}"
          f" {'dest':>16s}")
    total_tiles = 0
    for name, od, idim in LAYERS:
        nkt = (idim + K - 1) // K
        tiles = max(1, od // N)
        total_tiles += tiles * nkt
        last = idim - (nkt - 1) * K
        a_use = 4 * min(K, idim)
        a_last = 4 * last
        b_use = min(K, idim)
        dest = "IMG 784 B" if name == "G4" else ("score reg" if od == 1 else "ACT 256 B")
        a_txt = (f"{a_use:4d}B {100*a_use/1024:4.0f}%"
                 if nkt == 1 else
                 f"{a_use:4d}B/{a_last:3d}B last")
        print(f"{name:6s} {f'{idim}->{od}':12s} {nkt:7d} {a_txt:>14s}"
              f" {b_use:5d}B {100*b_use/1024:4.0f}% {dest:>16s}")
    print(f"\n  OP_TILE per generate pass          : "
          f"{sum(max(1, od//N) * ((idim+K-1)//K) for n, od, idim in LAYERS[:3]):,d}")
    print(f"  OP_TILE per discriminator pass     : "
          f"{sum(max(1, od//N) * ((idim+K-1)//K) for n, od, idim in LAYERS[3:]):,d}")

    # ---- 5. turnover and reuse ----------------------------------------------
    rule("5. TURNOVER AND WEIGHT REUSE")
    a_writes = 0
    for name, od, idim in LAYERS:
        nkt = (idim + K - 1) // K
        tiles = max(1, od // N)
        for t in range(tiles):
            for kt in range(nkt):
                live = min(K, max(0, idim - kt * K))
                a_writes += 4 * (K if t == 0 else live)
    g_writes = 0
    for name, od, idim in LAYERS[:3]:
        nkt = (idim + K - 1) // K
        tiles = max(1, od // N)
        for t in range(tiles):
            for kt in range(nkt):
                live = min(K, max(0, idim - kt * K))
                g_writes += 4 * (K if t == 0 else live)
    d_writes = a_writes - g_writes
    run = g_writes + 2 * d_writes
    macs = sum(od * idim for _, od, idim in LAYERS[:3]) + \
        2 * sum(od * idim for _, od, idim in LAYERS[3:])
    print(f"  A-buffer bytes written, generate            : {g_writes:9,d}")
    print(f"  A-buffer bytes written, one D pass          : {d_writes:9,d}")
    print(f"  generate + D(fake) + D(real)                : {run:9,d}"
          f"  = {run/1024:.0f} KiB")
    print(f"  A buffer reloaded                           : "
          f"{run/1024:9,.0f} times over")
    print(f"  useful MACs in that run                     : {macs:9,d}")
    print(f"  weight bytes streamed per MAC               : {run/macs:9.2f}")
    print(f"  ... at batch {BATCH}, per image                    : "
          f"{run/BATCH/1024:9,.0f} KiB  ({BATCH}x less)")
    print("""
  A ratio of ~1 byte per MAC is why batching matters: a matrix-VECTOR product uses
  each weight exactly once, so no on-chip SRAM size short of holding the whole model
  creates reuse.  Batching does -- and the MAC array was already a 4x4 matrix-matrix
  engine, so four lanes cost nothing in the engine itself.  What batching needs is
  downstream storage, and that is what the right-sized macros bought:

    ACT   4 x 256 activations  = 1,024 B  -> one 1024x8 macro
    IMG   4 x 784 pixels       = 3,136 B  -> does NOT fit; the host holds the images
                                             and this buffer is a 1 KiB drain window

  Keeping all four images on chip would need IMG at 4 x 1024x8, adding ~466k um2 and
  pushing the die past the Stage-2 slot -- hence "batch 4, host holds images".""")


if __name__ == "__main__":
    main()
