"""hooks.py (TB3_hmc): hysteresis spread under device mismatch, plus the functional check at VID = +-100 mV.

Same DC-sweep deck as TB3_trip (PLAN_V2 finding C5: the DC method is also the one used inside Monte Carlo; sweep 0 = up first), run with mismatch at the two extreme
corners.  Metrics (contract with spec/gates.yaml TB3_hmc):
  vh_v       hysteresis V_TH+ - V_TH- of the run (nominal-supply sweep)
  ok_pm100   1 if every sample of the sweep with VID within 2 mV of +100 mV has the output above 0.9 VDD on the way up AND every sample within 2 mV of -100 mV has it
             below 0.1 VDD on the way down (the output holds the right state at the minimum LVDS input level whatever the random offset and hysteresis)
  vth_plus_v, vth_minus_v   the trip points (reported); both must lie inside +-100 mV for ok_pm100 = 1
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
import importlib.util  # noqa: E402

sys.path.insert(0, os.path.join(HERE, ".."))
from harness import analysis as A  # noqa: E402

_sp = importlib.util.spec_from_file_location("tb3_trip_hooks", os.path.join(HERE, "..", "tb3_trip", "hooks.py"))
T = importlib.util.module_from_spec(_sp)
_sp.loader.exec_module(T)


def post(ctx):
    d = ctx["run_dir"]
    nom = T.one_loop(os.path.join(d, "trip_nom.txt"))
    s, (vid, out, vdd) = A.load_wrdata(os.path.join(d, "trip_nom.txt"), nvec=3)
    final = vdd[-1]
    k0 = int(np.argmax(vdd >= final - 1e-6)) + 2
    vid, out = vid[k0:], out[k0:]
    # the sweep goes from one extreme to the other and back: the first half is the first leg, the second half the way back
    up_first = vid[0] < 0
    imid = int(np.argmax(vid) if up_first else np.argmin(vid))
    hi_leg = slice(0, imid + 1) if up_first else slice(imid, len(vid))
    lo_leg = slice(imid, len(vid)) if up_first else slice(0, imid + 1)
    hi_sel = np.abs(vid[hi_leg] - 0.1) < 2e-3
    lo_sel = np.abs(vid[lo_leg] + 0.1) < 2e-3
    ok_hi = bool(hi_sel.any() and np.all(out[hi_leg][hi_sel] > 0.9 * final))
    ok_lo = bool(lo_sel.any() and np.all(out[lo_leg][lo_sel] < 0.1 * final))
    return {"vh_v": nom["vh"], "ok_pm100": float(ok_hi and ok_lo), "vth_plus_v": nom["vth_plus"], "vth_minus_v": nom["vth_minus"],
            "off_v": nom["offset"], "n_up": nom["n_up"], "n_dn": nom["n_dn"]}
