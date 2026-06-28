import argparse
import json
from pathlib import Path

import torch


def _load_state(path: Path):
    obj = torch.load(path, map_location="cpu")
    if isinstance(obj, dict) and "state_dict" in obj:
        return obj["state_dict"]
    return obj


def _quantize_int8(tensor):
    max_abs = float(tensor.abs().max().item())
    if max_abs == 0.0:
        scale = 1.0
    else:
        scale = max_abs / 127.0
    q = (tensor / scale).round().clamp(-128, 127).to(torch.int8)
    return q, scale


def _write_memh(values, path: Path, width_bits: int):
    digits = (width_bits + 3) // 4
    with path.open("w", encoding="utf-8") as f:
        for v in values:
            if v < 0:
                v = (1 << width_bits) + v
            f.write(f"{v:0{digits}x}\n")


def _write_vh(name: str, length: int, width_bits: int, memh_name: str, path: Path):
    guard = f"WEIGHTS_{name.upper()}_VH"
    with path.open("w", encoding="utf-8") as f:
        f.write(f"`ifndef {guard}\n")
        f.write(f"`define {guard}\n")
        f.write(f"localparam integer {name}_LEN = {length};\n")
        f.write(f"reg signed [{width_bits-1}:0] {name} [0:{length-1}];\n")
        f.write(f"initial $readmemh(\"{memh_name}\", {name});\n")
        f.write("`endif\n")


def main():
    parser = argparse.ArgumentParser(description="Convert PyTorch .ckpt to .vh/.memh (int8).")
    parser.add_argument("--ckpt", required=True, help="Path to .ckpt file")
    parser.add_argument("--out", required=True, help="Output directory for .vh/.memh")
    parser.add_argument("--prefix", default="", help="Optional filename prefix")
    args = parser.parse_args()

    ckpt_path = Path(args.ckpt)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    state = _load_state(ckpt_path)
    if not isinstance(state, dict):
        raise ValueError("Unsupported checkpoint format: expected dict/state_dict")

    manifest_path = out_dir / "weights_manifest.json"
    if manifest_path.exists():
        with manifest_path.open("r", encoding="utf-8") as f:
            manifest = json.load(f)
    else:
        manifest = {
            "sources": [],
            "tensors": {}
        }

    if "sources" not in manifest:
        manifest["sources"] = [manifest.pop("source", "")]
    if str(ckpt_path) not in manifest["sources"]:
        manifest["sources"].append(str(ckpt_path))

    for name, tensor in state.items():
        q, scale = _quantize_int8(tensor.cpu())
        flat = q.reshape(-1).tolist()
        safe_name = name.replace(".", "_").replace("/", "_")
        base = f"{args.prefix}{safe_name}" if args.prefix else safe_name

        memh_path = out_dir / f"{base}.memh"
        vh_path = out_dir / f"{base}.vh"

        _write_memh(flat, memh_path, 8)
        _write_vh(base, len(flat), 8, memh_path.name, vh_path)

        manifest_key = base
        manifest["tensors"][manifest_key] = {
            "original_name": name,
            "shape": list(tensor.shape),
            "scale": scale,
            "memh": memh_path.name,
            "vh": vh_path.name,
            "dtype": "int8"
        }

    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


if __name__ == "__main__":
    main()
