"""hooks.py (TB3 offset): input-referred offset = VID at which d2a - d2b crosses 0 during the rising VID sweep (hysteresis disabled).
The output VDD/2 crossing is reported as vos_out_v (biased, see tb3_off.spice header).

Metrics (contract with spec/gates.yaml TB3_off):
  vos_v      input-referred offset [V] (NaN -> the run FAILS: no crossing means the offset is outside +-w or the stage is stuck)
  n_cross    number of VDD/2 crossings of the output in the sweep (1 = clean)
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from harness import analysis as A  # noqa: E402


def post_tb3off(ctx):
    s, (vid, out, vdd, d2d) = A.load_wrdata(os.path.join(ctx["run_dir"], "off.txt"), nvec=4)
    final = vdd[-1]
    k0 = int(np.argmax(vdd >= final - 1e-6))
    s, vid, out, d2d = s[k0 + 2:], vid[k0 + 2:], out[k0 + 2:], d2d[k0 + 2:]
    xs = A.crossings(s, out, final / 2.0, "both")
    vos_out = float(np.interp(xs[0], s, vid)) if len(xs) else float("nan")
    x2 = A.crossings(s, d2d, 0.0, "both")
    vos = float(np.interp(x2[0], s, vid)) if len(x2) else float("nan")
    return {"vos_v": vos, "vos_out_v": vos_out, "n_cross": len(x2), "n_cross_out": len(xs), "vid_end_v": float(vid[-1])}
