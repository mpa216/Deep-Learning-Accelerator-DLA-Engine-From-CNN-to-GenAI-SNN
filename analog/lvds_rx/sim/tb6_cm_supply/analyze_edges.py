"""analyze_edges.py <run_dir>: per-edge delay (disturbed - reference output) of a TB6 case-0 run, listed against the nearest CM step.
Diagnostic only (not part of the gate)."""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import lib_tb as L  # noqa: E402
import hooks as H  # noqa: E402
from harness import analysis as A  # noqa: E402

rd = sys.argv[1]
vdd = float(sys.argv[2])
t, (vo_d, vo_r, vm, vs, vp, vn) = A.load_wrdata(os.path.join(rd, "tb6.txt"), nvec=6)
b = H.bits()
th = vdd / 2
td, sd = L.crossings_with_sense(t, vo_d, th, L.TD0 - 5e-9)
tr_, sr = L.crossings_with_sense(t, vo_r, th, L.TD0 - 5e-9)
pairs, _, _ = L.match_edges(tr_, sr, td, sd, H.UI / 2)
tog = np.array([x[0] - H.TR / 2.0 for x in L.toggle_times(b, H.UI, H.TR)])
st = H.steps()
dl = np.array([p[1] - p[0] for p in pairs])
far = np.array([all(abs(te - ts) > 3 * H.UI for (ts, _) in st) for te in tog])
print("static delay delta (far edges) median %.0f ps, range %.0f..%.0f" % (np.median(dl[far]) * 1e12, dl[far].min() * 1e12, dl[far].max() * 1e12))
for i, te in enumerate(tog):
    nearest = min(st, key=lambda s: abs(te - s[0]))
    dtn = (te - nearest[0]) * 1e9
    if abs(dtn) < 25:
        print("edge %2d  t=%7.1f ns  %s step at %+6.1f ns from step start  delta_delay %+7.0f ps" % (i, te * 1e9, nearest[1], dtn, dl[i] * 1e12))
