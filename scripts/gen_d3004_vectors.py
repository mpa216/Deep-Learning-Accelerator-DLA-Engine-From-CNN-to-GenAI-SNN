from __future__ import annotations

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


def _gen_input_vector(length: int) -> list[int]:
    return [((i * 13 + 7) % 256) - 128 for i in range(length)]


def main() -> None:
    root_dir = Path(__file__).resolve().parents[1]
    weights_dir = root_dir / "weights_vh" / "mnist_gan_mlp"
    out_dir = root_dir / "tb" / "data"

    weight = _read_memh_int8(weights_dir / "D300_4_weight.memh")
    bias = _read_memh_int8(weights_dir / "D300_4_bias.memh")

    if len(weight) != 256:
        raise ValueError(f"Expected 256 weights, got {len(weight)}")
    if len(bias) != 1:
        raise ValueError(f"Expected 1 bias, got {len(bias)}")

    input_vec = _gen_input_vector(256)
    acc = sum(w * x for w, x in zip(weight, input_vec))
    acc = _wrap_signed(acc + bias[0], 24)

    out_dir.mkdir(parents=True, exist_ok=True)
    _write_memh(input_vec, out_dir / "d3004_input.memh", 8)
    _write_memh([acc], out_dir / "d3004_expected.memh", 24)
    (out_dir / "d3004_expected.txt").write_text(f"{acc}\n")

    print("Generated d3004_input.memh and d3004_expected.memh")
    print(f"Expected output (signed 24-bit): {acc}")


if __name__ == "__main__":
    main()
