"""hooks.py (TB10 three lanes): lane-to-lane skew and crosstalk of the full lvds_rx_x3 driven with realistic patterns.

Lanes: 0 = CLK (1010... at 100 Mb/s, i.e. a 50 MHz clock), 1 = D0 (PRBS7), 2 = D1 (PRBS7 delayed by 41 bits); VID 100 mV, tr 2 ns, VIC 1.2 V, full input network per
lane.  Every macro copy has its own supply with 1 ohm + 2 nH per rail (shared by the three lanes of that copy: this is the crosstalk path besides the bias).
Copies:
  a        nominal, all three lanes active                        -> skew_s
  b0 b1 b2 nominal, only lane k active, the others held at VIC     -> reference for the crosstalk of lane k (per-edge difference a_k - b_k)
  m0..m3   (grid mc3s = 1 only) like a, but with device mismatch (each lane draws its own mismatch)  -> 12 lane samples of the delay
Metrics (contract with spec/gates.yaml TB10):
  skew_s           max - min over the three lanes of the median propagation delay (nominal copy a)
  xtalk_jitter_ui  largest over lanes of the peak-to-peak spread of (t_out in a - t_out in b_k) over all edges, in UI
  skew_3sigma_s    (mc3s = 1) 3 * sqrt(2) * pooled sigma of the lane delays over the mismatch copies, lane-pattern means removed (dof = 9); the lane-to-lane
                   difference of two independent lanes has sigma sqrt(2)*sigma.  skew_3sigma_ucl_s = same with the 95 % chi-square upper confidence factor.
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import lib_tb as L  # noqa: E402
from harness import analysis as A  # noqa: E402

UI = 10e-9
NBIT = 70
VID, TR, VIC = 0.1, 2.0e-9, 1.2
RSUP, LSUP = 1.0, 2e-9
NMC = 4
SEED = 20261113
CHI2_95_LOW_9 = 3.325     # chi-square 5 % point, 9 dof


def lane_bits():
    b1 = L.S.prbs7(NBIT + 41)
    return [[(k + 1) % 2 for k in range(NBIT)], b1[:NBIT], b1[41:41 + NBIT]]


def copy_text(n, active, vdd, tend, mm):
    sup = [(0.0, 0.0), (L.T_RAMP, vdd), (tend, vdd)]
    t = []
    t.append(L.pwl_text("Vs_%s" % n, "s_%s" % n, "0", sup))
    t.append("Lvp_%s s_%s np_%s %.3e\nRvp_%s np_%s v_%s %.3f\nLvn_%s w_%s nn_%s %.3e\nRvn_%s nn_%s 0 %.3f\n"
             % (n, n, n, LSUP, n, n, n, RSUP / 2, n, n, n, LSUP, n, n, RSUP / 2))
    t.append("Ben_%s en_%s 0 V=v(s_%s)\n" % (n, n, n))
    for l in range(3):
        sp, sn = ("srcp%d" % l, "srcn%d" % l) if l in active else ("cm", "cm")
        t.append("Xnet_%s%d %s %s rx%d_p_%s rx%d_n_%s v_%s w_%s lvds_input_network\n" % (n, l, sp, sn, l, n, l, n, n, n))
        t.append("cl_%s%d rx%d_o_%s 0 30f\n" % (n, l, l, n))
    sub = "lvds_rx_x3_mm" if mm else "lvds_rx_x3"
    t.append("Xdut_%s v_%s w_%s rx0_p_%s rx0_n_%s rx1_p_%s rx1_n_%s rx2_p_%s rx2_n_%s en_%s rx0_o_%s rx1_o_%s rx2_o_%s %s\n"
             % ((n,) * 13 + (sub,)))
    return "".join(t)


def copies(mc3s):
    cp = [("a", {0, 1, 2}, False), ("b0", {0}, False), ("b1", {1}, False), ("b2", {2}, False)]
    if mc3s:
        cp += [("m%d" % i, {0, 1, 2}, True) for i in range(NMC)]
    return cp


def prep(ctx):
    mc3s = int(ctx["vars"]["mc3s"])
    vdd = ctx["corner"].vdd
    tend = L.TD0 + NBIT * UI + 3 * UI
    txt = ["* TB10 body mc3s=%d\n" % mc3s]
    if mc3s:
        txt.append(".option seed=%d\n" % SEED)
        # wrapper whose local parameter switches the PDK mismatch on for everything inside (the global header keeps it off for the nominal copies)
        txt.append(".subckt lvds_rx_x3_mm VDD VSS RX0_P RX0_N RX1_P RX1_N RX2_P RX2_N EN RX0_O RX1_O RX2_O\n.param sw_stat_mismatch=1\n"
                   "xi VDD VSS RX0_P RX0_N RX1_P RX1_N RX2_P RX2_N EN RX0_O RX1_O RX2_O lvds_rx_x3\n.ends lvds_rx_x3_mm\n")
    cm = [(0.0, 0.0), (L.T_RAMP, VIC), (tend, VIC)]
    txt.append(L.pwl_text("Vcm", "cm", "0", cm))
    for l, b in enumerate(lane_bits()):
        d = L.data_pwl(b, UI, TR, VID)
        txt.append(L.pwl_text("Vsp%d" % l, "srcp%d" % l, "0", L.pwl_sum(cm, d)))
        txt.append(L.pwl_text("Vsn%d" % l, "srcn%d" % l, "0", L.pwl_sum(cm, d, scales=[1.0, -1.0])))
    for (n, act, mm) in copies(mc3s):
        txt.append(copy_text(n, act, vdd, tend, mm))
    if not mc3s:   # the deck writes the same 24 columns in both modes: give the unused mismatch-copy output nodes a (dummy) resistor
        for i in range(NMC):
            for l in range(3):
                txt.append("Rdum_m%d_%d rx%d_o_m%d 0 1k\n" % (i, l, l, i))
    return {"body.inc": "".join(txt)}


def lane_delays(t, vo, bits, th):
    """Per data toggle: delay from the nominal mid-edge to the first output crossing of the right sense (NaN if missed).  Returns (t_cross list in toggle order, delays)."""
    tog = L.toggle_times(bits, UI, TR)
    r = A.crossings(t, vo, th, "rising")
    f = A.crossings(t, vo, th, "falling")
    tc, dl = [], []
    for (te, s) in tog:
        arr = r if s else f
        a = arr[arr >= te]
        if len(a) and a[0] - te < 0.9 * UI:
            tc.append(a[0])
            dl.append(a[0] - te)
        else:
            tc.append(float("nan"))
            dl.append(float("nan"))
    return np.array(tc), np.array(dl)


def post(ctx):
    mc3s = int(ctx["vars"]["mc3s"])
    vdd = ctx["corner"].vdd
    th = vdd / 2.0
    cps = copies(1)          # the data file always has the columns of all eight copies (unused ones are dummies)
    names = []
    for (n, _, _) in cps:
        for l in range(3):
            names.append((n, l))
    t, cols = A.load_wrdata(os.path.join(ctx["run_dir"], "tb10.txt"), nvec=len(names))
    vo = {nm: c for nm, c in zip(names, cols)}
    lb = lane_bits()
    out = {}
    # nominal skew
    med = []
    dly = {}
    for l in range(3):
        tc, dl = lane_delays(t, vo[("a", l)], lb[l], th)
        dly[l] = (tc, dl)
        out["n_missed_a%d" % l] = float(np.sum(np.isnan(dl[2:])))
        med.append(float(np.nanmedian(dl[2:])))
        out["delay_lane%d_ps" % l] = med[-1] * 1e12
    out["skew_s"] = float(max(med) - min(med))
    # crosstalk
    xt = []
    for l in range(3):
        tc_a, _ = dly[l]
        tc_b, _ = lane_delays(t, vo[("b%d" % l, l)], lb[l], th)
        d = (tc_a - tc_b)[2:]
        if np.any(np.isnan(d)):
            xt.append(1.0)           # a missed edge in either copy is a failure of the comparison
        else:
            xt.append(float((d.max() - d.min()) / UI))
        out["xtalk_lane%d_ui" % l] = xt[-1]
    out["xtalk_jitter_ui"] = float(max(xt))
    if mc3s:
        mat = np.zeros((NMC, 3))
        for i in range(NMC):
            for l in range(3):
                _, dl = lane_delays(t, vo[("m%d" % i, l)], lb[l], th)
                mat[i, l] = np.nanmedian(dl[2:]) if not np.all(np.isnan(dl[2:])) else float("nan")
        if np.any(np.isnan(mat)):
            out["skew_3sigma_s"] = float("nan")
        else:
            res = mat - mat.mean(axis=0, keepdims=True)
            dof = NMC * 3 - 3
            sig = float(np.sqrt(np.sum(res ** 2) / dof))
            out["sigma_lane_delay_ps"] = sig * 1e12
            out["skew_3sigma_s"] = 3.0 * np.sqrt(2.0) * sig
            out["skew_3sigma_ucl_s"] = out["skew_3sigma_s"] * float(np.sqrt(dof / CHI2_95_LOW_9))
            out["mc_range_ps"] = float((mat.max(axis=0) - mat.min(axis=0)).max() * 1e12)
    return out
