"""Generate golden vectors for the N=4/K=256 DLA unit test (dla_engine_top_d3004n4_tb.sv).

Same shared input vector and DLA configuration (K=256) as gen_d3004_vectors.py, but
exercises all 4 output rows (N=4) instead of 1, matching the real hardened
dla_engine_top default (N=4, K=256). Row 0 reuses D300_4_weight.memh/D300_4_bias.memh
exactly, so its golden value must equal d3004's own golden output (-34139) -- a
built-in cross-check between the two unit tests.
"""
from __future__ import annotations

from pathlib import Path

N = 4
K = 256


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
    # Identical formula to gen_d3004_vectors.py -- same shared input for every row.
    return [((i * 13 + 7) % 256) - 128 for i in range(length)]


def _gen_weight_row(row: int, length: int) -> list[int]:
    # Distinct deterministic formula per row (rows 1-3); row 0 uses the real
    # D300_4_weight.memh fixture instead, so its result cross-checks against d3004.
    a = 17 + 4 * row
    b = 11 + 9 * row
    return [((k * a + b) % 256) - 128 for k in range(length)]


def _gen_bias(row: int) -> int:
    return _wrap_signed(23 * row - 50, 8)


def main() -> None:
    root_dir = Path(__file__).resolve().parents[1]
    weights_dir = root_dir / "weights_vh" / "mnist_gan_mlp"
    out_dir = root_dir / "tb" / "data"
    out_dir.mkdir(parents=True, exist_ok=True)

    input_vec = _gen_input_vector(K)

    d3004_weight = _read_memh_int8(weights_dir / "D300_4_weight.memh")
    d3004_bias = _read_memh_int8(weights_dir / "D300_4_bias.memh")
    if len(d3004_weight) != K:
        raise ValueError(f"Expected {K} weights, got {len(d3004_weight)}")
    if len(d3004_bias) != 1:
        raise ValueError(f"Expected 1 bias, got {len(d3004_bias)}")

    weight_rows: list[list[int]] = [d3004_weight]
    bias_vals: list[int] = [d3004_bias[0]]
    for row in range(1, N):
        weight_rows.append(_gen_weight_row(row, K))
        bias_vals.append(_gen_bias(row))

    expected: list[int] = []
    for row in range(N):
        acc = sum(w * x for w, x in zip(weight_rows[row], input_vec))
        acc = _wrap_signed(acc + bias_vals[row], 24)
        expected.append(acc)

    # Cross-check: row 0 must reproduce d3004's own golden value exactly.
    D3004_GOLDEN = -34139
    if expected[0] != D3004_GOLDEN:
        raise AssertionError(
            f"Row 0 golden ({expected[0]}) does not match d3004's golden "
            f"({D3004_GOLDEN}) -- input/weight/bias fixtures have diverged."
        )

    weights_flat = [w for row in weight_rows for w in row]  # row-major, matches wr_addr = row*K + k

    _write_memh(input_vec, out_dir / "d3004n4_input.memh", 8)
    _write_memh(weights_flat, out_dir / "d3004n4_weights.memh", 8)
    _write_memh(bias_vals, out_dir / "d3004n4_bias.memh", 8)
    _write_memh(expected, out_dir / "d3004n4_expected.memh", 24)

    print("Generated d3004n4_input.memh, d3004n4_weights.memh, d3004n4_bias.memh, d3004n4_expected.memh")
    for row in range(N):
        print(f"  row {row}: expected (signed 24-bit) = {expected[row]}")


if __name__ == "__main__":
    main()
