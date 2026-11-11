"""hooks.py (TB2): -3 dB frequencies and gains from the wrdata file of the AC run, CMRR and PSRR from the two single-frequency runs.

Metrics (names are the contract with spec/gates.yaml TB2):
  a1                    stage-1 differential gain (oa - ob per unit differential input), low-frequency value (1 MHz)
  a2, a3                stage-2 (d2a - d2b per oa - ob) and stage-3 (d3 per d2a - d2b) low-frequency gains, hysteresis feedback scaled to zero
  a_chain               d3 per unit differential input
  f3db1_hz, f3db2_hz, f3db3_hz   -3 dB frequency of each stage transfer function (3 GHz = not reached in the sweep)
  f3db_chain_hz         -3 dB frequency of d3 per unit differential input
  f3db_stage_over_dr    min(f3db1, f3db2, f3db3) / data rate
  cmrr_db               20 log10( (A1/2) / |oa per unit common-mode input| ) at 1 MHz (half-circuit definition: the nominal netlist is symmetric, so the
                        differential common-mode conversion is zero by construction; Monte Carlo is where it would show)
  psrr_db               20 log10( (A1/2) / |oa per unit supply ripple| ) at 1 MHz, inputs quiet, common mode fixed
"""
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "harness"))
sys.path.insert(0, os.path.join(HERE, ".."))
from harness import analysis as A  # noqa: E402

FMAX = 3.0e9


def f3db(f, g):
    """-3 dB frequency of magnitude g(f) relative to its first point (log-interpolated); FMAX if never reached."""
    g = np.asarray(g, float)
    thr = g[0] / math.sqrt(2.0)
    below = np.nonzero(g < thr)[0]
    if len(below) == 0:
        return FMAX
    k = below[0]
    if k == 0:
        return float(f[0])
    f0, f1, g0, g1 = f[k - 1], f[k], g[k - 1], g[k]
    return float(f0 * math.exp(math.log(f1 / f0) * (g0 - thr) / (g0 - g1)))


def post_tb2(ctx):
    m = ctx["measures"]
    f, (g1, g2, g3) = A.load_wrdata(os.path.join(ctx["run_dir"], "ac_dm.txt"), nvec=3)
    eps = 1e-30
    r2 = g2 / np.maximum(g1, eps)
    r3 = g3 / np.maximum(g2, eps)
    out = dict(a1=g1[0], a2=r2[0], a3=r3[0], a_chain=g3[0],
               f3db1_hz=f3db(f, g1), f3db2_hz=f3db(f, r2), f3db3_hz=f3db(f, r3), f3db_chain_hz=f3db(f, g3))
    out["f3db_stage_over_dr"] = min(out["f3db1_hz"], out["f3db2_hz"], out["f3db3_hz"]) / float(ctx["vars"]["dr"])
    a_se = g1[0] / 2.0
    out["cmrr_db"] = 20 * math.log10(a_se / max(m["acm_oa"], eps))
    out["psrr_db"] = 20 * math.log10(a_se / max(m["aps_oa"], eps))
    out["f_first_hz"] = f[0]
    return out
