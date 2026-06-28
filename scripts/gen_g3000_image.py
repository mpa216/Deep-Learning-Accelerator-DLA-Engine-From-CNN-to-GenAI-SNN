from __future__ import annotations

import argparse
import json
import math
import random
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


def _to_hex_signed(value: int, bits: int) -> str:
    mask = (1 << bits) - 1
    if value < 0:
        value = (1 << bits) + value
    return f"{value & mask:0{bits // 4}x}"


def _write_memh(values: list[int], path: Path, bits: int) -> None:
    lines = [_to_hex_signed(v, bits) for v in values]
    path.write_text("\n".join(lines) + "\n")


def _load_scales(manifest_path: Path) -> dict[str, float]:
    manifest = json.loads(manifest_path.read_text())
    scales: dict[str, float] = {}
    for name, info in manifest.get("tensors", {}).items():
        scales[name] = float(info["scale"])
    return scales


def _reshape(values: list[float], rows: int, cols: int) -> list[list[float]]:
    return [values[r * cols:(r + 1) * cols] for r in range(rows)]


def _matvec(weights: list[list[float]], bias: list[float], x: list[float]) -> list[float]:
    out: list[float] = []
    for r, row in enumerate(weights):
        acc = bias[r]
        for c, w in enumerate(row):
            acc += w * x[c]
        out.append(acc)
    return out


def _relu(x: list[float]) -> list[float]:
    return [v if v > 0.0 else 0.0 for v in x]


def _tanh(x: list[float]) -> list[float]:
    return [math.tanh(v) for v in x]


def _gen_latent(seed: int, dim: int) -> list[float]:
    rng = random.Random(seed)
    return [rng.gauss(0.0, 1.0) for _ in range(dim)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a G300 sample image from int8 weights.")
    parser.add_argument("--seed", type=int, default=0, help="Random seed for latent vector")
    parser.add_argument("--out-dir", default="tb/data", help="Output directory relative to repo root")
    parser.add_argument("--out-prefix", default="g300_output", help="Output file prefix")
    args = parser.parse_args()

    root_dir = Path(__file__).resolve().parents[1]
    weights_dir = root_dir / "weights_vh" / "mnist_gan_mlp"
    out_dir = root_dir / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    scales = _load_scales(weights_dir / "weights_manifest.json")

    def load_weight(name: str, rows: int, cols: int) -> list[list[float]]:
        raw = _read_memh_int8(weights_dir / f"{name}.memh")
        expected = rows * cols
        if len(raw) != expected:
            raise ValueError(f"{name}: expected {expected} values, got {len(raw)}")
        scale = scales[name]
        deq = [v * scale for v in raw]
        return _reshape(deq, rows, cols)

    def load_bias(name: str, length: int) -> list[float]:
        raw = _read_memh_int8(weights_dir / f"{name}.memh")
        if len(raw) != length:
            raise ValueError(f"{name}: expected {length} values, got {len(raw)}")
        scale = scales[name]
        return [v * scale for v in raw]

    w0 = load_weight("G300_0_weight", 256, 64)
    b0 = load_bias("G300_0_bias", 256)
    w2 = load_weight("G300_2_weight", 256, 256)
    b2 = load_bias("G300_2_bias", 256)
    w4 = load_weight("G300_4_weight", 784, 256)
    b4 = load_bias("G300_4_bias", 784)

    z = _gen_latent(args.seed, 64)
    h0 = _relu(_matvec(w0, b0, z))
    h2 = _relu(_matvec(w2, b2, h0))
    out = _tanh(_matvec(w4, b4, h2))

    pixels: list[int] = []
    for v in out:
        p = int(round((v + 1.0) * 127.5))
        if p < 0:
            p = 0
        if p > 255:
            p = 255
        pixels.append(p)

    out_base = f"{args.out_prefix}{args.seed}"
    signed_pixels = [p - 128 for p in pixels]
    _write_memh(signed_pixels, out_dir / f"{out_base}.memh", 8)

    (out_dir / f"{out_base}_latent.txt").write_text("\n".join(f"{v:.6f}" for v in z) + "\n")
    (out_dir / f"{out_base}_pixels.txt").write_text("\n".join(str(p) for p in pixels) + "\n")

    print(f"Wrote {out_base}.memh and {out_base}_pixels.txt")


if __name__ == "__main__":
    main()
