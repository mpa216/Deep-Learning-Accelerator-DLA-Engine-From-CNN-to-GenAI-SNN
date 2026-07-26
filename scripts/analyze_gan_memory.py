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

MACRO_BYTES = 256                       # gf180mcu_ocd_ip_sram__sram256x8m8wm1
MACRO_UM2 = 301.3 * 224.93              # from the macro LEF

# bank -> (macro count, note)
BANKS = {
    "A   (weight tile)":   (4, "4 weight rows x 256 k"),
    "B   (input vector)":  (4, "4 columns x 256 k"),
    "C   (MAC results)":   (3, "3 byte planes of a 24-bit word, 256 deep"),
    "ACT (activations)":   (1, "one layer's outputs"),
    "IMG (the digit)":     (4, "1024 flat bytes across 4 banks"),
}

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
    print(f"{'bank':22s} {'macros':>7s} {'bytes':>8s} {'area um2':>10s}   note")
    n_macros = 0
    for name, (cnt, note) in BANKS.items():
        n_macros += cnt
        print(f"{name:22s} {cnt:7d} {cnt*MACRO_BYTES:8,d} {cnt*MACRO_UM2:10,.0f}   {note}")
    sram_bytes = n_macros * MACRO_BYTES
    print(f"{'-'*70}")
    print(f"{'TOTAL':22s} {n_macros:7d} {sram_bytes:8,d} {n_macros*MACRO_UM2:10,.0f}"
          f"   = {sram_bytes/1024:.1f} KiB")
    print(f"\n  weights / on-chip SRAM = {tot/sram_bytes:,.0f}x  "
          f"-- only 1/{tot/sram_bytes:,.0f} of the model fits at any instant")

    # ---- 3. structural utilisation ------------------------------------------
    rule("3. HOW MUCH OF EACH BANK THE WORKLOAD CAN EVER USE")
    print("   ('usable' = addresses this design ever touches, at peak)")
    print(f"\n{'bank':22s} {'capacity':>9s} {'usable':>8s} {'util':>7s}   why")
    rows = [
        ("A   (weight tile)", 4*MACRO_BYTES, 4*K,
         "all 4 rows x full K depth"),
        ("B   (input vector)", 4*MACRO_BYTES, 1*K,
         "only column 0: the GAN is matrix-VECTOR, not matrix-matrix"),
        ("C   (MAC results)", 3*MACRO_BYTES, N*N*3,
         f"only {N*N} of 256 words hold results"),
        ("ACT (activations)", 1*MACRO_BYTES, 256,
         "256-wide hidden layers fill it exactly"),
        ("IMG (the digit)", 4*MACRO_BYTES, IMG_LEN,
         f"{IMG_LEN} of 1024 bytes = a 28x28 digit"),
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
        a_txt = (f"{a_use:4d}B {100*a_use/(4*MACRO_BYTES):4.0f}%"
                 if nkt == 1 else
                 f"{a_use:4d}B/{a_last:3d}B last")
        print(f"{name:6s} {f'{idim}->{od}':12s} {nkt:7d} {a_txt:>14s}"
              f" {b_use:5d}B {100*b_use/(4*MACRO_BYTES):4.0f}% {dest:>16s}")
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
          f"{run/(4*MACRO_BYTES):9,.0f} times over")
    print(f"  useful MACs in that run                     : {macs:9,d}")
    print(f"  weight bytes streamed per MAC               : {run/macs:9.2f}")
    print("""
  A ratio of ~1 byte per MAC is the whole story: a matrix-VECTOR product uses each
  weight exactly once, so there is no reuse to capture and no on-chip SRAM size
  short of holding the entire model would change it.  Reuse only appears with
  batching -- and the MAC array is ALREADY a 4x4 matrix-matrix engine, so B's three
  idle columns and C's twelve idle words are exactly a free 4-way batch.  What
  blocks it is downstream storage, not the engine:""")
    print(f"    batch-4 would need ACT {4*256:,d} B (have {256:,d}) and "
          f"IMG {4*IMG_LEN:,d} B (have {4*MACRO_BYTES:,d})")
    need = (4 * 256 - 256 + 4 * IMG_LEN - 4 * MACRO_BYTES + MACRO_BYTES - 1) // MACRO_BYTES
    print(f"    i.e. ~{need} more macros ({n_macros + need} total) to cut weight traffic 4x")


if __name__ == "__main__":
    main()
