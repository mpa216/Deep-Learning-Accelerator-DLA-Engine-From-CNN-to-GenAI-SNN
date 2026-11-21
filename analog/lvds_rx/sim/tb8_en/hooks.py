"""hooks.py (TB8 EN and supply ramps): two copies of the macro (a: VID = +350 mV, expected HIGH when enabled; b: VID = -350 mV, expected LOW), each with three lanes
on one bias, share the same supply waveform and EN; inputs are driven directly (no pad) at VIC 1.375 / 1.025 V scaled with the supply.

cases (grid `case`):
  0 en0          supply up in 50 ns, EN = 0 for 1.5 us: outputs LOW; IDD averaged over the last 300 ns (the macro, i.e. one copy's three lanes + bias)
  1 vdd_below_2v supply up to 1.9 V (below the 2.0 V threshold), 1.5 us, both copies driven VID = +350 mV.  Copy b has EN = 0: its outputs must be LOW (the gate,
                 vout_off_v).  Copy a has EN = 1 (EN follows the supply): REPORT ONLY (vout_en1_v, en1_valid_ok).  The macro has no under-voltage lockout
                 (decision D-008): with EN = 1 it keeps decoding validly at 1.9 V, so 'VDD < 2.0 V -> LOW' holds when EN is low, which the system must
                 guarantee until VDD >= 2.0 V.
  2 en_rise      supply at VDD from 50 ns; EN 0 -> 1 at 300 ns, 1 -> 0 at 1.5 us; valid time = EN 50 % -> all three a-outputs above 0.9 VDD
  3 ramp_1us     supply 0 -> VDD in 1 us, EN follows the supply (tied high), 2 us
  4 ramp_100us   same in 100 us, 110 us
  5 en_mid_ramp  supply ramps in 20 us; EN stays 0 until the supply reaches 2.0 V, then rises in 1 ns and follows the supply; 30 us
  6 ramp_1us_en0   supply 0 -> VDD in 1 us with EN = 0 throughout (the power-up order the system must use, D-008), 2 us   (decision D-019)
  7 ramp_100us_en0 same in 100 us, then 0.2 us settled (a 10 us tail stalls ngspice at some corners), 100.2 us             (decision D-019)

Metrics (contract with spec/gates.yaml TB8):
  vout_off_v    highest output voltage of the outputs that must be LOW (case 1: copy b; cases 0, 6, 7: all six).  Cases 0-1 from 100 ns on
                (decision D-019: their 50 ns setup ramp is not a spec ramp, as D-011 ruled for min_pulse_s); cases 6-7 over the whole run,
                i.e. the spec ramps.  Cases 2-5: all six outputs, whole run, reported only.
  vout_off_all_v  the same over the whole run (cases 0-1 incl. the setup ramp), reported
  vdd_at_peak_v, vdd_low_from_v  (cases 0, 1, 6, 7) supply at the vout_off_all_v peak, and the supply level of the last sample at which an output
                that must be LOW is above 10 % of the instantaneous supply (supply >= 0.5 V), reported
  early_high_v  case 5: highest output while EN is still 0 (supply below 2.0 V), gated since D-019
  idd_en0_a     mean supply current of one copy over the last 300 ns (case 0), worst of the two copies
  valid_time_s  case 2: EN rising 50 % to all a-outputs above 0.9 VDD (reported for ramps: from VDD = 2.0 V or EN rise)
  min_pulse_s   shortest completed pulse (interval between consecutive completed level changes of v_out / VDD(t), VDD(t) >= 0.5 V, each timed at
                its last 50 % crossing; lib_tb.pulses_norm, decision D-019) or shortest runt, over all six outputs (1 s if none).  A runt is an
                excursion off a rail zone (<= 10 % / >= 90 % of the instantaneous VDD) that returns without reaching the other zone; its width is
                taken at the departing 10 / 90 % level.  Spec: no runt pulse < 2 ns on EN edges or supply ramps.
  n_runt        number of runt excursions of any output (reported)
  vdd_at_out_rise_v  (ramps) supply voltage at which an a-output first leaves the LOW rail (0.5 V crossing)
  final_ok      1 if at the end (EN = 1 cases) the a-outputs are above 0.9 VDD and the b-outputs below 0.1 VDD, or (EN = 0 cases 0, 6, 7) all outputs
                below 0.1 VDD
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import lib_tb as L  # noqa: E402
from harness import analysis as A  # noqa: E402

CASES = ["en0", "vdd_below_2v", "en_rise", "ramp_1us", "ramp_100us", "en_mid_ramp", "ramp_1us_en0", "ramp_100us_en0"]
EN0_CASES = (0, 6, 7)              # EN = 0 for both copies for the whole run: every output must stay LOW
VIC, VID = 1.2, 0.35
V_UVLO = 2.0


def plan(case, vdd):
    """-> dict: supply pts, EN switch pts (None = no switch: ens = 1 or 0), tstop, tmax"""
    p = {}
    if case == 0:
        p.update(sup=[(0, 0), (50e-9, vdd), (1.5e-6, vdd)], ens=[(0, 0), (1.5e-6, 0)], tstop=1.5e-6, tmax=1e-9)
    elif case == 1:
        p.update(sup=[(0, 0), (50e-9, 1.9), (1.5e-6, 1.9)], ens=[(0, 1), (1.5e-6, 1)], tstop=1.5e-6, tmax=1e-9)
    elif case == 2:
        p.update(sup=[(0, 0), (50e-9, vdd), (2.2e-6, vdd)],
                 ens=[(0, 0), (300e-9, 0), (301e-9, 1), (1.5e-6, 1), (1.501e-6, 0), (2.2e-6, 0)], tstop=2.2e-6, tmax=1e-9)
    elif case == 3:
        p.update(sup=[(0, 0), (1e-6, vdd), (2e-6, vdd)], ens=[(0, 1), (2e-6, 1)], tstop=2e-6, tmax=1e-9)
    elif case == 4:
        p.update(sup=[(0, 0), (100e-6, vdd), (110e-6, vdd)], ens=[(0, 1), (110e-6, 1)], tstop=110e-6, tmax=20e-9)
    elif case == 5:
        tr = 20e-6
        te = V_UVLO / vdd * tr
        p.update(sup=[(0, 0), (tr, vdd), (30e-6, vdd)], ens=[(0, 0), (te, 0), (te + 1e-9, 1), (30e-6, 1)], tstop=30e-6, tmax=20e-9, t_en=te)
    elif case == 6:                 # D-019: case 3's ramp with EN = 0 throughout
        p.update(sup=[(0, 0), (1e-6, vdd), (2e-6, vdd)], ens=[(0, 0), (2e-6, 0)], tstop=2e-6, tmax=1e-9)
    elif case == 7:                 # D-019: case 4's ramp with EN = 0 throughout, 0.2 us of settled supply after it
        # A 10 us tail (case 4's) stalled ngspice at ss/125C/3.6 V, fs/125C/3.6 V, sf/-40C/3.0 V and sf/27C/3.6 V in every solver variant
        # (gear, tmax / 2, trtol 10, rshunt 1e13 tried too); with 0.2 us all four finish in 15-17 s: the stall sits in the settled tail, as
        # in cases 1 / 3 / 4 (about 0.7 us after the ramp).  The gated peak falls mid-ramp (VDD about 0.8 V) and final_ok reads the last 100 ns.
        p.update(sup=[(0, 0), (100e-6, vdd), (100.2e-6, vdd)], ens=[(0, 0), (100.2e-6, 0)], tstop=100.2e-6, tmax=20e-9)
    else:
        raise ValueError("TB8: no case %d" % case)
    return p


def prep(ctx):
    case = int(ctx["vars"]["case"])
    vdd = ctx["corner"].vdd
    p = plan(case, vdd)
    txt = ["* TB8 body case %d (%s)\n" % (case, CASES[case]), ".param tstop_run=%.5e tmax_run=%.4e\n" % (p["tstop"], p["tmax"]),
           ".option rshunt=%s\n" % ("1e13" if case == 0 else "1e11")]
    if case in (1, 3, 4, 6, 7):
        # Measured 2026-11-11: with EN = 1 from the start and the supply settled, ngspice stalls (steps of ps, > 10 min) about 0.7 us after the end of
        # the supply ramp at default tolerances: a decaying branch quantity of the cap_nmos model reaches the denormal range (1e-270 A seen) and the
        # relative truncation test can no longer be met.  reltol = 0.01 removes it (abstol, vntol, chgtol, method = gear, rshunt did not).  The
        # measurements of these cases are rail levels, 10/90 % excursions and 50 % crossings, insensitive to 1 % tolerance.
        # D-019 (cases 6, 7, EN = 0 on the spec ramps): the same stall hit 21 of the first 24 case-7 runs at default tolerance.  rshunt stays 1e11:
        # 1e13, case 0's value, moved the off-state peak at ss/-40C/3.6 V by 0.0 / 0.5 mV before layout and 0.1 / 2.2 mV extracted (case 6 / 7;
        # case 7 keeps 74 mV of margin), .scratch/tb8z.
        txt.append(".option reltol=0.01\n")
    txt.append(L.pwl_text("Vsa", "vdda", "0", p["sup"]))
    txt.append(L.pwl_text("Vsb", "vddb", "0", p["sup"]))
    txt.append(L.pwl_text("Vens", "ens", "0", p["ens"]))
    txt.append("Ben en 0 V=v(vdda)*v(ens)\nBsc sc 0 V=v(vdda)/%.3f\n" % vdd)
    for s, sg in (("a", 1), ("b", 1 if case == 1 else -1)):
        hi, lo = VIC + sg * VID / 2, VIC - sg * VID / 2
        for ln in range(3):
            txt.append("Bp%s%d rx%d_p_%s 0 V=v(sc)*%.4f\nBn%s%d rx%d_n_%s 0 V=v(sc)*%.4f\n" % (s, ln, ln, s, hi, s, ln, ln, s, lo))
            txt.append("cl%s%d rx%d_o_%s 0 30f\n" % (s, ln, ln, s))
        txt.append("Xdut_%s vdd%s 0 rx0_p_%s rx0_n_%s rx1_p_%s rx1_n_%s rx2_p_%s rx2_n_%s %s rx0_o_%s rx1_o_%s rx2_o_%s lvds_rx_x3\n"
                   % ((s, s) + (s,) * 6 + ("0" if (case == 1 and s == "b") else "en",) + (s,) * 3))
    return {"body.inc": "".join(txt)}


def post(ctx):
    case = int(ctx["vars"]["case"])
    vdd = ctx["corner"].vdd
    p = plan(case, vdd)
    t, cols = A.load_wrdata(os.path.join(ctx["run_dir"], "tb8.txt"), nvec=9)
    oa, ob = cols[0:3], cols[3:6]
    ia, ib, vsup = cols[6], cols[7], cols[8]
    outs = list(oa) + list(ob)
    if case == 1:
        vdd = 1.9                         # the supply level of the brown-out case (the corner's vdd does not apply)
    th = vdd / 2.0
    out = {}
    # gate metric: the highest output voltage that must be LOW.  Case 1: copy b (EN = 0, VID = +350 mV) at VDD = 1.9 V (EN = 0 or VDD < 2.0 V: LOW);
    # cases 0, 6, 7: all six (EN = 0 throughout); cases 2-5: all six, reported only.
    # D-019 (2026-11-22): cases 0-1 power the macro with the 50 ns setup ramp, which is not a spec ramp (1 us and 100 us).  While it passes about
    # 0.6-1.2 V no stage of the output chain (NAND + three inverters) conducts and the outputs float to about a third of the supply (extracted up to
    # 0.363 V at ss/-40C, 2-3 ns above 0.33 V).  As D-011 did for min_pulse_s, vout_off_v is judged from 100 ns on in cases 0-1; the whole-run value
    # stays reported (vout_off_all_v).  Cases 6 and 7 cover the spec ramps with EN = 0 over the whole run.
    off = ob if case == 1 else outs
    out["vout_off_all_v"] = float(max(o.max() for o in off))
    if case in (0, 1):
        w0 = t >= 100e-9
        out["vout_off_v"] = float(max(o[w0].max() for o in off))
    else:
        out["vout_off_v"] = out["vout_off_all_v"]
    if case == 1 or case in EN0_CASES:
        m = np.max(np.vstack(off), axis=0)
        i = int(np.argmax(m))
        out["vdd_at_peak_v"] = float(vsup[i])
        above = (vsup >= 0.5) & (m > 0.1 * vsup)
        out["vdd_low_from_v"] = float(vsup[np.where(above)[0][-1]]) if above.any() else 0.0
    if case == 1:
        # reported only (decision D-008): copy a has EN = 1 (EN follows the supply) at 1.9 V; the macro has no under-voltage lockout and decodes validly
        out["vout_en1_v"] = float(max(o.max() for o in oa))
        k1 = t >= t[-1] - 100e-9
        out["en1_valid_ok"] = float(all(o[k1].mean() > 0.9 * vdd for o in oa))
    if case == 0:
        w = t >= p["tstop"] - 300e-9
        out["idd_en0_a"] = float(max(-ia[w].mean(), -ib[w].mean()))
    # pulses
    # T5 (decision D-011): cases 0-2 power the macro with a 50 ns setup ramp that is NOT one of the spec ramps (1 us, 100 us = cases 3-5).  The
    # 1-2 ns excursions seen while that ramp passes 0.5-0.7 V (outputs ~0.1 V, the chain is not powered yet) were counted as runts and landed
    # at 1.99-2.00 ns at ff / fs corners.  The gated min_pulse_s therefore starts at 100 ns for cases 0-2 (supply settled; EN edges at 301 ns and
    # 1501 ns of case 2 are inside); the whole-run value stays in the results as min_pulse_all_s.
    t_from = 100e-9 if case in (0, 1, 2) else 0.0
    wsel = t >= t_from
    mp = mpa = L.BIG
    nrunt = 0
    mrw = mrwa = L.BIG
    for o in outs:
        mw, n, rw = L.pulses_norm(t[wsel], o[wsel], vsup[wsel])
        mp = min(mp, mw)
        mrw = min(mrw, rw)
        nrunt += n
        mwa, na, rwa = L.pulses_norm(t, o, vsup)
        mpa = min(mpa, mwa)
        mrwa = min(mrwa, rwa)
    out["n_runt"] = float(nrunt)
    out["min_pulse_all_s"] = min(mpa, mrwa)
    out["min_pulse_s"] = min(mp, mrw)
    out["min_pulse_cross_s"] = mp
    out["min_runt_width_s"] = mrw
    # valid time
    if case == 2:
        t_en = 301e-9 - 0.5e-9
        tv = []
        for o in oa:
            w = t >= t_en
            c = A.crossings(t[w], o[w], 0.9 * vdd, "rising")
            tv.append(c[0] - t_en if len(c) else float("nan"))
        out["valid_time_s"] = float(max(tv)) if not np.any(np.isnan(tv)) else float("nan")
    elif case in (3, 4):
        tv = []
        for o in oa:
            c = A.crossings(t, o, 0.9 * vdd, "rising")
            tv.append(c[0] if len(c) else float("nan"))
        out["t_high_s"] = float(np.nanmax(tv)) if not np.all(np.isnan(tv)) else float("nan")
        # at which supply level did the a-outputs first leave the LOW rail
        c0 = [A.crossings(t, o, 0.5, "rising") for o in oa]
        out["vdd_at_out_rise_v"] = float(np.interp(min(c[0] for c in c0), t, vsup)) if all(len(c) for c in c0) else float("nan")
    elif case == 5:
        w = t >= p["t_en"]
        tv = []
        for o in oa:
            c = A.crossings(t[w], o[w], 0.9 * vdd, "rising")
            tv.append(c[0] - p["t_en"] if len(c) else float("nan"))
        out["valid_time_s"] = float(max(tv)) if not np.any(np.isnan(tv)) else float("nan")
        # earliest moment an output left the LOW rail (before EN rose?)
        out["early_high_v"] = float(max(o[t < p["t_en"]].max() for o in outs))
    # end state
    k = t >= t[-1] - 100e-9
    ea = [o[k].mean() for o in oa]
    eb = [o[k].mean() for o in ob]
    if case == 1:
        ok = all(x < 0.1 * vdd for x in eb)
    elif case in EN0_CASES:
        ok = all(x < 0.1 * vdd for x in ea + eb)
    elif case == 2:
        # EN has fallen at 1.5 us: all LOW again; check the HIGH plateau just before
        kh = (t > 1.3e-6) & (t < 1.49e-6)
        okh = all(o[kh].mean() > 0.9 * vdd for o in oa) and all(o[kh].mean() < 0.1 * vdd for o in ob)
        out["high_phase_ok"] = float(okh)
        ok = okh and all(x < 0.1 * vdd for x in ea + eb)
    else:
        ok = all(x > 0.9 * vdd for x in ea) and all(x < 0.1 * vdd for x in eb)
    out["final_ok"] = float(ok)
    out["end_a_v"] = float(min(ea))
    out["end_b_v"] = float(max(eb))
    return out
