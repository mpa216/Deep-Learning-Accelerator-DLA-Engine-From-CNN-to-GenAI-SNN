"""Read the float32 tensors out of a legacy-format PyTorch .ckpt without PyTorch.

`weights/mnist_gan_mlp/{G,D}--300.ckpt` are legacy (pre-zip) `torch.save` files: three
pickled headers, the pickled state_dict whose tensors are `persistent_id` references, a
pickled list of storage keys, and then the raw little-endian storage blocks in that key
order, each prefixed by an int64 element count.

Everything downstream of the trained model in this project consumes the *quantised* int8
copy in `weights_vh/mnist_gan_mlp/`, so the float originals were effectively unreadable
in any environment without PyTorch installed -- which is every environment this project
actually runs in.  That blocked the one measurement the precision study needs: how much
accuracy INT8 is giving up against the float model, and whether more bits would buy
anything.  This module unblocks it in ~60 lines of stdlib.

    from torch_ckpt import load_state_dict
    sd = load_state_dict("weights/mnist_gan_mlp/G--300.ckpt")   # {name: (shape, list)}

Only what these two checkpoints use is supported: float32 storages, contiguous tensors,
protocol-2 pickles.  It refuses anything else rather than guessing.
"""

from __future__ import annotations

import collections
import pickle
import struct
from pathlib import Path


class _Meta(pickle.Unpickler):
    """Resolves just enough of torch's pickle vocabulary to recover shapes and keys."""

    def find_class(self, module, name):
        if name == "_rebuild_tensor_v2":
            return lambda storage, off, size, stride, *r: {
                "storage": storage, "offset": off,
                "shape": tuple(size), "stride": tuple(stride)}
        if name == "OrderedDict":
            return collections.OrderedDict
        if name == "FloatStorage":
            return "float32"
        return lambda *a, **k: None

    def persistent_load(self, pid):
        # ('storage', <storage_type>, key, location, numel)
        return {"dtype": pid[1], "key": pid[2], "numel": pid[4]}


def load_state_dict(path: str | Path) -> dict[str, tuple[tuple, list]]:
    """Return {tensor_name: (shape, flat list of python floats)}."""
    path = Path(path)
    with path.open("rb") as f:
        for _ in range(3):                       # magic, protocol, sys_info
            _Meta(f).load()
        sd = _Meta(f).load()
        keys = _Meta(f).load()

        raw: dict[str, list[float]] = {}
        for key in keys:
            (numel,) = struct.unpack("<q", f.read(8))
            buf = f.read(numel * 4)
            if len(buf) != numel * 4:
                raise ValueError(f"{path.name}: truncated storage {key}")
            raw[key] = list(struct.unpack(f"<{numel}f", buf))

    out = {}
    for name, t in sd.items():
        if not isinstance(t, dict) or "storage" not in t:
            continue
        st = t["storage"]
        if st["dtype"] != "float32":
            raise ValueError(f"{name}: only float32 storages are supported")
        n = 1
        for d in t["shape"]:
            n *= d
        off = t["offset"]
        out[name] = (t["shape"], raw[st["key"]][off:off + n])
    return out


if __name__ == "__main__":
    import sys

    for p in sys.argv[1:] or ["weights/mnist_gan_mlp/G--300.ckpt"]:
        sd = load_state_dict(p)
        print(p)
        for k, (shape, vals) in sd.items():
            lo, hi = min(vals), max(vals)
            print(f"  {k:12s} {str(shape):14s} n={len(vals):7d}  "
                  f"range [{lo:+.6f}, {hi:+.6f}]")
