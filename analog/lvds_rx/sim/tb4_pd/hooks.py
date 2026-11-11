"""hooks.py (TB4 propagation delay): stimulus writer and delay / skew / edge / DCD extraction.

Metrics (names are the contract with spec/gates.yaml TB4 / TB4b):
  tpd_s         max(mean tPLH, mean tPHL) of phase A (fast edges, tr = 0.4 ns), from the 50 % point of the input edge (at the pins) to VDD/2 at the output
  tplh_s, tphl_s, skew_s      the two means and |tPLH - tPHL| (phase A)
  edge_10_90_s  10-90 % output transition time, the larger of the rising / falling means (phase A)
  dcd_ui        |tPLH - tPHL| / UI in phase B (the NAMED edge time: 1 ns at VID 350 mV, 2 ns at VID 100 mV): for a 1010 pattern the duty-cycle
                distortion |t_high - t_low|/2 equals |tPLH - tPHL|
  tpd_b_s, dcd_a_ui    phase B delay and phase A DCD (reported)
  n_missed      input edges without an output edge (any non-zero count makes the delays NaN: the run FAILS)
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from harness import analysis as A  # noqa: E402

UI = 10e-9
NEDGE = 12             # edges per phase
TA0 = 150e-9           # first edge of phase A
TB0 = 310e-9           # first edge of phase B
TR_A = 0.4e-9
SKIP = 2               # edges skipped at the start of each phase
OFFSET_VID100 = 0.010  # input-offset source at VID = 100 mV (spec timing.vid100_offset_source_v)


def tr_named(vid):
    return 1.0e-9 if float(vid) > 0.2 else 2.0e-9


def vic_shift(vic, vid):
    """Move of the common mode that keeps both pins inside 0..2.4 V (TIA/EIA-644 input range): VIC +- VID/2 within [0, 2.4].  Zero for VID <= 0.1 V and
    for every VIC in the spec range 0.05..2.35 V at VID = 100 mV; at VID = 350 mV the common mode is held to 0.175..2.225 V."""
    return min(max(float(vic), vid / 2.0), 2.4 - vid / 2.0) - float(vic)


def vid_offset(vid):
    return OFFSET_VID100 if float(vid) < 0.2 else 0.0


def edges(t0, tr, ui, n, hi, lo):
    """PWL (t, v) of the differential level: idle low, edge k starts at t0 + k*ui (even k rises, odd falls)."""
    pts = []
    cur = lo
    for k in range(n):
        te = t0 + k * ui
        new = hi if k % 2 == 0 else lo
        pts += [(te, cur), (te + tr, new)]
        cur = new
    return pts


def prep_tb4(ctx):
    vid = float(ctx["vars"]["vid"])
    off = vid_offset(vid)
    hi, lo = vid + off, -vid + off
    sh = vic_shift(ctx["vars"]["vic"], vid)
    pts = [(0.0, 0.0), (50e-9, lo)] + edges(TA0, TR_A, UI, NEDGE, hi, lo) + edges(TB0, tr_named(vid), UI, NEDGE, hi, lo)
    ts = [p[0] for p in pts]
    assert all(b > a for a, b in zip(ts, ts[1:])), "PWL times must increase"

    def pwl(sign):
        body = " ".join("%.6e %.6f" % (t, (sh if t > 0 else 0.0) + sign * v / 2.0) for t, v in pts)
        return body

    text = "Vp0 rx0_p cm PWL(%s)\nVn0 rx0_n cm PWL(%s)\n" % (pwl(+1), pwl(-1))
    return {"stim.inc": text}


def _phase(t, vo, vi, vdd, off, t0, tr, n):
    lo_t = t0 + SKIP * UI - 2e-9
    hi_t = t0 + n * UI + 8e-9
    m = (t >= lo_t) & (t <= hi_t)
    d = A.prop_delays(t[m], vi[m], vo[m], off, vdd / 2.0)
    rise = A.slew_times(t[m], vo[m], 0.1 * vdd, 0.9 * vdd, "rising")
    fall = A.slew_times(t[m], vo[m], 0.1 * vdd, 0.9 * vdd, "falling")
    return d, rise, fall


def post_tb4(ctx):
    vid = float(ctx["vars"]["vid"])
    vdd = ctx["corner"].vdd
    off = vid_offset(vid)
    t, (vo, vp, vn) = A.load_wrdata(os.path.join(ctx["run_dir"], "tb4.txt"), nvec=3)
    vi = vp - vn
    nan = float("nan")
    da, ra, fa = _phase(t, vo, vi, vdd, off, TA0, TR_A, NEDGE)
    db, rb, fb = _phase(t, vo, vi, vdd, off, TB0, tr_named(vid), NEDGE)
    missed = da["n_missed"] + db["n_missed"] + (NEDGE - SKIP - len(da["tplh"]) - len(da["tphl"])) * 0
    ok = missed == 0 and len(da["tplh"]) >= 3 and len(da["tphl"]) >= 3 and len(db["tplh"]) >= 3 and len(db["tphl"]) >= 3
    out = {"n_missed": missed, "n_edges_a": len(da["tplh"]) + len(da["tphl"]), "n_edges_b": len(db["tplh"]) + len(db["tphl"])}
    if not ok:
        out.update(tpd_s=nan, tplh_s=nan, tphl_s=nan, skew_s=nan, edge_10_90_s=nan, dcd_ui=nan, tpd_b_s=nan, dcd_a_ui=nan)
        return out
    out.update(tplh_s=da["tplh_mean"], tphl_s=da["tphl_mean"], tpd_s=max(da["tplh_mean"], da["tphl_mean"]), skew_s=da["skew"],
               edge_10_90_s=max(float(ra.mean()) if len(ra) else nan, float(fa.mean()) if len(fa) else nan),
               dcd_ui=db["skew"] / UI, dcd_a_ui=da["skew"] / UI, tpd_b_s=max(db["tplh_mean"], db["tphl_mean"]),
               vout_hi_v=float(vo[(t > TB0 + 2 * UI)].max()), vout_lo_v=float(vo[(t > TB0 + 2 * UI)].min()))
    return out
