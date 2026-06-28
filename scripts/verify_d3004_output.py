from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _read_memh_signed(path: Path, bits: int) -> list[int]:
    values: list[int] = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line:
            continue
        val = int(line, 16)
        if val >= (1 << (bits - 1)):
            val -= 1 << bits
        values.append(val)
    return values


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify D3004 actual vs expected memh outputs."
    )
    parser.add_argument(
        "--actual",
        default="tb/data/d3004_actual.memh",
        help="Path to actual output memh (default: tb/data/d3004_actual.memh).",
    )
    parser.add_argument(
        "--expected",
        default="tb/data/d3004_expected.memh",
        help="Path to expected output memh (default: tb/data/d3004_expected.memh).",
    )
    parser.add_argument(
        "--bits",
        type=int,
        default=24,
        help="Signed bit width for memh values (default: 24).",
    )
    args = parser.parse_args()

    actual_path = Path(args.actual)
    expected_path = Path(args.expected)

    if not actual_path.exists():
        print(f"Missing actual memh: {actual_path}", file=sys.stderr)
        return 2
    if not expected_path.exists():
        print(f"Missing expected memh: {expected_path}", file=sys.stderr)
        return 2

    actual_vals = _read_memh_signed(actual_path, args.bits)
    expected_vals = _read_memh_signed(expected_path, args.bits)

    if len(actual_vals) != len(expected_vals):
        print(
            "Length mismatch: "
            f"actual={len(actual_vals)} expected={len(expected_vals)}",
            file=sys.stderr,
        )
        return 2

    mismatches: list[tuple[int, int, int]] = []
    for idx, (act, exp) in enumerate(zip(actual_vals, expected_vals)):
        if act != exp:
            mismatches.append((idx, act, exp))

    if mismatches:
        first = mismatches[0]
        print(
            "FAIL: mismatches found. "
            f"first idx={first[0]} actual={first[1]} expected={first[2]}",
            file=sys.stderr,
        )
        return 1

    print(f"PASS: {len(actual_vals)} outputs match expected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
