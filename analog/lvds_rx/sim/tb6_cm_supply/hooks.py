"""hooks.py (TB6): common-mode step, supply ripple and current-spike train during PRBS7 data on lane 0.

Two copies of the macro see the SAME data through the same input network:
  _d  the DISTURBED copy: rails vddm/vssm behind a supply impedance (1.0 ohm + 2 nH per rail, an assumption), pad ESD rails = the same local rails
  _r  the REFERENCE copy: ideal quiet rails, static common mode
The case (grid value) selects the disturbance applied to the _d copy only:
  0 cm_step  eight common-mode steps of 2 ns, alternating 0.05 -> 2.35 V and back, placed at -1 / 0 / +1 / +2 ns relative to the start of a data edge
             (see STEP_PLAN: every alignment of a step with a 2 ns data edge is inside each run); VID 100 mV (worst small-signal case), tr 2 ns
  1 ripple   100 mVpp (+-50 mV) 25 MHz sine on the board supply, EN follows the supply
  2 spike    25 MHz train of 20 mA / 1 ns triangular current spikes drawn from the local rails (digital-core emulation): rail bounce through R + L
  3 quiet    no disturbance (measures the harness itself: should give ~0 added jitter)

Metrics (contract with spec/gates.yaml TB6):
  false_toggles    | (output 50 % crossings of the disturbed copy after data start) - (input toggles) |
  added_jitter_ui  peak-to-peak spread of (t_out_d - t_out_ref) over all edges, UI units; for the CM step case the median of each static-CM segment (edges
                   more than 3 UI away from every step) is removed first (the static tPD shift with VIC is TB4's job, <= 1 ns); an edge that starts while a
                   step is running is judged against the PREVIOUS common-mode level
  rail_dev_v       largest excursion of the disturbed output from its rail in the settled part of every bit (reported)
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import lib_tb as L  # noqa: E402
from harness import analysis as A  # noqa: E402

UI = 10e-9
NBIT = 88
VID = 0.1
TR = 2.0e-9
VIC = 1.2
VLO, VHI = 0.05, 2.35
RSUP, LSUP = 1.0, 2e-9
F_RIP, A_RIP = 25e6, 0.05
I_SPK, T_SPK = 20e-3, 1e-9
CASES = ["cm_step", "ripple", "spike", "quiet"]


def bits():
    return L.S.prbs7(NBIT)


# Case 0 holds EIGHT 2 ns common-mode steps, alternating up (0.05 -> 2.35 V) and down, each placed relative to the start of a data edge (the data edge
# itself lasts 2 ns): offsets -1, 0, +1, +2 ns for the up steps and again for the down steps, so the worst alignment of a step with an edge is inside
# every run (alignment study 2026-11-11: one edge hit by a step can be delayed by up to 1.2 ns, depending on the alignment).  >= 8 bits between steps.
STEP_PLAN = [("up", -1e-9), ("dn", -1e-9), ("up", 0.0), ("dn", 0.0), ("up", 1e-9), ("dn", 1e-9), ("up", 2e-9), ("dn", 2e-9)]
STEP_FIRST_BIT = 14
STEP_SPACING = 8
T_STEP = 2e-9


def steps():
    """[(t_start, 'up'|'dn')] of the CM steps."""
    b = bits()
    out = []
    s = STEP_FIRST_BIT
    for (dr, off) in STEP_PLAN:
        i = next(k for k in range(s, len(b)) if b[k] != b[k - 1])
        out.append((L.TD0 + i * UI + off, dr))
        s = i + STEP_SPACING
    return out


def prep(ctx):
    case = int(ctx["vars"]["case"])
    b = bits()
    tend = L.TD0 + NBIT * UI + 3 * UI
    d = L.data_pwl(b, UI, TR, VID)
    # common mode of the disturbed copy and of the reference copy
    if case == 0:
        cm_d = [(0.0, 0.0), (L.T_RAMP, VLO)]
        for (ts, dr) in steps():
            lo, hi = (VLO, VHI) if dr == "up" else (VHI, VLO)
            cm_d += [(ts, lo), (ts + T_STEP, hi)]
        cm_d.append((tend, cm_d[-1][1]))
    else:
        cm_d = [(0.0, 0.0), (L.T_RAMP, VIC), (tend, VIC)]
    cm_r = [(0.0, 0.0), (L.T_RAMP, VIC if case != 0 else VLO), (tend, VIC if case != 0 else VLO)]
    vdd = ctx["corner"].vdd
    # board supply
    if case == 1:
        tt = np.arange(L.T_RAMP, tend + 1e-9, 0.5e-9)
        vs = vdd + A_RIP * np.sin(2 * np.pi * F_RIP * (tt - L.T_RAMP))
        sup = [(0.0, 0.0)] + list(zip(tt, vs))
    else:
        sup = [(0.0, 0.0), (L.T_RAMP, vdd), (tend, vdd)]
    txt = ["* TB6 body, case %d (%s)\n" % (case, CASES[case])]
    txt.append(L.pwl_text("Vsup", "vsup", "0", sup))
    txt.append("Lvp vsup nvp %.3e\nRvp nvp vddm %.3f\nLvn vssm nvn %.3e\nRvn nvn 0 %.3f\n" % (LSUP, RSUP / 2, LSUP, RSUP / 2))
    # the series R is split 0.5 ohm per side of L only for numerical convenience; total 1 ohm per rail (rail drop + return)
    txt.append("Vsupr vddr 0 PWL(0 0 %.3e %.4f)\n" % (L.T_RAMP, vdd))
    if case == 2:
        pts = [(0.0, 0.0)]
        t0 = L.T_RAMP + 20e-9 + 7e-9          # first spike 7 ns after the start of the measured window, then every 40 ns
        k = 0
        while t0 + k * 40e-9 + T_SPK < tend:
            te = t0 + k * 40e-9
            pts += [(te, 0.0), (te + T_SPK / 2, I_SPK), (te + T_SPK, 0.0)]
            k += 1
        pts.append((tend, 0.0))
        txt.append(L.pwl_text("Ispk", "vddm", "vssm", pts))
    txt.append("Ben_d en_d 0 V=v(vsup)\nBen_r en_r 0 V=v(vddr)\n")
    # pins of the unused lanes at the common mode of the copy (ramped with the supply)
    txt.append(L.pwl_text("Vcm_d", "cm_d", "0", cm_d))
    txt.append(L.pwl_text("Vcm_r", "cm_r", "0", cm_r))
    # lane 0 driver emf: P = cm + d, N = cm - d
    sp_d = L.pwl_sum(cm_d, d)
    sn_d = L.pwl_sum(cm_d, d, scales=[1.0, -1.0])
    sp_r = L.pwl_sum(cm_r, d)
    sn_r = L.pwl_sum(cm_r, d, scales=[1.0, -1.0])
    txt.append(L.pwl_text("Vsp_d", "srcp_d", "0", sp_d))
    txt.append(L.pwl_text("Vsn_d", "srcn_d", "0", sn_d))
    txt.append(L.pwl_text("Vsp_r", "srcp_r", "0", sp_r))
    txt.append(L.pwl_text("Vsn_r", "srcn_r", "0", sn_r))
    for s, rails in (("d", "vddm vssm"), ("r", "vddr 0")):
        txt.append("Xnet_%s srcp_%s srcn_%s rx0_p_%s rx0_n_%s %s lvds_input_network\n" % (s, s, s, s, s, rails))
        for ln in (1, 2):
            txt.append("Vp%d_%s rx%d_p_%s cm_%s dc 0\nVn%d_%s rx%d_n_%s cm_%s dc 0\n" % (ln, s, ln, s, s, ln, s, ln, s, s))
        txt.append("Xdut_%s %s rx0_p_%s rx0_n_%s rx1_p_%s rx1_n_%s rx2_p_%s rx2_n_%s en_%s rx0_o_%s rx1_o_%s rx2_o_%s lvds_rx_x3\n"
                   % (s, rails, s, s, s, s, s, s, s, s, s, s))
        txt.append("cl0_%s rx0_o_%s 0 30f\ncl1_%s rx1_o_%s 0 30f\ncl2_%s rx2_o_%s 0 30f\n" % (s, s, s, s, s, s))
    return {"body.inc": "".join(txt)}


def post(ctx):
    case = int(ctx["vars"]["case"])
    vdd = ctx["corner"].vdd
    b = bits()
    t, (vo_d, vo_r, vm, vs, vp, vn) = A.load_wrdata(os.path.join(ctx["run_dir"], "tb6.txt"), nvec=6)
    th = vdd / 2.0
    t_lo = L.TD0 - 5e-9
    td, sd = L.crossings_with_sense(t, vo_d, th, t_lo)
    tr_, sr = L.crossings_with_sense(t, vo_r, th, t_lo)
    n_in = len(L.toggle_times(b, UI, TR))
    out = {"false_toggles": float(abs(len(td) - n_in)), "n_out_d": float(len(td)), "n_out_r": float(len(tr_)), "n_in": float(n_in)}
    pairs, unm_d, unm_r = L.match_edges(tr_, sr, td, sd, UI / 2)
    out["unmatched"] = float(unm_d + unm_r)
    if case == 0:
        st = steps()
        edges_t = np.array([p[0] for p in pairs])           # reference output crossing of each edge
        dl = np.array([p[1] - p[0] for p in pairs])
        # input edge (start) belonging to each pair: the reference crossings follow the data toggles one to one
        tog = np.array([x[0] - TR / 2.0 for x in L.toggle_times(b, UI, TR)])
        if len(tog) != len(pairs):
            tog = edges_t - 6e-9
        # segment = number of steps that had finished (+2 ns) before the edge started: an edge that starts while a step is running is measured
        # against the delay level of the PREVIOUS common mode (conservative, the static shift between the two levels is up to 0.2 ns)
        seg = np.array([sum(1 for (ts, _) in st if ts + T_STEP <= te) for te in tog])
        far = np.array([all(abs(te - ts) > 3 * UI for (ts, _) in st) for te in tog])
        dev = dl.copy()
        for s in range(len(st) + 1):
            sel = seg == s
            ref = sel & far
            if ref.any():
                dev[sel] = dl[sel] - np.median(dl[ref])
        # worst edge per step alignment (reported)
        for j, (ts, dr) in enumerate(st):
            near = np.abs(tog - ts) <= 1.5 * UI
            if near.any():
                out["dev_step%d_%s_ps" % (j, dr)] = float(np.max(np.abs(dev[near])) * 1e12)
    else:
        dl = np.array([p[1] - p[0] for p in pairs])
        dev = dl - (np.median(dl) if len(dl) else 0.0)
    if len(dev) == 0:
        out["added_jitter_ui"] = float("nan")
    else:
        out["added_jitter_ui"] = float((dev.max() - dev.min()) / UI)
        out["delta_max_ps"] = float(np.max(np.abs(dl)) * 1e12)
    # rail deviation in the settled part of each bit (2 ns after the delayed edge ... 1 ns before the next one)
    dev_v = 0.0
    tt_in = L.TD0 + np.arange(NBIT) * UI
    for k in range(8, NBIT - 1):
        lo, hi = tt_in[k] + 8e-9, tt_in[k] + UI + 1e-9 - 0.0
        # the delayed output of bit k is settled between (edge + tpd + 2 ns) and (next edge + tpd); use [edge + 8 ns, next edge + 3 ns]
        hi = tt_in[k] + UI + 3e-9
        sel = (t >= lo) & (t <= hi)
        if not sel.any():
            continue
        rail = vdd if b[k] else 0.0
        dev_v = max(dev_v, float(np.max(np.abs(vo_d[sel] - rail))))
    out["rail_dev_v"] = dev_v
    out["vrail_pp_v"] = float((vm - vs)[t > L.TD0].max() - (vm - vs)[t > L.TD0].min())
    if ctx["corner"].name == "tt_27c_3v30":
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            pl = os.path.join(ctx["run_dir"], "..", "..", "plots")
            os.makedirs(pl, exist_ok=True)
            fig, ax = plt.subplots(3, 1, figsize=(9, 6), sharex=True)
            ax[0].plot(t * 1e9, vp - vn, lw=0.8)
            ax[0].set_ylabel("pin P-N (V)")
            ax[1].plot(t * 1e9, vm - vs, lw=0.8, label="local VDD-VSS")
            ax[1].plot(t * 1e9, vp, lw=0.8, label="pin P")
            ax[1].legend(fontsize=7)
            ax[1].set_ylabel("V")
            ax[2].plot(t * 1e9, vo_d, lw=0.8, label="disturbed")
            ax[2].plot(t * 1e9, vo_r, lw=0.8, ls="--", label="reference")
            ax[2].legend(fontsize=7)
            ax[2].set_ylabel("out (V)")
            ax[2].set_xlabel("ns")
            ax[0].set_title("TB6 %s tt  false=%d  jitter %.3f UI" % (CASES[case], out["false_toggles"], out.get("added_jitter_ui", float("nan"))))
            fig.tight_layout()
            fig.savefig(os.path.join(pl, "tb6_%s_tt.png" % CASES[case]), dpi=90)
            plt.close(fig)
        except Exception:
            out["plot_error"] = 1.0
    return out
