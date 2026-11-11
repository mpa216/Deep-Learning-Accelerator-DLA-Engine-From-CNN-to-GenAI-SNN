"""hooks.py (TB3 trip): trip points and hysteresis from the DC-sweep wrdata files.

Metrics (names are the contract with spec/gates.yaml TB3_trip):
  vth_plus_v, vth_minus_v   input difference (VP - VN at the pins) at which the output crosses VDD/2 upward / downward
  vh_v                      hysteresis VTH+ - VTH-
  off_v                     centre of the window (VTH+ + VTH-)/2
  n_up, n_dn                number of upward / downward output crossings in the whole sweep (1 and 1 = clean; more = chatter)
  vh_v30, vh_v36, off_v30, off_v36   the same sweep with the final supply 3.0 V / 3.6 V
  dvh_dvdd, dvtrip_dvdd     (vh36 - vh30)/0.6 and (off36 - off30)/0.6   [V per V]  (reported)
The sweep starts with the supply ramp, during which VID rests at its start value; the output is not valid there (supply below ~1 V),
so crossings are only taken where the supply has reached its final value.
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from harness import analysis as A  # noqa: E402


def one_loop(path):
    s, (vid, out, vdd) = A.load_wrdata(path, nvec=3)
    final = vdd[-1]
    ok = vdd >= final - 1e-6
    k0 = int(np.argmax(ok))
    # a few points of margin so that the supply-ramp end is excluded from the crossing search
    s, vid, out = s[k0 + 2:], vid[k0 + 2:], out[k0 + 2:]
    return A.hysteresis(s, vid, out, final / 2.0)


def post_tb3(ctx):
    d = ctx["run_dir"]
    nom = one_loop(os.path.join(d, "trip_nom.txt"))
    lo = one_loop(os.path.join(d, "trip_v30.txt"))
    hi = one_loop(os.path.join(d, "trip_v36.txt"))
    out = dict(vth_plus_v=nom["vth_plus"], vth_minus_v=nom["vth_minus"], vh_v=nom["vh"], off_v=nom["offset"],
               n_up=nom["n_up"], n_dn=nom["n_dn"],
               vh_v30=lo["vh"], vh_v36=hi["vh"], off_v30=lo["offset"], off_v36=hi["offset"])
    out["dvh_dvdd"] = (hi["vh"] - lo["vh"]) / 0.6
    out["dvtrip_dvdd"] = (hi["offset"] - lo["offset"]) / 0.6
    return out
