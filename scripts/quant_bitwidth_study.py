"""Numeric-format study for the G300 generator: INT4 / INT8 / INT16 / FP16 vs FP32.

Answers the reviewer question "why INT8 and not INT4/INT16/FP16?" with measured
numbers instead of an appeal to convention.  For each candidate format the FP32
generator checkpoint is re-quantized with *this project's own* scheme (per-tensor
symmetric scales, integer accumulation, the same requantize-and-clamp between
layers) and the rendered 28x28 image is compared against an FP64 reference render
of the same latent.  Error is reported in gray levels of 255, which is the unit a
reader can actually judge.

The FP32 masters are read straight from the PyTorch checkpoint.  torch is not
installed in the flow container, so the legacy (pre-zip) torch.save format is
unpickled directly -- it is a plain pickle stream followed by raw storage blobs.

Usage (from the repo root, inside the container):
    python3 scripts/quant_bitwidth_study.py
"""

from __future__ import annotations

import io
import pickle
import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CKPT = ROOT / "weights" / "mnist_gan_mlp" / "G--300.ckpt"
SAMPLES = ROOT / "tb" / "data" / "g300_samples"

# The three dense layers of the generator, in nn.Sequential order.
LAYERS = ["0", "2", "4"]

_DTYPES = {
    "FloatStorage": np.dtype("<f4"),
    "DoubleStorage": np.dtype("<f8"),
    "HalfStorage": np.dtype("<f2"),
    "LongStorage": np.dtype("<i8"),
    "IntStorage": np.dtype("<i4"),
}


class _StateDict(dict):
    """dict that can also carry torch's _metadata attribute."""


class _Storage:
    """Placeholder for one raw tensor storage; data is attached in pass 2."""

    def __init__(self, key: str, dtype: np.dtype):
        self.key = key
        self.dtype = dtype
        self.data: np.ndarray | None = None


class _Tensor:
    """Deferred tensor view: materialized once its storage has been read."""

    def __init__(self, storage: _Storage, offset: int, size, stride):
        self.storage = storage
        self.offset = offset
        self.size = tuple(size)
        self.stride = tuple(stride)

    def array(self) -> np.ndarray:
        flat = self.storage.data
        return np.lib.stride_tricks.as_strided(
            flat[self.offset:],
            shape=self.size,
            strides=tuple(s * flat.itemsize for s in self.stride),
        ).copy()


def load_legacy_torch(path: Path) -> dict[str, np.ndarray]:
    """Read a legacy-format torch.save file without torch installed."""
    storages: dict[str, _Storage] = {}

    def persistent_load(pid):
        # ('storage', storage_type, root_key, location, numel, view_metadata)
        tag, storage_type, root_key, _location, _numel = pid[:5]
        assert tag == "storage", tag
        return storages.setdefault(root_key, _Storage(root_key, storage_type))

    def rebuild_tensor(storage, offset, size, stride, *_rest):
        return _Tensor(storage, offset, size, stride)

    class Unpickler(pickle.Unpickler):
        def find_class(self, module, name):
            if name in _DTYPES:
                return _DTYPES[name]
            if name == "_rebuild_tensor_v2":
                return rebuild_tensor
            if name == "OrderedDict":
                # torch attaches a _metadata attribute via BUILD, which a bare
                # dict cannot carry -- a subclass can.
                return _StateDict
            return super().find_class(module, name)

        def persistent_load(self, pid):  # type: ignore[override]
            return persistent_load(pid)

    with path.open("rb") as fh:
        pickle.load(fh)  # magic number
        pickle.load(fh)  # protocol version
        pickle.load(fh)  # sys info
        state = Unpickler(fh).load()
        keys = pickle.load(fh)
        for key in keys:
            storage = storages[key]
            (numel,) = struct.unpack("<q", fh.read(8))
            raw = fh.read(numel * storage.dtype.itemsize)
            storage.data = np.frombuffer(raw, dtype=storage.dtype)

    return {name: t.array() for name, t in state.items() if isinstance(t, _Tensor)}


def load_latent(seed: int) -> np.ndarray:
    text = (SAMPLES / f"seed_{seed}" / f"g300_output{seed}_latent.txt").read_text()
    values = [float(line) for line in text.split() if line.strip()]
    assert len(values) == 64, len(values)
    return np.array(values, dtype=np.float64)


def to_pixels(out: np.ndarray) -> np.ndarray:
    """Generator output in [-1, 1] -> 0..255 gray levels, as the RTL does."""
    return np.clip(np.round((out + 1.0) * 255.0 / 2.0), 0, 255)


def forward_reference(w, b, z: np.ndarray) -> np.ndarray:
    """Exact FP64 render: the ground truth every format is scored against."""
    h = z.astype(np.float64)
    for i, name in enumerate(LAYERS):
        h = w[name] @ h + b[name]
        h = np.maximum(h, 0.0) if i < 2 else np.tanh(h)
    return to_pixels(h)


def q_symmetric(x: np.ndarray, bits: int):
    """Per-tensor symmetric quantization, this project's scheme."""
    qmax = (1 << (bits - 1)) - 1
    scale = np.max(np.abs(x)) / qmax
    if scale == 0:
        scale = 1.0
    return np.clip(np.round(x / scale), -qmax - 1, qmax).astype(np.int64), scale


def forward_int(w, b, z: np.ndarray, bits: int) -> np.ndarray:
    """Integer forward with per-tensor scales and exact integer accumulation.

    Mirrors the hardware: the array returns sum(Wq*xq) as an integer, and the
    rescale-add-bias-activate-requantize step happens around it.
    """
    qmax = (1 << (bits - 1)) - 1
    xq, sx = q_symmetric(z.astype(np.float64), bits)
    for i, name in enumerate(LAYERS):
        wq, sw = q_symmetric(w[name], bits)
        acc = wq @ xq                       # exact integer dot product
        real = acc.astype(np.float64) * (sw * sx) + b[name]
        if i < 2:
            real = np.maximum(real, 0.0)
            xq, sx = q_symmetric(real, bits)  # requantize for the next layer
        else:
            return to_pixels(np.tanh(real))
    raise AssertionError


def forward_fp16(w, b, z: np.ndarray) -> np.ndarray:
    """FP16 storage and FP16 products, accumulated in FP16 (a half-precision MAC)."""
    h = z.astype(np.float16)
    for i, name in enumerate(LAYERS):
        wh = w[name].astype(np.float16)
        acc = np.zeros(wh.shape[0], dtype=np.float16)
        for k in range(wh.shape[1]):
            acc = (acc + (wh[:, k] * h[k]).astype(np.float16)).astype(np.float16)
        h = (acc + b[name].astype(np.float16)).astype(np.float16)
        h = np.maximum(h, np.float16(0)) if i < 2 else np.tanh(h.astype(np.float32)).astype(np.float16)
    return to_pixels(h.astype(np.float64))


def accumulator_width(bits: int, depth: int = 256) -> int:
    """Bits needed to hold `depth` products of two `bits`-wide signed operands."""
    peak = depth * (1 << (2 * bits - 2))
    return int(np.ceil(np.log2(peak))) + 1


def main() -> None:
    state = load_legacy_torch(CKPT)
    w = {n: state[f"{n}.weight"].astype(np.float64) for n in LAYERS}
    b = {n: state[f"{n}.bias"].astype(np.float64) for n in LAYERS}
    n_weights = sum(w[n].size for n in LAYERS)
    print(f"generator weights: {n_weights:,} ({[w[n].shape for n in LAYERS]})")

    seeds = sorted(int(p.name.split("_")[1]) for p in SAMPLES.glob("seed_*"))
    latents = {s: load_latent(s) for s in seeds}
    refs = {s: forward_reference(w, b, latents[s]) for s in seeds}
    print(f"reference renders: {len(seeds)} latents (seeds {seeds[0]}-{seeds[-1]})\n")

    formats = [("INT4", 4), ("INT8", 8), ("INT16", 16)]
    print(f"{'format':>7} {'mean err':>9} {'max err':>8} {'RMSE':>7} "
          f"{'weights':>9} {'acc bits':>9}")
    rows = []
    for label, bits in formats:
        errs = []
        for s in seeds:
            errs.append(np.abs(forward_int(w, b, latents[s], bits) - refs[s]))
        errs = np.concatenate(errs)
        row = (label, errs.mean(), errs.max(), np.sqrt((errs ** 2).mean()),
               n_weights * bits / 8 / 1024, accumulator_width(bits))
        rows.append(row)
        print(f"{row[0]:>7} {row[1]:9.2f} {row[2]:8.0f} {row[3]:7.2f} "
              f"{row[4]:8.1f}K {row[5]:9d}")

    errs = np.concatenate([np.abs(forward_fp16(w, b, latents[s]) - refs[s]) for s in seeds])
    print(f"{'FP16':>7} {errs.mean():9.2f} {errs.max():8.0f} "
          f"{np.sqrt((errs ** 2).mean()):7.2f} {n_weights * 2 / 1024:8.1f}K {'16 (fp)':>9}")

    # Serial-link cost of the weight stream, at the documented SCLK <= clk/8.
    print("\nweight-stream time at SCLK = 3.125 MHz (clk/8), 20 edges per byte:")
    for label, bits in formats:
        nbytes = n_weights * bits / 8
        print(f"  {label:>5}: {nbytes/1024:7.1f} KiB -> {nbytes * 20 / 3.125e6:6.3f} s")


if __name__ == "__main__":
    main()
