from __future__ import annotations

import argparse
import math
from pathlib import Path


def _read_memh_int8(path: Path) -> list[int]:
    values: list[int] = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line:
            continue
        val = int(line, 16)
        if val >= 0x80:
            val -= 0x100
        values.append(val)
    return values


def _read_latent_txt(path: Path) -> list[float]:
    values: list[float] = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line:
            continue
        values.append(float(line))
    return values


def _to_hex_signed(value: int, bits: int) -> str:
    mask = (1 << bits) - 1
    if value < 0:
        value = (1 << bits) + value
    return f"{value & mask:0{(bits + 3) // 4}x}"


def _write_memh(values: list[int], path: Path, bits: int) -> None:
    lines = [_to_hex_signed(v, bits) for v in values]
    path.write_text("\n".join(lines) + "\n")


def _clamp(val: int, lo: int, hi: int) -> int:
    if val < lo:
        return lo
    if val > hi:
        return hi
    return val


def _to_fp(value: float, fp_shift: int) -> int:
    return int(round(value * (1 << fp_shift)))


def _tanh_lut(fp_shift: int, tanh_max: float, lut_shift: int) -> list[int]:
    tanh_max_fp = int(round(tanh_max * (1 << fp_shift)))
    step = 1 << lut_shift
    size = (tanh_max_fp * 2) // step + 1
    out: list[int] = []
    for idx in range(size):
        x_fp = -tanh_max_fp + idx * step
        x = x_fp / float(1 << fp_shift)
        y = math.tanh(x)
        out.append(_to_fp(y, fp_shift))
    return out


def _load_scales(manifest_path: Path) -> dict[str, float]:
    import json

    manifest = json.loads(manifest_path.read_text())
    scales: dict[str, float] = {}
    for name, info in manifest.get("tensors", {}).items():
        scales[name] = float(info["scale"])
    return scales


def _matvec_fp(
    weights_fp: list[int],
    bias_fp: list[int],
    rows: int,
    cols: int,
    x_fp: list[int],
    fp_shift: int,
) -> list[int]:
    out: list[int] = []
    for r in range(rows):
        acc = 0
        base = r * cols
        for c in range(cols):
            acc += weights_fp[base + c] * x_fp[c]
        if acc >= 0:
            acc = (acc + (1 << (fp_shift - 1))) >> fp_shift
        else:
            acc = -(((-acc) + (1 << (fp_shift - 1))) >> fp_shift)
        acc += bias_fp[r]
        out.append(acc)
    return out


def _relu_fp(values: list[int]) -> list[int]:
    return [v if v > 0 else 0 for v in values]


def _tanh_fp(values: list[int], lut: list[int], fp_shift: int, tanh_max: float, lut_shift: int) -> list[int]:
    tanh_max_fp = int(round(tanh_max * (1 << fp_shift)))
    step = 1 << lut_shift
    size = len(lut)
    out: list[int] = []
    for v in values:
        if v > tanh_max_fp:
            v = tanh_max_fp
        elif v < -tanh_max_fp:
            v = -tanh_max_fp
        idx = (v + tanh_max_fp) // step
        if idx < 0:
            idx = 0
        if idx >= size:
            idx = size - 1
        out.append(lut[idx])
    return out


def _tanh_to_pixel(values_fp: list[int], fp_shift: int) -> list[int]:
    one_fp = 1 << fp_shift
    out: list[int] = []
    for v in values_fp:
        tmp = (v + one_fp) * 255
        pix = (tmp + (1 << fp_shift)) >> (fp_shift + 1)
        pix = _clamp(pix, 0, 255)
        out.append(pix - 128)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate fixed-point assets for G300 RTL.")
    parser.add_argument("--seed", type=int, default=5, help="Seed index for latent vector.")
    parser.add_argument("--fp-shift", type=int, default=20, help="Fractional bits for fixed point.")
    parser.add_argument("--tanh-max", type=float, default=4.0, help="Clamp range for tanh input.")
    parser.add_argument("--lut-shift", type=int, default=8, help="LUT step shift in FP units.")
    parser.add_argument(
        "--weight-bits",
        type=int,
        default=0,
        help="Bit width for weights/latent/LUT (default: fp_shift+4).",
    )
    parser.add_argument(
        "--bias-bits",
        type=int,
        default=32,
        help="Bit width for bias values (default: 32).",
    )
    parser.add_argument(
        "--out-dir",
        default="tb/data/g300_fp",
        help="Output directory relative to repo root.",
    )
    args = parser.parse_args()

    root_dir = Path(__file__).resolve().parents[1]
    weights_dir = root_dir / "weights_vh" / "mnist_gan_mlp"
    out_dir = root_dir / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    scales = _load_scales(weights_dir / "weights_manifest.json")

    def load_weight(name: str) -> list[int]:
        raw = _read_memh_int8(weights_dir / f"{name}.memh")
        scale = scales[name]
        return [_to_fp(v * scale, args.fp_shift) for v in raw]

    def load_bias(name: str) -> list[int]:
        raw = _read_memh_int8(weights_dir / f"{name}.memh")
        scale = scales[name]
        return [_to_fp(v * scale, args.fp_shift) for v in raw]

    w_bits = args.weight_bits if args.weight_bits > 0 else (args.fp_shift + 4)
    b_bits = args.bias_bits

    w0_fp = load_weight("G300_0_weight")
    b0_fp = load_bias("G300_0_bias")
    w2_fp = load_weight("G300_2_weight")
    b2_fp = load_bias("G300_2_bias")
    w4_fp = load_weight("G300_4_weight")
    b4_fp = load_bias("G300_4_bias")

    latent_path = root_dir / "tb" / "data" / "g300_samples" / f"seed_{args.seed}" / f"g300_output{args.seed}_latent.txt"
    if not latent_path.exists():
        raise FileNotFoundError(f"Missing latent file: {latent_path}")
    z_float = _read_latent_txt(latent_path)
    if len(z_float) != 64:
        raise ValueError(f"Expected 64 latent values, got {len(z_float)}")
    z_fp = [_to_fp(v, args.fp_shift) for v in z_float]

    tanh_lut = _tanh_lut(args.fp_shift, args.tanh_max, args.lut_shift)

    _write_memh(w0_fp, out_dir / "g300_w0_fp.memh", w_bits)
    _write_memh(b0_fp, out_dir / "g300_b0_fp.memh", b_bits)
    _write_memh(w2_fp, out_dir / "g300_w2_fp.memh", w_bits)
    _write_memh(b2_fp, out_dir / "g300_b2_fp.memh", b_bits)
    _write_memh(w4_fp, out_dir / "g300_w4_fp.memh", w_bits)
    _write_memh(b4_fp, out_dir / "g300_b4_fp.memh", b_bits)
    _write_memh(z_fp, out_dir / "g300_latent_fp.memh", w_bits)
    _write_memh(tanh_lut, out_dir / "g300_tanh_lut_fp.memh", w_bits)

    # Fixed-point reference output to check matching.
    h0 = _relu_fp(_matvec_fp(w0_fp, b0_fp, 256, 64, z_fp, args.fp_shift))
    h2 = _relu_fp(_matvec_fp(w2_fp, b2_fp, 256, 256, h0, args.fp_shift))
    y4 = _matvec_fp(w4_fp, b4_fp, 784, 256, h2, args.fp_shift)
    y4_tanh = _tanh_fp(y4, tanh_lut, args.fp_shift, args.tanh_max, args.lut_shift)
    pixels = _tanh_to_pixel(y4_tanh, args.fp_shift)

    _write_memh(pixels, out_dir / "g300_fp_expected.memh", 8)

    expected_ref = root_dir / "tb" / "data" / "g300_samples" / f"seed_{args.seed}" / "g300_output5.memh"
    if expected_ref.exists():
        exp = _read_memh_int8(expected_ref)
        mismatches = [(i, p, exp[i]) for i, p in enumerate(pixels) if p != exp[i]]
        if mismatches:
            first = mismatches[0]
            print(
                "Fixed-point output does NOT match float reference. "
                f"First mismatch idx={first[0]} fp={first[1]} ref={first[2]} "
                f"(total {len(mismatches)})"
            )
        else:
            print("Fixed-point output matches float reference.")
    else:
        print(f"Reference memh not found: {expected_ref}")

    print("Wrote fixed-point assets to", out_dir)


if __name__ == "__main__":
    main()
