"""Generate int8 quantization assets + golden output for the DLA-backed G300 pipeline.

The G300 generator MLP (64 -> 256 -> 256 -> 784, ReLU/ReLU/Tanh) is mapped onto the
4x4 DLA engine. The DLA produces only the integer dot product acc = sum(Wq * xq); this
script defines the exact *integer* requantization arithmetic that surrounds it, so that
`rtl/g300_pipeline_top.v` can reproduce the golden output bit-for-bit.

Outputs:
  - rtl/g300_quant_params.vh            : localparam requant constants (included by RTL)
  - tb/data/g300_int8/g300_zq.memh      : int8 quantized latent input (64 values)
  - tb/data/g300_int8/g300_int8_expected.memh : golden 784 signed-8 pixels

Weights/biases are read directly from weights_vh/mnist_gan_mlp/ (already int8) using the
per-tensor scales in weights_manifest.json.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

# Fixed-point / activation constants shared with the RTL.
FP_SHIFT = 20                       # Q20 fixed-point for the tanh path (matches g300 LUT)
LUT_SHIFT = 8
TANH_MAX_FP = 4 << FP_SHIFT         # +/-4.0 clamp range for tanh input
REQUANT_SHIFT = 16                  # shift S for ReLU-layer requant multipliers
REQUANT_SHIFT_L4 = 16               # shift S for the L4 (tanh) dequant-to-Q20 multipliers

ROOT = Path(__file__).resolve().parents[1]
WDIR = ROOT / "weights_vh" / "mnist_gan_mlp"
FP_DIR = ROOT / "tb" / "data" / "g300_fp"
OUT_DIR = ROOT / "tb" / "data" / "g300_int8"


def read_memh_signed(path: Path, bits: int) -> list[int]:
    """Read a $readmemh file of `bits`-wide two's-complement hex values."""
    out: list[int] = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line:
            continue
        val = int(line, 16)
        if val & (1 << (bits - 1)):
            val -= 1 << bits
        out.append(val)
    return out


def to_hex_signed(value: int, bits: int) -> str:
    mask = (1 << bits) - 1
    return f"{value & mask:0{bits // 4}x}"


def round_shift_unsigned(x: int, s: int) -> int:
    # x is guaranteed >= 0 here (post-ReLU). Round-half-up.
    return (x + (1 << (s - 1))) >> s


def round_shift_signed(x: int, s: int) -> int:
    # Matches Verilog signed >>> with round-half-up bias. Python >> is arithmetic floor.
    return (x + (1 << (s - 1))) >> s


def requant_relu(acc: int, bias_q: int, m_acc: int, m_bias: int, s: int) -> int:
    t = acc * m_acc + bias_q * m_bias
    if t < 0:
        t = 0  # ReLU on the scaled pre-activation
    h = round_shift_unsigned(t, s)
    if h > 127:
        h = 127
    return h  # in [0, 127]


def tanh_to_pixel(tanh_fp: int) -> int:
    """Replicates g300_pipeline_top tanh_to_pixel; returns 8-bit signed pattern value."""
    one_fp = 1 << FP_SHIFT
    tmp = (tanh_fp + one_fp) * 255
    pix = (tmp + (1 << FP_SHIFT)) >> (FP_SHIFT + 1)
    if pix < 0:
        pix = 0
    elif pix > 255:
        pix = 255
    res = pix - 128            # equivalent to RTL's signed(pix[7:0]) - 128
    return res                  # range [-128, 127]


def make_mult(real: float, s: int) -> int:
    return round(real * (1 << s))


def load_latent_real(seed, latent_txt) -> list[float]:
    """Return the 64 real-valued latent components for this run."""
    if latent_txt:
        text = Path(latent_txt).read_text()
        return [float(x) for x in text.split()]
    if seed is not None:
        p = (ROOT / "tb" / "data" / "g300_samples" / f"seed_{seed}"
             / f"g300_output{seed}_latent.txt")
        if not p.exists():
            raise FileNotFoundError(f"No latent for seed {seed}: {p}")
        return [float(x) for x in p.read_text().split()]
    # Fallback: dequantize the Q20 latent left by gen_g300_fp_assets.py.
    z_q20 = read_memh_signed(FP_DIR / "g300_latent_fp.memh", 24)
    return [v / (1 << FP_SHIFT) for v in z_q20]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate int8 quant assets + golden for the DLA-backed G300 pipeline."
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Sample seed (0-9) whose saved latent to use. Omit to reuse g300_latent_fp.memh.",
    )
    parser.add_argument(
        "--latent-txt", default=None,
        help="Path to a custom 64-value latent .txt (overrides --seed).",
    )
    args = parser.parse_args()

    manifest = json.loads((WDIR / "weights_manifest.json").read_text())["tensors"]
    sW0 = manifest["G300_0_weight"]["scale"]
    sB0 = manifest["G300_0_bias"]["scale"]
    sW2 = manifest["G300_2_weight"]["scale"]
    sB2 = manifest["G300_2_bias"]["scale"]
    sW4 = manifest["G300_4_weight"]["scale"]
    sB4 = manifest["G300_4_bias"]["scale"]

    W0 = read_memh_signed(WDIR / "G300_0_weight.memh", 8)   # [256*64] row-major [out][in]
    b0 = read_memh_signed(WDIR / "G300_0_bias.memh", 8)     # [256]
    W2 = read_memh_signed(WDIR / "G300_2_weight.memh", 8)   # [256*256]
    b2 = read_memh_signed(WDIR / "G300_2_bias.memh", 8)     # [256]
    W4 = read_memh_signed(WDIR / "G300_4_weight.memh", 8)   # [784*256]
    b4 = read_memh_signed(WDIR / "G300_4_bias.memh", 8)     # [784]

    tanh_lut = read_memh_signed(FP_DIR / "g300_tanh_lut_fp.memh", 24)  # Q20

    # ---- Latent input: select source (seed / custom / fallback), quantize to int8. ----
    z_real = load_latent_real(args.seed, args.latent_txt)
    if len(z_real) != 64:
        raise ValueError(f"Expected 64 latent values, got {len(z_real)}")
    sZ = max(abs(v) for v in z_real) / 127.0
    zq = [max(-127, min(127, round(v / sZ))) for v in z_real]

    L0_OUT, L0_IN = 256, 64
    L2_OUT, L2_IN = 256, 256
    L4_OUT, L4_IN = 784, 256

    # ---- Layer 0: calibrate sH0, then quantize h0. ----
    acc0 = [sum(W0[i * L0_IN + k] * zq[k] for k in range(L0_IN)) for i in range(L0_OUT)]
    h0_real = [max(0.0, sW0 * sZ * acc0[i] + sB0 * b0[i]) for i in range(L0_OUT)]
    sH0 = max(h0_real) / 127.0

    MA0 = make_mult(sW0 * sZ / sH0, REQUANT_SHIFT)
    MB0 = make_mult(sB0 / sH0, REQUANT_SHIFT)
    h0q = [requant_relu(acc0[i], b0[i], MA0, MB0, REQUANT_SHIFT) for i in range(L0_OUT)]

    # ---- Layer 2: calibrate sH2 from integer h0q, then quantize h2. ----
    acc2 = [sum(W2[i * L2_IN + k] * h0q[k] for k in range(L2_IN)) for i in range(L2_OUT)]
    h2_real = [max(0.0, sW2 * sH0 * acc2[i] + sB2 * b2[i]) for i in range(L2_OUT)]
    sH2 = max(h2_real) / 127.0

    MA2 = make_mult(sW2 * sH0 / sH2, REQUANT_SHIFT)
    MB2 = make_mult(sB2 / sH2, REQUANT_SHIFT)
    h2q = [requant_relu(acc2[i], b2[i], MA2, MB2, REQUANT_SHIFT) for i in range(L2_OUT)]

    # ---- Layer 4: dequantize acc to Q20, tanh via LUT, map to pixel. ----
    MW4 = make_mult(sW4 * sH2 * (1 << FP_SHIFT), REQUANT_SHIFT_L4)
    MB4 = make_mult(sB4 * (1 << FP_SHIFT), REQUANT_SHIFT_L4)

    pixels: list[int] = []
    for i in range(L4_OUT):
        acc4 = sum(W4[i * L4_IN + k] * h2q[k] for k in range(L4_IN))
        pre_q20 = round_shift_signed(acc4 * MW4 + b4[i] * MB4, REQUANT_SHIFT_L4)
        if pre_q20 > TANH_MAX_FP:
            pre_q20 = TANH_MAX_FP
        elif pre_q20 < -TANH_MAX_FP:
            pre_q20 = -TANH_MAX_FP
        lut_idx = (pre_q20 + TANH_MAX_FP) >> LUT_SHIFT
        pixels.append(tanh_to_pixel(tanh_lut[lut_idx]))

    # ---- Emit assets. ----
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "g300_zq.memh").write_text(
        "\n".join(to_hex_signed(v, 8) for v in zq) + "\n"
    )
    (OUT_DIR / "g300_int8_expected.memh").write_text(
        "\n".join(to_hex_signed(v, 8) for v in pixels) + "\n"
    )

    vh = f"""// AUTO-GENERATED by scripts/gen_g300_int8_assets.py -- do not edit by hand.
// int8 requantization constants for the DLA-backed G300 pipeline.
localparam integer G300_REQ_SHIFT    = {REQUANT_SHIFT};
localparam integer G300_REQ_SHIFT_L4 = {REQUANT_SHIFT_L4};
localparam signed [63:0] G300_MA0 = 64'sd{MA0};
localparam signed [63:0] G300_MB0 = 64'sd{MB0};
localparam signed [63:0] G300_MA2 = 64'sd{MA2};
localparam signed [63:0] G300_MB2 = 64'sd{MB2};
localparam signed [63:0] G300_MW4 = 64'sd{MW4};
localparam signed [63:0] G300_MB4 = 64'sd{MB4};
"""
    (ROOT / "rtl" / "g300_quant_params.vh").write_text(vh)

    print("Scales: sZ=%.6g sH0=%.6g sH2=%.6g" % (sZ, sH0, sH2))
    print("MA0=%d MB0=%d MA2=%d MB2=%d MW4=%d MB4=%d" % (MA0, MB0, MA2, MB2, MW4, MB4))
    print("Wrote rtl/g300_quant_params.vh, %d zq, %d expected pixels"
          % (len(zq), len(pixels)))
    print("pixel range: [%d, %d]" % (min(pixels), max(pixels)))


if __name__ == "__main__":
    main()
