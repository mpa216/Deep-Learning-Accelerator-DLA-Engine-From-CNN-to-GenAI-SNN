"""hooks.py (TB5 eye, also used by TB12): PRBS7 stimulus through the input network, BER at mid-UI, toggle count, eye metrics.

Stimulus: 8 lead-in bits + 127 compared bits of PRBS7 (one full period), UI = 1/rate; the driver emf per side is vic +- vid for a 1 / 0
(= +-vid across the 100 ohm termination, 2 x 50 ohm source), edges are linear ramps of `tr` (named edge times of the spec: 1 ns at VID 350 mV and
2 ns at VID 100 mV at 100 Mb/s; half of that at 200 Mb/s).  Pin levels in the grid come from `vic` (moved inward by vic_eff() where VID would push a pin outside 0..2.4 V); `vid` is a grid value (TB5) or follows the rate (TB12:
0.1 V at 100 Mb/s, 0.35 V at 200 Mb/s, the two conditions the spec gives eye limits for).

Metrics (contract with spec/gates.yaml TB5 / TB12):
  ber_errors     bits (of the 127 compared) whose output level at the delayed mid-UI sampling instant differs from the sent bit
  toggle_diff    output crossings of VDD/2 after data start minus the number of input toggles (0 = clean)
  eye_open_ui    horizontal opening = 1 - (peak-to-peak crossing spread)/UI of the output at VDD/2 (all edges, so ISI and DCD count)
  dcd_ui         |mean rising crossing phase - mean falling crossing phase| in UI (reported)
  delay_s        median delay from the driver's nominal edge midpoint to the output crossing (includes the network)
  v_open_v       vertical opening at the eye centre
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from harness import analysis as A  # noqa: E402
from harness import stimulus as S  # noqa: E402

LEAD = 8               # lead-in bits (not compared)
NCMP = 127             # compared bits = one PRBS7 period
TD0 = 100e-9           # first bit boundary
T_RAMP = 50e-9         # supply (and common-mode) ramp
PKG = [(1e-9, 0.5e-12), (1e-9, 1.5e-12), (5e-9, 0.5e-12), (5e-9, 1.5e-12)]   # TB12 grid index -> (L, C)


def settings(v):
    rate = float(v["rate"])
    vid = float(v["vid"]) if "vid" in v else (0.1 if rate < 150e6 else 0.35)
    tr100 = 2.0e-9 if vid < 0.2 else 1.0e-9
    tr = tr100 * (100e6 / rate) if rate > 150e6 else tr100
    lpk, cpk = (3e-9, 0.7e-12)
    if "pkg" in v:
        lpk, cpk = PKG[int(v["pkg"])]
    return rate, vid, tr, lpk, cpk


def vic_eff(vic, vid):
    """Keep both pins inside the TIA/EIA-644 input range 0..2.4 V: VIC +- VID/2 must lie in [0, 2.4].  For VID = 100 mV this is the whole spec range
    0.05..2.35 V (unchanged); for VID = 350 mV the lowest / highest usable common mode is 0.175 / 2.225 V.  (At VIC = 0.05 V, VID = 350 mV the N pin
    would sit at -0.125 V and ngspice failed to converge at ss/125C: `Timestep too small` at 70 % of the supply ramp.)"""
    return min(max(float(vic), vid / 2.0), 2.4 - vid / 2.0)


def bits_of():
    return S.prbs7(LEAD + NCMP)


def prep_eye(ctx):
    v = ctx["vars"]
    rate, vid, tr, lpk, cpk = settings(v)
    ui = 1.0 / rate
    vic = vic_eff(v["vic"], vid)
    bits = bits_of()
    # emf levels per side: P = vic +- vid, N = vic -+ vid.  Both ramp up from 0 with the supply, then follow the data.
    lp = lambda b: vic + (vid if b else -vid)
    ln = lambda b: vic + (-vid if b else vid)
    tp, vp = [0.0, T_RAMP], [0.0, lp(bits[0])]
    tn, vn = [0.0, T_RAMP], [0.0, ln(bits[0])]
    for k in range(1, len(bits)):
        if bits[k] != bits[k - 1]:
            te = TD0 + k * ui
            tp += [te, te + tr]
            vp += [lp(bits[k - 1]), lp(bits[k])]
            tn += [te, te + tr]
            vn += [ln(bits[k - 1]), ln(bits[k])]
    tend = TD0 + len(bits) * ui + 3 * ui
    tp.append(tend); vp.append(vp[-1])
    tn.append(tend); vn.append(vn[-1])
    text = ("Vsp srcp 0 PWL(\n+ %s)\nVsn srcn 0 PWL(\n+ %s)\n" % (S.pwl_string(tp, vp), S.pwl_string(tn, vn)))
    return {"stim.inc": text, "pkg.inc": ".param lpk=%.4e cpk=%.4e\n" % (lpk, cpk)}


def tstop_of(v):
    rate = float(v["rate"])
    return TD0 + (LEAD + NCMP + 3) / rate


def post_eye(ctx):
    v = ctx["vars"]
    rate, vid, tr, lpk, cpk = settings(v)
    ui = 1.0 / rate
    vdd = ctx["corner"].vdd
    bits = bits_of()
    t, (vo, vp, vn) = A.load_wrdata(os.path.join(ctx["run_dir"], "eye.txt"), nvec=3)
    nan = float("nan")
    skip = 4
    # toggles
    t_lo = TD0 - 5e-9
    xo = A.crossings(t, vo, vdd / 2.0, "both")
    n_out = int(np.sum(xo >= t_lo))
    n_in = int(sum(1 for k in range(1, len(bits)) if bits[k] != bits[k - 1]))
    # delay: nominal driver edge midpoint -> first output crossing of the same sense
    ro = A.crossings(t, vo, vdd / 2.0, "rising")
    fo = A.crossings(t, vo, vdd / 2.0, "falling")
    dl = []
    for k in range(skip, len(bits)):
        if bits[k] == bits[k - 1]:
            continue
        te = TD0 + k * ui + tr / 2.0
        arr = ro if bits[k] else fo
        a = arr[arr >= te]
        if len(a) and a[0] - te < 2.0 * ui:
            dl.append(a[0] - te)
    d_med = float(np.median(dl)) if dl else nan
    # BER at the delayed mid-UI
    err = 0
    if np.isfinite(d_med):
        for k in range(skip, skip + NCMP):
            ts = TD0 + k * ui + tr / 2.0 + d_med + ui / 2.0
            lvl = np.interp(ts, t, vo) > vdd / 2.0
            err += int(lvl != bool(bits[k]))
    else:
        err = NCMP
    m = A.eye_metrics(t, vo, ui, vdd / 2.0, t_skip_ui=skip, t0=TD0)
    out = {"ber_errors": err, "toggle_diff": n_out - n_in, "n_out_toggles": n_out, "n_in_toggles": n_in,
           "eye_open_ui": m["h_open_ui"], "dcd_ui": m["dcd_ui"], "jitter_pp_ps": m["jitter_pp"] * 1e12, "v_open_v": m["v_open"],
           "delay_s": d_med, "vid_set_v": vid, "tr_s": tr, "vic_eff_v": vic_eff(v["vic"], vid)}
    vpin = vp - vn
    sel = t > TD0 + skip * ui
    out["vid_pin_pp_v"] = float(vpin[sel].max() - vpin[sel].min())
    if float(v.get("vic", 0)) == 1.2:
        pl = os.path.join(ctx["run_dir"], "..", "..", "plots")
        os.makedirs(pl, exist_ok=True)
        tag = "%s_vid%g_%gMbps" % (ctx["corner"].name, vid, rate / 1e6)
        if "pkg" in v:
            tag += "_pkg%d" % int(v["pkg"])
        try:
            A.plot_eye(t, vo, ui, os.path.join(pl, "eye_%s.png" % tag), threshold=vdd / 2.0, t_skip_ui=skip, t0=TD0,
                       title="%s  open %.2f UI  err %d" % (tag, m["h_open_ui"], err), metrics=m)
        except Exception as e:  # a missing PNG never fails a run
            out["plot_error"] = 1.0
    return out
