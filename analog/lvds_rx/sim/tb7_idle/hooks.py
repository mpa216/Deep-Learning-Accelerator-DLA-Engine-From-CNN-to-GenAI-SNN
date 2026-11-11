"""hooks.py (TB7 idle inputs, also TB7_mc): all three lanes see the same idle input; the output must hold a stable state (v0: no failsafe guarantee).

term (grid):
  0 open        driver removed: both source nodes float behind 1 Mohm to the common mode (the 50 ohm source resistors and the 100 ohm termination stay)
  1 terminated  driver powered off: both source nodes held at the common mode through the 50 ohm resistors, 100 ohm termination (VID = 0)
  2 shorted     as 1 plus a 1 mohm short between the two receiver pins
Phases: supply ramps 0 -> VDD in 50 ns (inputs and EN ramp with it); idle from 150 ns on.  With drift = 1 (terminated runs of TB7 only) the source
differential then drifts 0 -> +100 -> -100 -> 0 mV at 0.5 mV/ns (100 ns holds at the ends) to see a clean, chatter-free pass through both trip points.

Metrics (contract with spec/gates.yaml TB7 / TB7_mc), worst over the three lanes:
  osc_flag      1 if an output crossing of VDD/2 happens in the idle window, or the output moves by more than 0.1 V (p-p) in it, or the drift phase shows
                more than 2 crossings (one up through V_TH+, one down through V_TH- is the clean maximum); else 0
  min_pulse_s   shortest interval between consecutive 50 % crossings from 150 ns on (1 s when there are fewer than two)
  held_state    lane 0 at the end of the idle window: 1 = HIGH (> 0.9 VDD), 0 = LOW (< 0.1 VDD), -1 = intermediate level
  n_high        number of lanes (of 3) held HIGH
  n_mid         number of lanes held at an intermediate level
  drift_toggles output crossings per lane in the drift phase (max over lanes), drift only
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import lib_tb as L  # noqa: E402
from harness import analysis as A  # noqa: E402

T_IDLE0 = 150e-9
T_DRIFT0 = 600e-9
SLOPE = 0.5e-3 / 1e-9      # V/s
VD = 0.1
T_END_IDLE = 600e-9


def drift_pts():
    pts = [(0.0, 0.0), (T_DRIFT0, 0.0)]
    t = T_DRIFT0
    for lvl, hold in ((VD, 100e-9), (-VD, 100e-9), (0.0, 0.0)):
        t += abs(lvl - pts[-1][1]) / SLOPE
        pts.append((t, lvl))
        if hold:
            t += hold
            pts.append((t, lvl))
    return pts


def tend_drift():
    return drift_pts()[-1][0]


def prep(ctx):
    v = ctx["vars"]
    term = int(v["term"])
    vic = float(v["vic"])
    drift = int(v.get("drift", 0)) and term == 1
    vdd = ctx["corner"].vdd
    tend = tend_drift() + 100e-9 if drift else 600e-9 + 100e-9
    cm = [(0.0, 0.0), (L.T_RAMP, vic), (tend, vic)]
    txt = ["* TB7 body term=%d vic=%g drift=%d\n" % (term, vic, drift), ".param tstop_run=%.5e\n" % tend,
           # Measured 2026-11-11: at default tolerances ngspice stalls (ps steps, > 10 min) in some settled runs (1 of 105 and 10 of 450 at ff/-40C/3.6 V,
           # VIC 2.35 V): a decaying branch quantity of the cap_nmos model reaches the denormal range and the relative truncation test cannot be met.
           # reltol = 0.01 removes it (gmin, rshunt did not); the metrics are 50 % crossings and rail levels.  Same finding as TB8 (decision D-006).
           ".option reltol=0.01\n"]
    txt.append("Vsup vdd 0 PWL(0 0 %.3e %.4f)\nBen en 0 V=v(vdd)\n" % (L.T_RAMP, vdd))
    txt.append(L.pwl_text("Vcm", "cm", "0", cm))
    if drift:
        d = drift_pts()
        d.append((tend, 0.0))
        txt.append(L.pwl_text("Vsp", "srcp", "0", L.pwl_sum(cm, d)))
        txt.append(L.pwl_text("Vsn", "srcn", "0", L.pwl_sum(cm, d, scales=[1.0, -1.0])))
    for ln in range(3):
        p, n = "srcp%d" % ln, "srcn%d" % ln
        if term == 0:
            txt.append("Rop%d %s cm 1Meg\nRon%d %s cm 1Meg\n" % (ln, p, ln, n))
        else:
            txt.append("Rdp%d %s srcp 1m\nRdn%d %s srcn 1m\n" % (ln, p, ln, n)) if drift else \
                txt.append("Rdp%d %s cm 1m\nRdn%d %s cm 1m\n" % (ln, p, ln, n))
        txt.append("Xnet%d %s %s rx%d_p rx%d_n vdd 0 lvds_input_network\n" % (ln, p, n, ln, ln))
        if term == 2:
            txt.append("Rsh%d rx%d_p rx%d_n 1m\n" % (ln, ln, ln))
        txt.append("cl%d rx%d_o 0 30f\n" % (ln, ln))
    txt.append("Xdut vdd 0 rx0_p rx0_n rx1_p rx1_n rx2_p rx2_n en rx0_o rx1_o rx2_o lvds_rx_x3\n")
    return {"body.inc": "".join(txt)}


def post(ctx):
    v = ctx["vars"]
    term = int(v["term"])
    drift = int(v.get("drift", 0)) and term == 1
    vdd = ctx["corner"].vdd
    t, (o0, o1, o2) = A.load_wrdata(os.path.join(ctx["run_dir"], "tb7.txt"), nvec=3)
    th = vdd / 2.0
    osc = 0
    mp = L.BIG
    states = []
    dt_max = 0
    for o in (o0, o1, o2):
        # idle window: [T_IDLE0, T_END_IDLE]
        w = (t >= T_IDLE0) & (t <= T_END_IDLE)
        tt, _ = L.crossings_with_sense(t[w], o[w], th)
        if len(tt) > 0 or (o[w].max() - o[w].min()) > 0.1:
            osc = 1
        mp = min(mp, L.min_pulse(t, o, th, T_IDLE0))
        fin = o[(t >= T_END_IDLE - 50e-9) & (t <= T_END_IDLE)].mean()
        states.append(1 if fin > 0.9 * vdd else (0 if fin < 0.1 * vdd else -1))
        if drift:
            wd = t > T_DRIFT0 - 5e-9
            tc, _ = L.crossings_with_sense(t[wd], o[wd], th)
            dt_max = max(dt_max, len(tc))
            if len(tc) > 2:
                osc = 1
    out = {"osc_flag": float(osc), "min_pulse_s": mp, "held_state": float(states[0]), "n_high": float(sum(1 for s in states if s == 1)),
           "n_mid": float(sum(1 for s in states if s == -1)), "out_final_v": float(o0[(t >= T_END_IDLE - 50e-9) & (t <= T_END_IDLE)].mean())}
    if drift:
        out["drift_toggles"] = float(dt_max)
        out["out_end_v"] = float(o0[-1])
    return out
