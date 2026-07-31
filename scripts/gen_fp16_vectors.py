"""Model of study/fp16_mac.v and the vectors that verify it.

The FP16 area figure in the operand-width study is only worth quoting if the FP16 MAC
being synthesised actually computes something.  This is a bit-level model of exactly the
algorithm in `study/fp16_mac.v` -- same flush-to-zero, same round-to-nearest-even, same
binary32 accumulator -- used two ways:

  1. it generates `tb/data/fp16_vectors.memh`, which `study/fp16_mac_tb.sv` replays to
     confirm the RTL matches the model bit for bit;
  2. it reports the model's own error against exact float64 arithmetic, so the
     simplifications (no subnormals, no NaN/Inf) are quantified rather than hand-waved.

    python3 scripts/gen_fp16_vectors.py --n 4096
"""

from __future__ import annotations

import argparse
import random
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tb" / "data" / "fp16_vectors.memh"


def f32_bits(x: float) -> int:
    return struct.unpack("<I", struct.pack("<f", x))[0]


def bits_f32(b: int) -> float:
    return struct.unpack("<f", struct.pack("<I", b & 0xFFFFFFFF))[0]


def f16_bits(x: float) -> int:
    return struct.unpack("<H", struct.pack("<e", x))[0]


def bits_f16(b: int) -> float:
    return struct.unpack("<e", struct.pack("<H", b & 0xFFFF))[0]


def mac_model(a16: int, b16: int, acc32: int) -> int:
    """One `fp16_mac` step, mirroring the RTL exactly."""
    sa, ea, ma = a16 >> 15, (a16 >> 10) & 0x1F, a16 & 0x3FF
    sb, eb, mb = b16 >> 15, (b16 >> 10) & 0x1F, b16 & 0x3FF
    if ea == 0 or eb == 0:                      # flush-to-zero product
        return acc32

    pm_raw = (0x400 | ma) * (0x400 | mb)        # 22 bits
    ps = sa ^ sb
    pe_base = ea + eb + 97
    if pm_raw & (1 << 21):
        p_sig, p_exp = pm_raw >> 1, pe_base + 1
    else:
        p_sig, p_exp = pm_raw & 0x1FFFFF, pe_base

    sc, ec, mc = acc32 >> 31, (acc32 >> 23) & 0xFF, acc32 & 0x7FFFFF
    if ec == 0:                                 # accumulator is zero: take the product
        if p_exp <= 0:
            return 0
        if p_exp >= 255:
            return (ps << 31) | (0xFE << 23) | 0x7FFFFF
        return (ps << 31) | ((p_exp & 0xFF) << 23) | ((p_sig & 0xFFFFF) << 3)

    c_ext = (0x800000 | mc) << 24               # leading 1 at bit 47
    p_ext = p_sig << 27                         # leading 1 at bit 47
    ediff = p_exp - ec
    p_bigger = ediff > 0
    shamt = min(abs(ediff), 48)

    big, small = (p_ext, c_ext) if p_bigger else (c_ext, p_ext)
    big_s, small_s = (ps, sc) if p_bigger else (sc, ps)
    res_exp0 = p_exp if p_bigger else ec
    small_al = small >> shamt

    # `big` holds the larger exponent, not necessarily the larger magnitude: with equal
    # exponents the shift is zero and either side can win, so subtract in magnitude order.
    if big_s == small_s:
        sum_raw = big + small_al
        res_sign = big_s
    elif small_al > big:
        sum_raw = small_al - big
        res_sign = small_s
    else:
        sum_raw = big - small_al
        res_sign = big_s

    if sum_raw & (1 << 48):
        norm, norm_exp = sum_raw >> 1, res_exp0 + 1
    else:
        low = sum_raw & ((1 << 48) - 1)
        if low == 0:
            return 0
        lz = 47 - low.bit_length() + 1
        norm, norm_exp = low << lz, res_exp0 - lz

    sig_r = (norm >> 24) & 0xFFFFFF
    rbit = (norm >> 23) & 1
    sticky = 1 if (norm & 0x7FFFFF) else 0
    sig_rnd = sig_r + (1 if (rbit and (sticky or (sig_r & 1))) else 0)
    if sig_rnd & (1 << 24):
        sig_fin, exp_fin = sig_rnd >> 1, norm_exp + 1
    else:
        sig_fin, exp_fin = sig_rnd, norm_exp

    if exp_fin <= 0:
        return 0
    if exp_fin >= 255:
        return (res_sign << 31) | (0xFE << 23) | 0x7FFFFF
    return (res_sign << 31) | ((exp_fin & 0xFF) << 23) | (sig_fin & 0x7FFFFF)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=4096, help="random MAC steps")
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    OUT.parent.mkdir(parents=True, exist_ok=True)

    lines, acc = [], 0
    exact = 0.0                                  # float64 running sum, for the error check
    mag = 0.0                                    # sum of |terms|, the scale of the sum
    worst_rel = 0.0
    for i in range(args.n):
        if i % 256 == 0:                         # restart the dot product periodically
            acc, exact, mag = 0, 0.0, 0.0
        # Values in the range an INT8-scaled activation would occupy after dequantisation.
        a = bits_f16(f16_bits(rng.uniform(-4.0, 4.0)))
        b = bits_f16(f16_bits(rng.uniform(-4.0, 4.0)))
        a16, b16 = f16_bits(a), f16_bits(b)
        acc = mac_model(a16, b16, acc)
        exact += float(a) * float(b)
        mag += abs(float(a) * float(b))
        got = bits_f32(acc)
        # Normalised by the sum of |terms|, not by |sum|: a random-sign dot product
        # passes through zero, and dividing by that would report a meaningless blow-up
        # from ordinary cancellation rather than from any error in the unit.
        if mag > 1e-6:
            worst_rel = max(worst_rel, abs(got - exact) / mag)
        # {a[15:0], b[15:0], acc_out[31:0]} = 64 bits
        lines.append(f"{(a16 << 48) | (b16 << 32) | acc:016x}")

    OUT.write_text("\n".join(lines) + "\n")
    print(f"wrote {OUT}  ({len(lines)} vectors)")
    print(f"model vs exact float64, worst relative error over the run: {worst_rel:.3e}")
    print("  (the model flushes subnormals and omits NaN/Inf; within the dynamic range")
    print("   an INT8-scaled activation occupies, that is the only error it introduces)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
