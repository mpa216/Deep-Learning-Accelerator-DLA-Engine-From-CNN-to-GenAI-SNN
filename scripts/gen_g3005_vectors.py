from __future__ import annotations

import argparse
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


def _wrap_signed(value: int, bits: int) -> int:
    mask = (1 << bits) - 1
    value &= mask
    if value & (1 << (bits - 1)):
        value -= 1 << bits
    return value


def _to_hex_signed(value: int, bits: int) -> str:
    mask = (1 << bits) - 1
    if value < 0:
        value = (1 << bits) + value
    return f"{value & mask:0{bits // 4}x}"


def _write_memh(values: list[int], path: Path, bits: int) -> None:
    lines = [_to_hex_signed(v, bits) for v in values]
    path.write_text("\n".join(lines) + "\n")


def _gen_input_vector(length: int, seed: int) -> list[int]:
    return [((i * 13 + 7 + seed * 31) % 256) - 128 for i in range(length)]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate test vectors for G300_4 output row 5 (int8 MAC)."
    )
    parser.add_argument("--row", type=int, default=5, help="Output row index.")
    parser.add_argument("--seed", type=int, default=5, help="Input pattern seed.")
    parser.add_argument(
        "--out-dir",
        default="tb/data",
        help="Output directory relative to repo root.",
    )
    parser.add_argument(
        "--prefix",
        default="g3005",
        help="Output file prefix (default: g3005).",
    )
    args = parser.parse_args()

    root_dir = Path(__file__).resolve().parents[1]
    weights_dir = root_dir / "weights_vh" / "mnist_gan_mlp"
    out_dir = root_dir / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    k = 256
    rows = 784
    if not (0 <= args.row < rows):
        raise ValueError(f"row must be in [0, {rows - 1}], got {args.row}")

    weights = _read_memh_int8(weights_dir / "G300_4_weight.memh")
    bias = _read_memh_int8(weights_dir / "G300_4_bias.memh")

    expected_len = rows * k
    if len(weights) != expected_len:
        raise ValueError(f"Expected {expected_len} weights, got {len(weights)}")
    if len(bias) != rows:
        raise ValueError(f"Expected {rows} bias values, got {len(bias)}")

    input_vec = _gen_input_vector(k, args.seed)
    row_base = args.row * k
    acc = 0
    for i in range(k):
        acc += weights[row_base + i] * input_vec[i]
    acc = _wrap_signed(acc + bias[args.row], 24)

    prefix = args.prefix
    _write_memh(input_vec, out_dir / f"{prefix}_input.memh", 8)
    _write_memh([acc], out_dir / f"{prefix}_expected.memh", 24)
    (out_dir / f"{prefix}_expected.txt").write_text(f"{acc}\n")

    print(f"Generated {prefix}_input.memh and {prefix}_expected.memh")
    print(f"Row {args.row} expected output (signed 24-bit): {acc}")


if __name__ == "__main__":
    main()
