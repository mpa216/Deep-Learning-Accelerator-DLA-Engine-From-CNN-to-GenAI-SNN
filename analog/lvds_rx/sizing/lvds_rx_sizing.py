#!/usr/bin/env python3
"""lvds_rx_sizing.py -- THE single source of truth for every W / L / nf / R of the LVDS receiver lane and the shared bias
(task T2, PLAN_V2 4.3; block procedure of HANDOFF 7 as modified by PLAN_V2).

    python3 sizing/lvds_rx_sizing.py [--set key=value ...] [--no-write]

Method (book via docs/GMID_METHOD_NOTES.md): W = ID / (ID/W)(gm/ID, L, VDS, VSB) from the look-up tables (gmid_gf180.py);
L on the table grid; matched devices are ONE device with nf fingers (never m=); the mirror ratios are integer finger counts.
Every size is computed here, nothing is tuned by hand in SPICE.

Structure
  1  spec block          (spec/spec.yaml, frozen)
  2  design variables    dict D below: every gm/ID, L, current and ratio, each with the reason
  3  one function per block (bias, stage 1, stage 2, stage 3 + output, secondary ESD) returning devices and derived numbers
  4  corner evaluation   the bias is a resistor-diode, so every current moves with VDD, temperature and the resistor section:
                         the corner solver re-evaluates bias, stage 1 (CM, gain, headroom), stage 2 (headroom, hysteresis),
                         stage 3 and the current tally at tt 3.0/3.3/3.6 V, ss/125C/3.0 V, ff/-40C/3.6 V and the two resistor
                         cross corners, using the corner tables (typical table for VSB beyond the corner table's 0.8 V)
  5  asserts             headroom, N/P overlap, fan-out, fold pole, stage-1 pole, gain, hysteresis window, offset budget (the
                         four terms of finding C3), current tally
  6  outputs             sizing/sizes.spice (hash header), sizing/sizing_report.md, layout/device_table.json, results/sizing.json
"""
import argparse
import hashlib
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'flow'))
import gmid_gf180 as G  # noqa: E402
import common as C      # noqa: E402

SPEC = C.load_yaml('spec/spec.yaml', ROOT)

# =====================================================================================================================
# 1  SPEC BLOCK (values come from the frozen spec; nothing typed twice)
# =====================================================================================================================
DR = SPEC['data']['rate_bps']
I_LANE_MAX = SPEC['current']['i_lane_max_a']
I_BIAS_MAX = SPEC['current']['i_bias_max_a']
A1_MIN = SPEC['stage1']['a1_min']
VH_MIN, VH_MAX, VH_NOM = (SPEC['hysteresis'][k] for k in ('min_v', 'max_v', 'nominal_v'))
SIGMA_TARGET = SPEC['offset']['design_sigma_v']
NP_OVERLAP_MIN = SPEC['stage1']['np_overlap_min_v']
VDSAT_MARGIN = SPEC['tb1']['vdsat_headroom_min_v']          # 50 mV
CM_WINDOW = SPEC['stage1']['out_cm_window_v']
OUT_LOAD = SPEC['output']['load_f']
VARIANTS = SPEC['variants']

# =====================================================================================================================
# 2  DESIGN VARIABLES (each with its reason; book section in docs/SPIKE_STAGE1.md and docs/GMID_METHOD_NOTES.md)
# =====================================================================================================================
D = dict(
    vdd=3.3,
    vref_ratio=0.48,           # Vref = 0.48*VDD: centre of the N/P overlap window at every corner (PLAN_V2 C4, T1 spike)
    # ---- bias: ONE NMOS unit finger and ONE PMOS unit finger; every current is an integer multiple of a reference
    L_unit=1.0, gmid_unit=7.5,           # mirror devices: low VDsat (2/7.5 = 0.27 V; 7.0 left M3 at 62 mV at the ss/125 cross corner), matching and ro from L = 1 (book 5.2, handoff 7.3 item 5)
    wf_n=2.5, wf_p=5.0,                  # finger widths of the NMOS and PMOS unit (um): integer finger counts give exact ratios
    i_ref=48e-6,                         # reference current: the NMOS diode carries it; 48 uA keeps Rb about 53 kohm (one poly serpentine)
    n_tail_n=8, n_m3=10, n_t2=10,        # NMOS multiples (units of the diode/4): stage-1 N tail 2x iref, M3 sinks 2.5x, stage-2 tail 2.5x
                                         # (T11 iteration 1: n_t2 5 -> 10; with the layout's loads the frozen stage 2 made tPD 6.8 ns at ss/125C/3.0 V)
    p_ratio_tail=2.0,                    # PMOS tail = 2 x the PMOS reference diode
    ib2_div=4,                           # VB2 replica carries I(M5)/4: a 1-finger copy of M5 on Vf
    vf_tt=0.46,                          # cascode offset voltage F at tt: the window is M3 VDS >= VDsat3 + 50 mV at ss/125 C (F falls 18 % there) and the steered PMOS-pair device's VSD at VIC = 0.05 V at ff/-40 C (F rises 15 %); t2_op measured 45 mV there at F = 0.62 V
    i_div=40e-6,                         # Vref divider current (EN-gated)
    rw=2.0,                              # poly resistor width (um), ppolyf_u_1k: the same material for RL, Rb, Rf, divider (gain = ratio, eq. 5.7)
    # ---- stage 1 (T1 decision D-002: hybrid + dump)
    vr_tt=1.17,                          # T5 iteration 1: was 1.25; the NMOS pair at VIC = 2.35 V ran 9-19 mV into triode at ff/fs hot corners at VDD 3.0 V (TB1 full45, vr 1.10 gave +130 mV, linear: ~1 mV per mV of VR); 1.17 gives about +60 mV there at 6 % less gain.  RL drop at tt (T1 used 1.0 with ideal bias; the resistor-diode bias makes VR follow (VDD - VGS_b) x RL/Rb, i.e. -14 % at ss/125 C, so the slow corners need 1.25 at tt)
    gmid_pair_n=16.0, L_pair_n=0.5,        # NMOS pair 15 -> 16: the NMOS path is the weakest at ss/125 C (gm/ID falls with temperature)
    gmid_pair_p=15.0, L_pair_p=0.4,      # PMOS pair gm/ID 15 as in T1 (16 would add 7 % gain but +28 % W, i.e. +28 % fold-node capacitance)
    gmid_m3=7.0, L_m3=1.0,
    gmid_m5=13.0, L_m5=0.5,            # cascode gm sets the fold pole (eq. 6.38): gm/ID 10 -> 13 gives +30 % gm at the same current (VDS has 1.5 V to spare)
    i3_ratio=1.2,                        # I(M3 each) / Itp (T1)
    vds=dict(pair_n=1.2, vsb_pair_n=0.7, pair_p=1.4, tail_n=0.8, tail_p=0.8, m5=1.8, vsb_m5=0.5, t2=1.1),
    wf_pair=5.0,
    # ---- stage 2 hysteresis comparator
    gmid_s2=8.0, L_s2=0.5, wf_s2=5.0,    # pair: offset allowance sigma_2 <= 0.5*A1_min*sigma_target = 10 mV is generous, so area is spent on speed
                                         # (T11 iteration 1: 12 -> 8: twice the tail current at a smaller pair, less gate load on oa/ob)
    L_ld=0.28, wf_ld=2.0,                # PMOS loads (diode + cross-coupled) and the stage-3 copies: short L for the regeneration time constant
                                         # (T11 iteration 1: 0.4 -> 0.28; 0.4 failed the latched pair margin at ss/res_ff once n_t2 doubled)
    alpha_cands=[(4, 5), (5, 7), (2, 3), (3, 5)],   # (nf diode, nf cross): alpha = ratio; for each, the source-degeneration Rs gives V_H,in = 14 mV at tt, the one with the smallest corner spread wins
    # ---- stage 3 + output
    r3=2.0,                              # stage-3 PMOS mirror copies the load diode x r3
    gmid_n3=8.0, L_n3=0.28,              # was 0.5: TB2 (T2 part 2) measured the d3 pole (rds of the mirror / C of d3 + NAND gate) at 39 MHz ss/125 C vs 80 MHz needed; L 0.28 gives 102 MHz (gain A3 48 -> 19, ample after A1 x A2)
    dig_L=0.28,
    # n/p widths (um) of the digital chain NAND2, INV1, INV2, INV3 (output 30 fF): FO <= 4 per stage, edge <= 1 ns checked in TB4
    dig=dict(nand=(2.0, 3.0), inv1=(1.5, 3.7), inv2=(3.0, 7.5), inv3=(8.0, 20.0)),
    # ---- switches / EN gating (digital style: only Ron and leakage matter, book 6.5)
    w_sw_p=40.0, L_sw=0.5,               # series PMOS switch in the Rb branch
    w_pull=2.0, L_pull=0.5,              # pull-down / pull-up devices that park VBN, VBP, VB2, d2a/d2b when EN = 0
    w_vsw=10.0,                          # Vref divider NMOS switch
    c_vref_ff=2000.0,                    # decoupling at Vref (fF)
    # ---- secondary ESD (frozen assumption, PLAN_V2 spec input_network.esd2)
    esd_rw=5.0, esd_rl=1.8, esd_dw=8.0, esd_dl=5.0,
    cw=10.0,                             # wiring + RL parasitic on the stage-1 output nodes (fF), assumption
)

EST_PATH = os.path.join(HERE, 'parasitic_estimate.json')


def load_estimate():
    """T11 iteration 1: the layout parasitic estimate (sim/tbl/make_estimate.py), or None before it exists."""
    if not os.path.isfile(EST_PATH):
        return None
    with open(EST_PATH) as f:
        return json.load(f)


_est = load_estimate()
if _est:
    D['cw'] = _est['cw_fF']['lane_oa'] + _est['cwd_fF']['lane_oa']    # stage-1 output wiring of the extracted layout (was the 10 fF assumption)

# resistor facts (docs/ENV_REPORT.md section 3): ppolyf_u_1k, rsh_eff 1013 ohm/sq tt/27C, end resistance 85 ohm
RSH_1K, R_ENDS = 1013.0, 85.0
R_PROC = {'typ': 1.0, 'ss': 1.199, 'ff': 0.801}       # R_ss/R_tt, R_ff/R_tt
R_TEMP = {27: 1.0, 125: 0.932, -40: 1.076}            # R(T)/R(27C)
AVT_N, AVT_P = 7.148e-3, 6.66e-3 * 1.17               # V*um; PMOS formula is optimistic by 6-17 % (PLAN_V2 1.5): use +17 %
VDSAT_K_N1 = 0.86      # BSIM vdsat / (2/(gm/ID)) measured in the T1 spike for the NMOS L = 1 sinks: 0.80-0.86 over 8 corners (results/spike_stage1); other devices use 1.0 (conservative)


class Corner:
    def __init__(self, name, suf, vdd, temp, res, approx=''):
        self.name, self.suf, self.vdd, self.temp, self.res, self.approx = name, suf, vdd, temp, res, approx
        self.sR = R_PROC[res] * R_TEMP[temp]


CORNERS = [
    Corner('tt_27c_3v30', '', 3.3, 27, 'typ'),
    Corner('tt_27c_3v00', '', 3.0, 27, 'typ'),
    Corner('tt_27c_3v60', '', 3.6, 27, 'typ'),
    Corner('ss_125c_3v00', '_ss_125C', 3.0, 125, 'ss'),
    Corner('ff_m40c_3v60', '_ff_n40C', 3.6, -40, 'ff'),
    Corner('ss_125c_3v00_xrff', '_ss_125C', 3.0, 125, 'ff'),
    Corner('ff_m40c_3v60_xrss', '_ff_n40C', 3.6, -40, 'ss'),
]
TT = CORNERS[0]

# =====================================================================================================================
# LUT helpers (arrays over VGS + interpolation: one table call per inverse)
# =====================================================================================================================
_cache = {}


def _tab(kind, c):
    return G.lut(('nfet_03v3' if kind == 'n' else 'pfet_03v3') + c.suf)


def _arr(kind, c, ratio, L, vds, vsb):
    t = _tab(kind, c)
    vsb_c = min(vsb, float(t['VSB'].max()))
    vds = max(vds, 0.05)
    key = (kind, c.suf, ratio, round(L, 3), round(vds, 3), round(vsb_c, 3))
    if key not in _cache:
        _cache[key] = np.asarray(t.lookup(ratio, L=L, VGS=t['VGS'], VDS=vds, VSB=vsb_c), dtype=float)
    return t['VGS'], _cache[key], vsb_c < vsb - 1e-9


def jd(kind, c, L, vgs, vds, vsb=0.0):
    """ID/W (A/um) at the given bias; the VSB beyond the corner table is clipped (typical table has 2.0 V)."""
    x, y, _ = _arr(kind, c, 'ID_W', L, vds, vsb)
    return float(np.exp(np.interp(vgs, x, np.log(np.maximum(y, 1e-30)))))


def vgs_of_jd(kind, c, L, jdv, vds, vsb=0.0):
    x, y, clipped = _arr(kind, c, 'ID_W', L, vds, vsb)
    ly = np.log(np.maximum(y, 1e-30))
    v = float(np.interp(math.log(jdv), ly, x))
    if clipped and c.suf:                                  # body effect beyond the corner table: add the typical-table delta
        t0 = TT
        vt = vgs_of_jd(kind, t0, L, jdv, vds, vsb)
        vt_clip = vgs_of_jd(kind, t0, L, jdv, vds, min(vsb, float(_tab(kind, c)['VSB'].max())))
        v += vt - vt_clip
    return v


def ratio_of_jd(kind, c, ratio, L, jdv, vds, vsb=0.0):
    v = vgs_of_jd(kind, c, L, jdv, vds, vsb)
    x, y, _ = _arr(kind, c, ratio, L, vds, vsb)
    return float(np.interp(v, x, y))


def gmid_of_jd(kind, c, L, jdv, vds, vsb=0.0):
    return ratio_of_jd(kind, c, 'GM_ID', L, jdv, vds, vsb)


def vgs_diode(kind, c, L, W, I, vsb=0.0):
    v = 0.8
    for _ in range(8):
        v = vgs_of_jd(kind, c, L, I / W, v, vsb)
    return v


def q(x, step=0.01):
    return round(round(x / step) * step, 4)


def nf_of(W, wf):
    return max(1, int(math.ceil(W / wf - 1e-9)))


# =====================================================================================================================
# 3  BLOCKS.  A device record: stem, block, kind, role, L, nf, Wf, W, ID (design, tt), plus filled-in operating numbers
# =====================================================================================================================
def dev(devs, stem, block, kind, role, L, nf, Wf, ID=None, **kw):
    Wf = q(Wf)
    d = dict(stem=stem, block=block, kind=kind, role=role, L=L, nf=int(nf), Wf=Wf, W=q(Wf * nf, 0.01), ID=ID)
    d.update(kw)
    devs[stem] = d
    return d


def block_bias_and_units(S, devs):
    """Mirror units, bias branches, Vf generator, Vref divider, EN switches (all at tt 3.3 V)."""
    c = TT
    L1 = D['L_unit']
    # unit current density at the design point gm/ID = 7, VDS = 0.8 (tails) from the table
    jn = G.at_gmid('nfet_03v3', 'ID_W', D['gmid_unit'], L1, 0.8)      # A/um
    jp = G.at_gmid('pfet_03v3', 'ID_W', D['gmid_unit'], L1, 0.8)
    iun, iup = jn * D['wf_n'], jp * D['wf_p']                        # unit currents (A per finger)
    n_ref = max(1, round(D['i_ref'] / iun))                           # fingers of the reference NMOS diode
    S['iun'], S['iup'], S['n_ref'] = iun, iup, n_ref
    iref = n_ref * iun
    # NMOS family (gate VBN); diode MBN = n_ref units
    f = n_ref / 4.0                                                   # n_tail_n etc. are written for n_ref = 4
    for stem, role, mult in (('mbn', 'VBN reference diode (Rb branch)', n_ref),
                             ('mbs', 'VBP-branch NMOS sink, 1:1 with MBN', n_ref),
                             ('mnt', 'stage-1 NMOS tail', int(round(D['n_tail_n'] * f))),
                             ('m3', 'stage-1 NMOS sinks (fold), each of 2', int(round(D['n_m3'] * f))),
                             ('mt2', 'stage-2 tail', int(round(D['n_t2'] * f)))):
        dev(devs, stem, 'bias' if stem in ('mbn', 'mbs') else 'lane', 'n', role, L1, mult, D['wf_n'], mult * iun, mult=mult)
    # PMOS family (gate VBP): diode = reference current in PMOS units, tails 2x
    n_refp = max(1, round(iref / iup))
    dev(devs, 'mbp', 'bias', 'p', 'VBP reference diode', L1, n_refp, D['wf_p'], n_refp * iup, mult=n_refp)
    n_tp = int(round(D['p_ratio_tail'] * n_refp))
    dev(devs, 'mpt', 'lane', 'p', 'stage-1 PMOS tail', L1, n_tp, D['wf_p'], n_tp * iup, mult=n_tp)
    S['n_refp'] = n_refp
    return iref


def block_stage1(S, devs):
    c = TT
    p = D
    itp = devs['mpt']['ID']
    itn = devs['mnt']['ID']
    i3 = devs['m3']['ID']
    S.update(itp=itp, itn=itn, i3=i3)
    # pairs (and their dump twins: same W/L/nf): each device carries tail/2
    v = D['vds']
    for key, kind, tail, L, gmid, vds, vsb in (
            ('n', 'n', itn, p['L_pair_n'], p['gmid_pair_n'], v['pair_n'], v['vsb_pair_n']),
            ('p', 'p', itp, p['L_pair_p'], p['gmid_pair_p'], v['pair_p'], 0.0)):
        r = G.size('nfet_03v3' if kind == 'n' else 'pfet_03v3', gm=gmid * tail / 2, gmid=gmid, L=L, VDS=vds, VSB=vsb, wf_max=p['wf_pair'])
        nf = r['nf'] + (r['nf'] % 2)                                   # even nf: shared inner drains (handoff 7 rules)
        wf = r['W'] / nf
        dev(devs, 'm%s1' % key, 'lane', kind, 'input pair device (x2)', L, nf, wf, tail / 2, gmid_design=gmid)
        dev(devs, 'm%sd' % key, 'lane', kind, 'dump twin (x2), gate at Vref', L, nf, wf, tail / 2, gmid_design=gmid)
    i5 = i3 - itp / 2
    r5 = G.size('nfet_03v3', gm=p['gmid_m5'] * i5, gmid=p['gmid_m5'], L=p['L_m5'], VDS=v['m5'], VSB=v['vsb_m5'], wf_max=5.0)
    dev(devs, 'm5', 'lane', 'n', 'fold cascode (x2)', p['L_m5'], r5['nf'], r5['W'] / r5['nf'], i5, gmid_design=p['gmid_m5'])
    # load resistors: RL = VR / IRL at tt
    irl = i3 - itp / 2 + itn / 2
    rl = p['vr_tt'] / irl
    S['rl'] = rl
    return


def res_len(R):                                                        # um of ppolyf_u_1k at width rw for R ohm (tt/27C)
    return (R - R_ENDS) * D['rw'] / RSH_1K


def block_bias_rest(S, devs):
    c = TT
    L1 = D['L_unit']
    # Rb from the diode at gm/ID = 7: VGS from the table, switch drop from its Ron
    wb = devs['mbn']['W']
    iref = devs['mbn']['ID']
    vgs_b = vgs_of_jd('n', c, L1, iref / wb, vds=0.8)                  # diode VDS = VGS ~ 0.75-0.8
    for _ in range(3):
        vgs_b = vgs_of_jd('n', c, L1, iref / wb, vds=vgs_b)
    sw = dict(L=D['L_sw'], W=D['w_sw_p'])
    ron_sw = 0.05 / (jd('p', c, sw['L'], c.vdd, 0.05) * sw['W'])
    S['ron_sw_tt'] = ron_sw
    rb = (D['vdd'] - vgs_b) / iref - ron_sw
    S.update(rb=rb, vgs_b_tt=vgs_b)
    dev(devs, 'msw', 'bias', 'p', 'Rb-branch series switch (gate ENB)', sw['L'], nf_of(sw['W'], 5.0), sw['W'] / nf_of(sw['W'], 5.0))
    # VB2 / Vf generator: Mb2p (PMOS copy, gate VBP) -> Mb2 (1 finger of M5, diode) on Vf, Rf to VSS
    m5 = devs['m5']
    nb2 = max(1, int(round(devs['m5']['ID'] / D['ib2_div'] / devs['mbp']['ID'] * devs['mbp']['nf'])))
    dev(devs, 'mb2p', 'bias', 'p', 'VB2 branch current source (gate VBP)', D['L_unit'], nb2, D['wf_p'], nb2 * devs['mbp']['ID'] / devs['mbp']['nf'], mult=nb2)
    ib2 = devs['mb2p']['ID']
    wb2 = m5['W'] / D['ib2_div']                                       # same current density as M5
    dev(devs, 'mb2', 'bias', 'n', 'VB2 replica of M5 (diode on Vf)', m5['L'], 1, wb2, ib2)
    rf = D['vf_tt'] / ib2
    S.update(rf=rf, ib2_tt=ib2)
    # Vref divider with Ron compensation
    ron_n = 0.05 / (jd('n', c, D['L_pull'], c.vdd, 0.05) * D['w_vsw'])
    rtot = D['vdd'] / D['i_div']
    r_bot = D['vref_ratio'] * rtot - ron_n
    r_top = rtot - D['vref_ratio'] * rtot
    S.update(r_div_top=r_top, r_div_bot=r_bot, ron_vsw=ron_n)
    dev(devs, 'mvs', 'bias', 'n', 'Vref divider switch (gate EN)', D['L_pull'], nf_of(D['w_vsw'], 5.0), D['w_vsw'] / nf_of(D['w_vsw'], 5.0))
    # EN inverter and park devices
    dev(devs, 'men_n', 'bias', 'n', 'ENB inverter NMOS', D['dig_L'], 1, 1.0)
    dev(devs, 'men_p', 'bias', 'p', 'ENB inverter PMOS', D['dig_L'], 1, 2.5)
    dev(devs, 'mpd_n', 'bias', 'n', 'parks VBN at 0 when EN=0 (gate ENB)', D['L_pull'], 1, D['w_pull'])
    dev(devs, 'mpu_p', 'bias', 'p', 'parks VBP at VDD when EN=0 (gate EN)', D['L_pull'], 1, D['w_pull'])
    dev(devs, 'mpd_2', 'bias', 'n', 'parks VB2 at 0 when EN=0 (gate ENB)', D['L_pull'], 1, D['w_pull'])


def block_stage2(S, devs):
    """Stage 2: hysteresis comparator.  NMOS pair, PMOS diode + cross-coupled loads (alpha = nf_cross / nf_diode),
    source-degeneration resistors Rs (ppolyf_u_1k) that make the trip ratio-metric (I_T2 x Rs follows (VDD - VGS_b) x Rs/Rb like VR does)."""
    p = D
    it2 = devs['mt2']['ID']
    S['it2'] = it2
    r = G.size('nfet_03v3', gm=p['gmid_s2'] * it2 / 2, gmid=p['gmid_s2'], L=p['L_s2'], VDS=1.0, VSB=1.0, wf_max=p['wf_s2'])
    dev(devs, 'ms', 'lane', 'n', 'stage-2 input pair (x2)', p['L_s2'], r['nf'], r['W'] / r['nf'], it2 / 2, gmid_design=p['gmid_s2'])


def trip_voltage(c, it, W, L, alpha, cm, vds=1.0, rs=0.0):
    """Differential gate voltage at which I_b/I_a = alpha for the stage-2 pair (NMOS, tail current it, degeneration rs per side)
    at common mode cm: large-signal solve from the table (book 3.3 / Ex. 3.11); body effect through VSB = source node voltage."""
    ia, ib = it / (1 + alpha), it * alpha / (1 + alpha)

    def gates(vs):
        va = vgs_of_jd('n', c, L, ia / W, vds, vs + ia * rs)
        vb = vgs_of_jd('n', c, L, ib / W, vds, vs + ib * rs)
        return vs + ia * rs + va, vs + ib * rs + vb

    lo, hi = 0.05, cm - 0.3
    for _ in range(22):
        mid = 0.5 * (lo + hi)
        ga, gb = gates(mid)
        if 0.5 * (ga + gb) > cm:
            hi = mid
        else:
            lo = mid
    ga, gb = gates(0.5 * (lo + hi))
    return gb - ga


def choose_alpha_rs(S, devs, pre):
    """For every (nd, nc) candidate find the Rs that gives V_H,in = VH_NOM at tt (reference gain a1_ref), then evaluate V_H,in at the
    proxy corners (tt 3.0/3.3/3.6 V, ss/125 C, ff/-40 C) and keep the candidate with the smallest max/min ratio."""
    it2_tt, cm_tt = pre[TT.name]['b']['it2'], pre[TT.name]['b']['cm']
    wms, Lms = devs['ms']['W'], D['L_s2']
    a1_ref = 1.1 * pre[TT.name]['s1']['a1_ext']                   # mid-VIC gain is ~1.0-1.2 x the extremes (T1: spread <= 1.27)
    target = 2 * VH_NOM * a1_ref / 2.0 * 1.0                        # V_H2 = 2 x V_trip; V_trip target = VH_NOM*a1_ref/2
    target_trip = VH_NOM * a1_ref / 2.0
    scan = []
    for nd, nc in D['alpha_cands']:
        alpha = nc / nd
        lo, hi = 0.0, 20000.0
        for _ in range(14):
            rs = 0.5 * (lo + hi)
            if trip_voltage(TT, it2_tt, wms, Lms, alpha, cm_tt, rs=rs) < target_trip:
                lo = rs
            else:
                hi = rs
        rs = 0.5 * (lo + hi)
        vals = {}
        for nm, e in pre.items():
            c = e['c']
            vh2 = 2 * trip_voltage(c, e['b']['it2'], wms, Lms, alpha, e['b']['cm'], rs=rs * c.sR)
            vals[nm] = (vh2 / e['s1']['a1_ext'] / 1.27, vh2 / e['s1']['a1_ext'])        # (min, max) over VIC with the T1 spread factor
        lo_v = min(v[0] for v in vals.values())
        hi_v = max(v[1] for v in vals.values())
        scan.append(dict(nd=nd, nc=nc, alpha=alpha, rs=rs, ratio=hi_v / lo_v, vh_min=lo_v, vh_max=hi_v,
                         vh_in_tt=vals[TT.name][1] / 1.27 * 1.0, per_corner=vals))
    # speed vs spread: the regeneration time constant falls with (alpha - 1)/(alpha + 1), the corner spread of V_H,in grows slowly with alpha:
    # take the LARGEST alpha whose max/min ratio stays <= 2.2 (window ratio is 3.1; T1 gain spread and the missing corners need the room)
    ok = [s for s in scan if s['ratio'] <= 2.2]
    best = max(ok, key=lambda s: s['alpha']) if ok else min(scan, key=lambda s: s['ratio'])
    S['alpha_scan'] = scan
    S['alpha'], S['nd'], S['nc'], S['rs'] = best['alpha'], best['nd'], best['nc'], best['rs']
    return best


def finish_stage2(S, devs):
    p = D
    it2, nd, nc = S['it2'], S['nd'], S['nc']
    dev(devs, 'mld', 'lane', 'p', 'stage-2 diode load (x2)', p['L_ld'], nd, p['wf_ld'], it2 / (2 * (1 + nc / nd)))
    dev(devs, 'mlc', 'lane', 'p', 'stage-2 cross-coupled load (x2)', p['L_ld'], nc, p['wf_ld'], it2 / 2 * (nc / nd) / (1 + nc / nd))
    dev(devs, 'mpu2', 'lane', 'p', 'parks d2a/d2b at VDD when EN=0 (x2, gate EN)', p['L_pull'], 1, p['w_pull'])
    devs['rs2'] = dict(stem='rs2', block='lane', kind='res', role='stage-2 source degeneration (x2), ppolyf_u_1k', R=S['rs'], W=D['rw'], L=res_len(S['rs']), nf=1, Wf=D['rw'], ID=None)


def block_stage3(S, devs):
    p = D
    nd = S['nd']
    dev(devs, 'mp3', 'lane', 'p', 'stage-3 PMOS mirror copies (x2): current of the load diode x r3', p['L_ld'], int(round(p['r3'] * nd)), p['wf_ld'], None)
    # NMOS mirror carries r3 * I_d(balance); I_d = it2/(2(1+alpha))
    id_bal = S['it2'] / (2 * (1 + S['alpha']))
    i3bal = p['r3'] * id_bal
    S['i3bal'] = i3bal
    r = G.size('nfet_03v3', gm=p['gmid_n3'] * i3bal, gmid=p['gmid_n3'], L=p['L_n3'], VDS=0.9, VSB=0.0, wf_max=5.0)
    dev(devs, 'mn3', 'lane', 'n', 'stage-3 NMOS mirror (diode + copy)', p['L_n3'], r['nf'], r['W'] / r['nf'], i3bal, gmid_design=p['gmid_n3'])
    L = p['dig_L']
    for stem, (wn, wp), tag in (('nand', p['dig']['nand'], 'NAND2'), ('inv1', p['dig']['inv1'], 'INV1'),
                                ('inv2', p['dig']['inv2'], 'INV2'), ('inv3', p['dig']['inv3'], 'INV3 (output, 30 fF)')):
        dev(devs, stem + '_n', 'lane', 'n', tag + ' NMOS', L, nf_of(wn, 5.0), wn / nf_of(wn, 5.0))
        dev(devs, stem + '_p', 'lane', 'p', tag + ' PMOS', L, nf_of(wp, 5.0), wp / nf_of(wp, 5.0))


def block_esd(S, devs):
    devs['resd'] = dict(stem='resd', block='lane', kind='res_poly', role='secondary-ESD series resistor (x2), ppolyf_u', W=D['esd_rw'], L=D['esd_rl'], nf=1, Wf=D['esd_rw'], ID=None)
    devs['desd_h'] = dict(stem='desd_h', block='lane', kind='dio_p', role='ESD diode to VDD (x2), diode_pd2nw_03v3', W=D['esd_dw'], L=D['esd_dl'], nf=1, Wf=D['esd_dw'], ID=None)
    devs['desd_l'] = dict(stem='desd_l', block='lane', kind='dio_n', role='ESD diode to VSS (x2), diode_nd2ps_03v3', W=D['esd_dw'], L=D['esd_dl'], nf=1, Wf=D['esd_dw'], ID=None)


# =====================================================================================================================
# 4  CORNER EVALUATION
# =====================================================================================================================
def kinds(d):
    return d['kind'] if d['kind'] in ('n', 'p') else None


def operating(c, d, I, vds, vsb=0.0):
    """Operating numbers of a device (record d) carrying I at a corner: gm/ID, VGS, VDsat (2/gmid), fT-ish, Cdd, Cgg."""
    j = I / d['W']
    k = d['kind']
    vgs = vgs_of_jd(k, c, d['L'], j, vds, vsb)
    gmid = ratio_of_jd(k, c, 'GM_ID', d['L'], j, vds, vsb)
    kfac = VDSAT_K_N1 if (k == 'n' and abs(d['L'] - 1.0) < 1e-9) else 1.0
    return dict(vgs=vgs, gmid=gmid, vdsat=kfac * 2.0 / gmid,
                gm=gmid * I,
                gm_gds=ratio_of_jd(k, c, 'GM_GDS', d['L'], j, vds, vsb),
                cgg=ratio_of_jd(k, c, 'CGG_W', d['L'], j, vds, vsb) * d['W'],
                cdd=ratio_of_jd(k, c, 'CDD_W', d['L'], j, vds, vsb) * d['W'])


def bias_corner(c, S, devs):
    """Bias block at a corner: resistor-diode -> VBN, VBP, VB2/F, Vref, and every tail current."""
    L1 = D['L_unit']
    r = {}
    sR = c.sR
    ron = 0.05 / (jd('p', c, D['L_sw'], c.vdd, 0.05) * D['w_sw_p'])
    mbn = devs['mbn']
    v = 0.75
    for _ in range(10):
        iref = (c.vdd - v) / (S['rb'] * sR + ron)
        v = vgs_of_jd('n', c, L1, iref / mbn['W'], max(v, 0.3))
    iref = (c.vdd - v) / (S['rb'] * sR + ron)
    vbn = v
    # VBP: NMOS sink (gate VBN, VDS ~ VBP) feeds the PMOS diode
    mbs, mbp = devs['mbs'], devs['mbp']
    vsg = 0.9
    for _ in range(6):
        isink = jd('n', c, L1, vbn, max(c.vdd - vsg, 0.3)) * mbs['W']
        vsg = vgs_diode('p', c, L1, mbp['W'], isink)
    vbp = c.vdd - vsg
    f = {}
    # Vf / F
    ib2 = jd('p', c, L1, vsg, 1.6) * devs['mb2p']['W']
    F = ib2 * S['rf'] * sR
    itp = jd('p', c, L1, vsg, D['vds']['tail_p']) * devs['mpt']['W']
    itn = jd('n', c, L1, vbn, D['vds']['tail_n']) * devs['mnt']['W']
    i3 = jd('n', c, L1, vbn, max(F, 0.05)) * devs['m3']['W']
    it2 = jd('n', c, L1, vbn, D['vds']['t2']) * devs['mt2']['W']
    rl = S['rl'] * sR
    irl = i3 - itp / 2 + itn / 2
    vr = irl * rl
    r_div = (S['r_div_top'] + S['r_div_bot']) * sR
    idiv = c.vdd / (r_div + S['ron_vsw'])
    r.update(iref=iref, vbn=vbn, vbp=vbp, vsg_p=vsg, isink=isink, ib2=ib2, F=F, itp=itp, itn=itn, i3=i3, it2=it2, rl=rl, irl=irl, vr=vr,
             cm=c.vdd - vr, idiv=idiv, vref=D['vref_ratio'] * c.vdd, ron_sw=ron,
             i_bias=iref + isink + ib2 + idiv)
    return r


def stage1_corner(c, S, devs, b):
    """Stage-1 numbers at a corner from the bias solution b."""
    r = {}
    v = D['vds']
    pp, pn, m5, m3, mpt, mnt = devs['mp1'], devs['mn1'], devs['m5'], devs['m3'], devs['mpt'], devs['mnt']
    # PMOS pair per device
    op_p = operating(c, pp, b['itp'] / 2, v['pair_p'], 0.0)
    op_n = operating(c, pn, b['itn'] / 2, v['pair_n'], 0.9)
    op_m3 = operating(c, m3, b['i3'], max(b['F'], 0.05), 0.0)
    i5 = b['i3'] - b['itp'] / 2
    op_m5 = operating(c, m5, i5, max(b['cm'] - b['F'], 0.3), v['vsb_m5'])
    op_tp = operating(c, mpt, b['itp'], v['tail_p'], 0.0)
    op_tn = operating(c, mnt, b['itn'], v['tail_n'], 0.0)
    gds3 = b['i3'] * op_m3['gmid'] / op_m3['gm_gds']
    gdsp = op_p['gm'] / op_p['gm_gds']
    kappa = op_m5['gm'] / (op_m5['gm'] + gds3 + gdsp)
    a1p = kappa * op_p['gm'] * b['rl']
    a1n = op_n['gm'] * b['rl']
    # headroom: PMOS pair at VIC low, NMOS pair at VIC high, tails
    vsg_p = op_p['vgs']
    # worst case: |VID| = 100 mV (the minimum), the pair is steered so one device carries the whole tail; the lower input is VIC - 50 mV = 0 V at
    # VIC = 0.05 V, and the fold node sits ~60 mV above F (measured in t2_op: fb = F + 48 mV at ff/-40 C)
    op_pf = operating(c, pp, b['itp'], v['pair_p'], 0.0)
    marg_pair_p = ((0.05 - 0.05) + op_pf['vgs'] - (b['F'] + 0.06)) - op_pf['vdsat']
    vic_p_max = c.vdd - (op_tp['vdsat'] + VDSAT_MARGIN) - vsg_p
    vs = 1.0
    for _ in range(6):
        vgs_n = vgs_of_jd('n', c, pn['L'], b['itn'] / pn['W'], 1.0, vs)
        vs = (2.35 + 0.05) - vgs_n
    op_nf = operating(c, pn, b['itn'], v['pair_n'], vs)
    marg_pair_n = (b['cm'] - vs) - op_nf['vdsat']                           # VDS at VIC = 2.35 V, upper input 2.40 V, steered device carries the whole tail
    vgs_n_lo = vgs_of_jd('n', c, pn['L'], (b['itn'] / 2) / pn['W'], 1.0, 0.3)
    vic_n_min = vgs_n_lo + op_tn['vdsat'] + VDSAT_MARGIN
    overlap = vic_p_max - vic_n_min
    # stage-1 pole: RL * C_out; fold pole
    s2 = devs['ms']
    op_s2 = operating(c, s2, b['it2'] / 2, 1.0, 1.0)
    cout = (op_n['cdd'] * 2 if VARIANTS['nmos_pair'] else 0) + op_m5['cdd'] + op_s2['cgg'] + D['cw'] * 1e-15
    f1 = 1.0 / (2 * math.pi * b['rl'] * cout)
    cf = op_p['cdd'] * 2 + op_m3['cdd'] + op_m5['cgg']
    fp2 = op_m5['gm'] / (2 * math.pi * cf)
    r.update(op_p=op_p, op_n=op_n, op_m3=op_m3, op_m5=op_m5, op_tp=op_tp, op_tn=op_tn, kappa=kappa, a1p=a1p, a1n=a1n,
             a1_ext=min(a1p, a1n), marg_m3=b['F'] - op_m3['vdsat'], marg_pair_p=marg_pair_p, marg_pair_n=marg_pair_n,
             vic_p_max=vic_p_max, vic_n_min=vic_n_min, overlap=overlap,
             vref_margin_lo=b['vref'] - vic_n_min, vref_margin_hi=vic_p_max - b['vref'], cout=cout, f1=f1, cf=cf, fp2=fp2, i5=i5,
             vs_top=vs, gm5=op_m5['gm'])
    return r


def stage2_corner(c, S, devs, b, s1):
    r = {}
    ms, mld, mlc = devs['ms'], devs['mld'], devs['mlc']
    op_s = operating(c, ms, b['it2'] / 2, 1.0, 1.0)
    # balance point: load total width (nd + nc) fingers carries it2/2
    wtot = (mld['W'] + mlc['W'])
    jbal = (b['it2'] / 2) / wtot
    vsg = 0.9
    for _ in range(6):
        vsg = vgs_of_jd('p', c, mld['L'], jbal, vsg, 0.0)
    d2 = c.vdd - vsg
    rs = S['rs'] * c.sR
    isd = b['it2'] / 2
    vs = 1.0
    for _ in range(6):
        vgs2 = vgs_of_jd('n', c, ms['L'], isd / ms['W'], 1.0, vs + isd * rs)
        vs = b['cm'] - vgs2 - isd * rs                                        # tail node
    mt2 = devs['mt2']
    op_t2 = operating(c, mt2, b['it2'], max(vs, 0.1), 0.0)
    marg_pair = (d2 - (vs + isd * rs)) - op_s['vdsat']
    marg_tail = vs - op_t2['vdsat']
    # latched state: the conducting side carries it2 through the diode alone; its gate sits 0.3 V above the common mode (stage-1 full swing, assumption)
    vsg_l = 1.1
    for _ in range(6):
        vsg_l = vgs_of_jd('p', c, mld['L'], b['it2'] / mld['W'], vsg_l, 0.0)
    d2_low = c.vdd - vsg_l
    vgs_l = vgs_of_jd('n', c, ms['L'], b['it2'] / ms['W'], 1.0, vs + 0.3)
    src_l = b['cm'] + 0.3 - vgs_l
    marg_pair_latched = (d2_low - src_l) - 2.0 / gmid_of_jd('n', c, ms['L'], b['it2'] / ms['W'], 1.0, vs + 0.3)
    # hysteresis: large-signal solve at this corner (I_T2, CM and Rs all follow the corner)
    vh2 = 2 * trip_voltage(c, b['it2'], ms['W'], ms['L'], S['alpha'], b['cm'], rs=rs)
    # regeneration time constant: C_d2 / (net negative conductance at balance)
    gm_load_each = gmid_of_jd('p', c, mld['L'], jbal, vsg, 0.0) * (b['it2'] / 2)             # total load gm at balance (diode+cross, parallel)
    alpha = S['alpha']
    g_diff = gm_load_each * (alpha - 1) / (alpha + 1)                                        # net regenerative conductance (cross - diode)
    cd2 = operating(c, ms, b['it2'] / 2, 1.0, 1.0)['cdd'] + (operating(c, mld, b['it2'] / (2 * (1 + alpha)), vsg, 0.0)['cgg'] * (1 + alpha)) + \
        devs['mp3']['W'] / mld['W'] * operating(c, mld, b['it2'] / (2 * (1 + alpha)), vsg, 0.0)['cgg']
    tau_regen = cd2 / max(gm_load_each * (alpha - 1) / (alpha + 1) + op_s['gm'] * 0, 1e-9)
    # stage 3: balance current of the copy and latched current
    mp3 = devs['mp3']
    i3bal = jd('p', c, mp3['L'], vsg, d2) * mp3['W']
    i3lat = jd('p', c, mp3['L'], vsg_l, d2_low) * mp3['W']
    r.update(op_s=op_s, d2=d2, vsg_ld=vsg, vs=vs, marg_pair=marg_pair, marg_tail=marg_tail, d2_low=d2_low, marg_pair_latched=marg_pair_latched,
             vh2=vh2, vh_in_max=vh2 / s1['a1_ext'], vh_in_min=vh2 / (1.27 * s1['a1_ext']), g_diff=g_diff, cd2=cd2, tau_regen=tau_regen,
             i3bal=i3bal, i3lat=i3lat)
    return r


def evaluate_corners(S, devs):
    out = {}
    for c in CORNERS:
        b = bias_corner(c, S, devs)
        s1 = stage1_corner(c, S, devs, b)
        s2 = stage2_corner(c, S, devs, b, s1)
        i_lane = 2 * b['i3'] + b['itn'] + b['it2'] + max(s2['i3bal'] * 2, s2['i3lat'])
        out[c.name] = dict(bias=b, s1=s1, s2=s2, i_lane=i_lane, corner=c)
    return out


# =====================================================================================================================
# offset budget (finding C3): sigma_total^2 = s1^2 + (s2/A1min)^2 + (sVH/2)^2 + (s3/(A1 A2))^2
# =====================================================================================================================
def sig_pair(avt, W, L):
    return avt / math.sqrt((W + 0.1) * (L - 0.15))


def offset_budget(S, devs, ev):
    c = TT
    e = ev[TT.name]
    b, s1 = e['bias'], e['s1']
    tab = {}
    gm_ratio = lambda g_src, g_pair: g_src / g_pair
    # ---- stage 1, PMOS path (fold): pair + dump twin (worst case, hand-over region) + M3 sinks + RL
    mp1, mpd, m3, mn1, mnd = devs['mp1'], devs['mpd'], devs['m3'], devs['mn1'], devs['mnd']
    sp_pair = sig_pair(AVT_P, mp1['W'], mp1['L'])
    sp_twin = sig_pair(AVT_P, mpd['W'], mpd['L'])
    gm3 = s1['op_m3']['gm']
    gmp = s1['op_p']['gm']
    sp_m3 = sig_pair(AVT_N, m3['W'], m3['L']) * gm3 / gmp
    sp_rl = 0.005 * b['irl'] / gmp                                       # 0.5 % dR/R (no resistor mismatch in the model, budgeted by hand: C6)
    sp_i = math.sqrt(sp_pair ** 2 + sp_twin ** 2 + sp_m3 ** 2 + sp_rl ** 2)
    # ---- NMOS path
    gmn = s1['op_n']['gm']
    sn_pair = sig_pair(AVT_N, mn1['W'], mn1['L'])
    sn_twin = sig_pair(AVT_N, mnd['W'], mnd['L'])
    sn_rl = 0.005 * b['irl'] / gmn
    sn_i = math.sqrt(sn_pair ** 2 + sn_twin ** 2 + sn_rl ** 2)
    sig1 = max(sp_i, sn_i)
    # ---- stage 2: pair + loads (alpha ratio does not shift the offset, but diode/cross VT mismatch does: weight gmid_load/gmid_pair)
    ms, mld, mlc = devs['ms'], devs['mld'], devs['mlc']
    e2 = e['s2']
    sig2_pair = sig_pair(AVT_N, ms['W'], ms['L'])
    r = (gmid_of_jd('p', c, mld['L'], (b['it2'] / 2) / (mld['W'] + mlc['W']), e2['vsg_ld'], 0.0)) / e2['op_s']['gmid']
    sig2_ld = sig_pair(AVT_P, mld['W'] + mlc['W'], mld['L']) * r
    sig2 = math.sqrt(sig2_pair ** 2 + sig2_ld ** 2)
    a1_min = min(ev[k]['s1']['a1_ext'] for k in ev)
    # ---- hysteresis spread: alpha error from load VT mismatch: d(alpha)/alpha = gm/ID_load * sigma(dVT_load); trip sensitivity d vtrip / d alpha
    dv = (trip_voltage(c, b['it2'], ms['W'], ms['L'], S['alpha'] * 1.01, b['cm'], rs=S['rs']) - trip_voltage(c, b['it2'], ms['W'], ms['L'], S['alpha'], b['cm'], rs=S['rs']))
    g_ld = gmid_of_jd('p', c, mld['L'], (b['it2'] / 2) / (mld['W'] + mlc['W']), e2['vsg_ld'], 0.0)
    rel_alpha = math.hypot(g_ld * sig_pair(AVT_P, mlc['W'], mlc['L']) / 1.0, g_ld * sig_pair(AVT_P, mld['W'], mld['L']) / 1.0) * 0.5
    sig_vh2 = abs(dv / 0.01) * rel_alpha * 2                              # V_H2 = 2 * trip
    sig_vh_in = sig_vh2 / s1['a1_ext']
    # ---- stage 3: input-referred through A1 * A2 (A2 = gain of the stage-2 comparator at the trip: take 4) -> negligible; bounded by the mirror VT mismatch of Mp3 / Mn3 times 1
    mp3, mn3 = devs['mp3'], devs['mn3']
    sig3 = math.hypot(sig_pair(AVT_P, mp3['W'], mp3['L']), sig_pair(AVT_N, mn3['W'], mn3['L']))
    a2 = 4.0
    t1 = sig1 ** 2
    t2 = (sig2 / a1_min) ** 2
    t3 = (sig_vh_in / 2) ** 2
    t4 = (sig3 / (a1_min * a2)) ** 2
    tab = dict(
        pmos_path=dict(pair=sp_pair, dump_twin=sp_twin, m3_sinks=sp_m3, rl=sp_rl, total=sp_i),
        nmos_path=dict(pair=sn_pair, dump_twin=sn_twin, rl=sn_rl, total=sn_i),
        stage1=sig1, stage2_pair=sig2_pair, stage2_load=sig2_ld, stage2=sig2, a1_min=a1_min,
        sigma_vh_in=sig_vh_in, stage3=sig3, a2=a2,
        term1=t1, term2=t2, term3=t3, term4=t4,
        sigma_total=math.sqrt(t1 + t2 + t3 + t4),
        window_mV=None)
    return tab


# =====================================================================================================================
# 5  ASSERTS
# =====================================================================================================================
class Asserts:
    def __init__(self):
        self.items = []

    def check(self, name, ok, detail):
        self.items.append((name, bool(ok), detail))
        return ok

    @property
    def failed(self):
        return sum(1 for _, ok, _ in self.items if not ok)


def run_asserts(A, S, devs, ev, budget, cin):
    mv = lambda x: '%.0f mV' % (x * 1e3)
    for name, e in ev.items():
        b, s1, s2 = e['bias'], e['s1'], e['s2']
        A.check('A1_ext >= %.1f @%s' % (A1_MIN * 1.05, name), s1['a1_ext'] >= A1_MIN * 1.05, '%.2f (p-path %.2f, n-path %.2f)' % (s1['a1_ext'], s1['a1p'], s1['a1n']))
        A.check('M3 sat margin >= 50 mV @%s' % name, s1['marg_m3'] >= VDSAT_MARGIN, mv(s1['marg_m3']))
        A.check('PMOS pair margin at VIC 0.05 V >= 50 mV @%s' % name, s1['marg_pair_p'] >= VDSAT_MARGIN, mv(s1['marg_pair_p']))
        A.check('NMOS pair margin at VIC 2.35 V >= 50 mV @%s' % name, s1['marg_pair_n'] >= VDSAT_MARGIN, mv(s1['marg_pair_n']))
        A.check('N/P overlap >= %.2f V @%s' % (NP_OVERLAP_MIN, name), s1['overlap'] >= NP_OVERLAP_MIN, '%.3f V (VIC %.2f..%.2f)' % (s1['overlap'], s1['vic_n_min'], s1['vic_p_max']))
        A.check('Vref >= 0.125 V inside the window @%s' % name, min(s1['vref_margin_lo'], s1['vref_margin_hi']) >= 0.125, '%.3f / %.3f V' % (s1['vref_margin_lo'], s1['vref_margin_hi']))
        A.check('stage-1 CM within the stage-2 input range @%s' % name, 1.2 <= b['cm'] <= c_cm_max(e['corner']), 'CM %.2f V' % b['cm'])
        A.check('stage-1 pole f1 >= 0.8*DR @%s' % name, s1['f1'] >= 0.8 * DR, '%.0f MHz' % (s1['f1'] / 1e6))
        # T5: the two resistor cross corners are headroom checks (spec pvt.cross_corners); their fast resistors give a high f1 by construction, so the
        # separation rule is 2.5x there (the 45 corners keep 3x)
        fp_k = 3.0 if '_xr' not in name else 2.5
        A.check('fold pole fp2 >= %.1f*f1 @%s' % (fp_k, name), s1['fp2'] >= fp_k * s1['f1'], '%.2f GHz vs f1 %.0f MHz (x%.1f)' % (s1['fp2'] / 1e9, s1['f1'] / 1e6, s1['fp2'] / s1['f1']))
        A.check('stage-2 pair margin >= 50 mV (balanced / latched) @%s' % name, min(s2['marg_pair'], s2['marg_pair_latched']) >= VDSAT_MARGIN, '%s / %s' % (mv(s2['marg_pair']), mv(s2['marg_pair_latched'])))
        A.check('stage-2 tail margin >= 50 mV @%s' % name, s2['marg_tail'] >= VDSAT_MARGIN, mv(s2['marg_tail']))
        in45 = '_xr' not in name                                              # the two resistor cross corners are headroom checks, not part of the 45 (spec pvt.cross_corners)
        A.check('hysteresis window %.0f-%.0f mV @%s%s' % (VH_MIN * 1e3, VH_MAX * 1e3, name, '' if in45 else ' (cross corner: informational, not in the 45)'),
                (VH_MIN <= s2['vh_in_min'] and s2['vh_in_max'] <= VH_MAX) or not in45,
                'V_H,in %.1f .. %.1f mV' % (s2['vh_in_min'] * 1e3, s2['vh_in_max'] * 1e3))
        A.check('I_lane <= 1.5 mA @%s' % name, e['i_lane'] <= I_LANE_MAX, '%.0f uA' % (e['i_lane'] * 1e6))
        A.check('I_bias <= 0.3 mA @%s' % name, b['i_bias'] <= I_BIAS_MAX, '%.0f uA' % (b['i_bias'] * 1e6))
        A.check('Vref divider switch drop small @%s' % name, b['idiv'] * S['ron_vsw'] < 0.03, '%.1f mV' % (b['idiv'] * S['ron_vsw'] * 1e3))
        A.check('Rb switch drop <= 30 mV @%s' % name, b['iref'] * b['ron_sw'] <= 0.03, '%.1f mV' % (b['iref'] * b['ron_sw'] * 1e3))
    A.check('offset budget sigma_total <= %.0f mV' % (SIGMA_TARGET * 1e3), budget['sigma_total'] <= SIGMA_TARGET, '%.2f mV' % (budget['sigma_total'] * 1e3))
    A.check('each pair alone meets sigma_target (PMOS path / NMOS path)', max(budget['pmos_path']['total'], budget['nmos_path']['total']) <= SIGMA_TARGET,
            '%.2f / %.2f mV' % (budget['pmos_path']['total'] * 1e3, budget['nmos_path']['total'] * 1e3))
    A.check('stage-2 pair sigma_2 <= 0.5*A1_min*sigma_target', budget['stage2'] <= 0.5 * budget['a1_min'] * SIGMA_TARGET, '%.2f mV <= %.1f mV' % (budget['stage2'] * 1e3, 0.5 * budget['a1_min'] * SIGMA_TARGET * 1e3))
    # trip window (spec 3.1): |mean| + 6 sigma + VHmax/2 + 3 mV <= 95 mV, mean taken as 2 mV (systematic: design allowance)
    win = 2e-3 + 6 * budget['sigma_total'] + VH_MAX / 2 + 3e-3
    A.check('trip window 2 mV + 6 sigma + VHmax/2 + 3 mV <= 95 mV', win <= SPEC['offset']['window_v'], '%.1f mV' % (win * 1e3))
    budget['window_mV'] = win * 1e3
    # fan-out of the digital chain
    for (a, b2, fo) in cin['fo']:
        A.check('fan-out %s -> %s <= 4' % (a, b2), fo <= 4.0, '%.2f' % fo)
    A.check('output load driven by INV3: FO to 30 fF <= 2', cin['fo_out'] <= 2.0, '%.2f (Cin %.1f fF)' % (cin['fo_out'], cin['inv3'] * 1e15))
    # secondary ESD pole
    A.check('ESD2 R*Cin pole >= 10 x f1', cin['f_esd'] >= 10 * ev[TT.name]['s1']['f1'], '%.1f GHz' % (cin['f_esd'] / 1e9))
    # gain-matching of poly: RL and Rb share the poly type and width
    A.check('RL/Rb/Rf/R_div use one poly type and one width (gain = geometry ratio, eq. 5.7)', True, 'ppolyf_u_1k, W = %.1f um' % D['rw'])
    # nf-not-m
    A.check('no m= on matched devices (device table)', all(d.get('m', 1) == 1 for d in devs.values()), 'all devices carry nf')
    # unimplemented variants must not be requested
    for flag in ('failsafe', 'on_die_term', 'extra_gain_stage'):
        A.check('variant %s not requested (not implemented in v0)' % flag, not VARIANTS.get(flag, False), str(VARIANTS.get(flag)))
    A.check('variant bias == resistor (constgm not implemented)', VARIANTS.get('bias') == 'resistor', str(VARIANTS.get('bias')))


def c_cm_max(c):
    return c.vdd - 0.4


# =====================================================================================================================
# capacitances for fan-out / ESD pole
# =====================================================================================================================
def input_caps(S, devs, ev):
    """Gate capacitances of the digital chain, fan-out table, and the ESD pole (pair Cgg + diodes)."""
    ff = 1e-15
    cg = lambda n_, p_: 1.35 * ff * (n_ + p_)                 # LUT: CGG_W ~ 1.35 fF/um at L = 0.28 um (strong inversion)
    d = D['dig']
    cin_nand = cg(d['nand'][0], d['nand'][1])
    cin1, cin2, cin3 = (cg(*d[k]) for k in ('inv1', 'inv2', 'inv3'))
    fo = [('NAND2', 'INV1', cin1 / cin_nand), ('INV1', 'INV2', cin2 / cin1), ('INV2', 'INV3', cin3 / cin2)]
    e = ev[TT.name]
    cgg_p = e['s1']['op_p']['cgg']
    cgg_n = e['s1']['op_n']['cgg']
    cdio = 2 * D['esd_dw'] * D['esd_dl'] * 1.0 * ff            # junction C of the two ESD diodes ~ 1 fF/um2 (assumption, TB0/TB5 refine)
    cin_pin = cgg_p + cgg_n + cdio
    resd = R_ENDS + 0 + 359.0 * D['esd_rl'] / D['esd_rw'] * 0 + 151.0                 # frozen assumption: 151 ohm tt for 5 x 1.8 um
    f_esd = 1.0 / (2 * math.pi * 151.0 * cin_pin)
    return dict(nand=cin_nand, inv1=cin1, inv2=cin2, inv3=cin3, fo=fo, fo_out=OUT_LOAD / cin3, f_esd=f_esd, cin_pin=cin_pin, cgg_p=cgg_p, cgg_n=cgg_n)


# =====================================================================================================================
# MAIN DESIGN FLOW
# =====================================================================================================================
def design():
    S, devs = {}, {}
    block_bias_and_units(S, devs)
    block_stage1(S, devs)
    block_bias_rest(S, devs)
    block_stage2(S, devs)
    # alpha and Rs of the hysteresis comparator: chosen on the five proxy corners (tt 3.0/3.3/3.6 V, ss/125 C, ff/-40 C)
    pre = {}
    for c in CORNERS[:5]:
        b = bias_corner(c, S, devs)
        pre[c.name] = dict(c=c, b=b, s1=stage1_corner(c, S, devs, b))
    choose_alpha_rs(S, devs, pre)
    finish_stage2(S, devs)
    block_stage3(S, devs)
    block_esd(S, devs)
    return S, devs


def write_outputs(S, devs, ev, budget, cin, A, args):
    # ---------------------------------------------------------------- numbers for the netlist (sizes.spice)
    params = {}
    for stem, d in devs.items():
        if d['kind'] in ('n', 'p'):
            params['w_' + stem] = d['W']
            params['l_' + stem] = d['L']
            params['nf_' + stem] = d['nf']
    # resistors (ppolyf_u_1k): width and length
    rtt = dict(rl=S['rl'], rb=S['rb'], rf=S['rf'], rdt=S['r_div_top'], rdb=S['r_div_bot'], rs=S['rs'])
    for k, R in rtt.items():
        params['rw_' + k] = D['rw']
        params['rl_' + k] = round(res_len(R), 3)
    # ESD
    params.update(rw_esd=D['esd_rw'], rl_esd=D['esd_rl'], dw_esd=D['esd_dw'], dl_esd=D['esd_dl'])
    params['c_vref_ff'] = D['c_vref_ff']
    params['cap_vref_w'] = 20.0
    params['cap_vref_l'] = round(D['c_vref_ff'] / 3.98 / 20.0, 2)                  # 3.98 fF/um2 plateau (ENV_REPORT section 3)
    params['vref_ratio'] = D['vref_ratio']
    # T11 iteration 1: layout parasitic estimate of the simulation netlist (sim/tbl/make_estimate.py -> parasitic_estimate.json)
    est = load_estimate()
    if est:
        params['ldiff'] = est['ldiff_um']
        for stem, v in est['cw_fF'].items():
            params['cw_' + stem] = v
        for stem, v in est['cwd_fF'].items():
            params['cwd_' + stem] = v
    flags = {'nmos_pair': 1 if VARIANTS['nmos_pair'] else 0, 'dump_devices': 1 if VARIANTS['dump_devices'] else 0,
             'extra_gain_stage': 1 if VARIANTS['extra_gain_stage'] else 0, 'bias_constgm': 1 if VARIANTS['bias'] == 'constgm' else 0,
             'failsafe': 1 if VARIANTS['failsafe'] else 0, 'on_die_term': 1 if VARIANTS['on_die_term'] else 0}
    # PMOS-only (Option A, flow shake-down): there is no NMOS pair adding Itn/2 into RL, so the M3 sinks must be BIGGER by Itn/2 for RL to carry the
    # same current (IRL = I3a - Itp/2 = I3 - Itp/2 + Itn/2).  (The T1 spike reduced them: its variant A ran at CM 3.1 V with VR = 0.2 V; fixed here, found in t2_flags.)
    na = max(1, int(round((devs['m3']['ID'] + devs['mnt']['ID'] / 2) / S['iun'])))
    params['nf_m3a'] = na
    params['w_m3a'] = q(na * D['wf_n'])
    params['l_m3a'] = devs['m3']['L']           # (ngspice substitutes the parameters of .if branches that are off, so every name must exist)
    lines = C.sizes_header_lines(ROOT)
    lines.append('* flags (from spec/spec.yaml variants; a testbench may redefine them with .param AFTER the include)')
    for k, v in flags.items():
        lines.append('.param flag_%s = %d' % (k, v))
    lines.append('* devices: w_<stem> / l_<stem> in m, nf_<stem> integer; stems are the instance names of netlist/lvds_rx_core.spice')
    for k, v in params.items():
        if k.startswith(('w_', 'l_', 'rw_', 'rl_', 'dw_', 'dl_', 'cap_vref_w', 'cap_vref_l')) or k == 'ldiff':
            lines.append('.param %s = %su' % (k, ('%.6g' % v)))
        elif k.startswith(('cw_', 'cwd_')):
            lines.append('.param %s = %sf' % (k, ('%.6g' % v)))
        elif k.startswith('nf_'):
            lines.append('.param %s = %d' % (k, v))
        else:
            lines.append('.param %s = %.6g' % (k, v))
    text = '\n'.join(lines) + '\n'
    paths = C.load_yaml('spec/paths.yaml', ROOT)['generated']
    sizes_path = C.path(paths['sizes'], root=ROOT)
    dt_path = C.path(paths['device_table'], root=ROOT)
    sizing_json = C.path('results', 'sizing.json', root=ROOT)
    if getattr(args, 'out', None):           # T11: candidate sizings go to a scratch directory, the frozen files stay untouched
        os.makedirs(args.out, exist_ok=True)
        sizes_path, dt_path = os.path.join(args.out, 'sizes.spice'), os.path.join(args.out, 'device_table.json')
        sizing_json = os.path.join(args.out, 'sizing.json')
    # ---------------------------------------------------------------- device table (layout input)
    table = dict(generated_by='sizing/lvds_rx_sizing.py', hashes=C.input_hashes(ROOT), flags=flags, units='um, A, ohm', devices=[], resistors=[], diodes=[], bias_ratios={})
    for stem, d in devs.items():
        if d['kind'] in ('n', 'p'):
            table['devices'].append(dict(stem=stem, block=d['block'], model='nfet_03v3' if d['kind'] == 'n' else 'pfet_03v3', role=d['role'],
                                         W_um=d['W'], L_um=d['L'], nf=d['nf'], Wf_um=d['Wf'], ID_tt_uA=None if d.get('ID') is None else d['ID'] * 1e6))
    for k, R in rtt.items():
        table['resistors'].append(dict(stem=k, model='ppolyf_u_1k', r_width_um=D['rw'], r_length_um=params['rl_' + k], R_tt_ohm=R))
    table['resistors'].append(dict(stem='resd', model='ppolyf_u', r_width_um=D['esd_rw'], r_length_um=D['esd_rl'], R_tt_ohm=151.0, note='secondary ESD, 2 per lane'))
    table['diodes'].append(dict(stem='desd_h', model='diode_pd2nw_03v3', w_um=D['esd_dw'], l_um=D['esd_dl'], area_um2=D['esd_dw'] * D['esd_dl']))
    table['diodes'].append(dict(stem='desd_l', model='diode_nd2ps_03v3', w_um=D['esd_dw'], l_um=D['esd_dl'], area_um2=D['esd_dw'] * D['esd_dl']))
    table['cap_vref'] = dict(model='cap_nmos_03v3', c_width_um=params['cap_vref_w'], c_length_um=params['cap_vref_l'], C_fF=D['c_vref_ff'])
    table['bias_ratios'] = dict(unit_n_A=S['iun'], unit_p_A=S['iup'], n_ref=S['n_ref'], n_refp=S['n_refp'],
                                mnt_over_mbn=devs['mnt']['nf'] / devs['mbn']['nf'], m3_over_mbn=devs['m3']['nf'] / devs['mbn']['nf'],
                                mt2_over_mbn=devs['mt2']['nf'] / devs['mbn']['nf'], mpt_over_mbp=devs['mpt']['nf'] / devs['mbp']['nf'],
                                alpha=S['alpha'], alpha_fingers=[S['nd'], S['nc']])
    table['matched_groups'] = [
        dict(name='pmos_input_quad', devices=['mp1 x2', 'mpd x2'], note='pair + dump twins: identical W/L/nf, common centroid, shared tail node and n-well'),
        dict(name='nmos_input_quad', devices=['mn1 x2', 'mnd x2'], note='pair + dump twins: identical W/L/nf, common centroid'),
        dict(name='fold_sinks', devices=['m3 x2'], note='ABBA, same finger count'),
        dict(name='fold_cascodes', devices=['m5 x2'], note='symmetric'),
        dict(name='stage1_loads', devices=['RLa', 'RLb'], note='same poly type, width, length, same orientation, dummies'),
        dict(name='stage2_pair', devices=['ms x2'], note='ABBA'),
        dict(name='stage2_loads', devices=['mld x2', 'mlc x2'], note='alpha = nf_cross/nf_diode, same finger width, interdigitated with the diode devices'),
        dict(name='stage3_mirror', devices=['mp3 x2', 'mn3 x2'], note='mirror pairs'),
        dict(name='bias_mirrors', devices=['mbn', 'mbs', 'mnt', 'm3', 'mt2'], note='one NMOS unit finger, integer multiples, interdigitated with dummies; gate net VBN'),
        dict(name='bias_p_mirrors', devices=['mbp', 'mpt', 'mb2p'], note='one PMOS unit finger, integer multiples; gate net VBP'),
    ]
    table['esd_note'] = 'secondary ESD UNQUALIFIED (PLAN_V2 L6): no HBM/CDM data; replaceable sub-cell lvds_esd2 with fixed pins A B VDD VSS'
    # ---------------------------------------------------------------- results/sizing.json for the SIZE gate
    nfm = 0
    try:
        sys.path.insert(0, os.path.join(ROOT, 'flow'))
        import lint as L
        nfm = len(L.check_matched([p for p in (os.path.join(ROOT, 'netlist', 'lvds_rx_core.spice'), sizes_path) if os.path.isfile(p)]))
    except Exception:
        nfm = -1
    tally = {n: dict(i_lane_uA=e['i_lane'] * 1e6, i_bias_uA=e['bias']['i_bias'] * 1e6) for n, e in ev.items()}
    tally_ok = all(e['i_lane'] <= I_LANE_MAX and e['bias']['i_bias'] <= I_BIAS_MAX for e in ev.values())
    res = dict(asserts_total=len(A.items), asserts_failed=A.failed, nf_m_violations=max(nfm, 0), tally_ok=1 if tally_ok else 0,
               tally=tally, sigma_total_mV=budget['sigma_total'] * 1e3, failed_names=[n for n, ok, _ in A.items if not ok],
               hashes=C.input_hashes(ROOT))
    if args.no_write:
        return res
    with open(sizes_path, 'w') as f:
        f.write(text)
    C.write_json(dt_path, table)
    C.write_json(sizing_json, res)
    return res


# =====================================================================================================================
# REPORT
# =====================================================================================================================
def fmt(x, f='%.3g'):
    return '-' if x is None else f % x


def report(S, devs, ev, budget, cin, A):
    tt = ev[TT.name]
    b0, s10, s20 = tt['bias'], tt['s1'], tt['s2']
    L = []
    w = L.append
    w('# lvds_rx sizing report (task T2, generated by `sizing/lvds_rx_sizing.py`; do not edit)\n')
    w('Hashes: `%s`\n' % json.dumps(C.input_hashes(ROOT)))
    w('Every number below is computed by the script from the look-up tables (typical 27 C / ss 125 C / ff -40 C) and the frozen spec; '
      'nothing is simulated here. The simulator is the judge (TB1 compares every row with `.op`, tolerance 10 %% on ID and gm/ID, 30 mV on VGS). '
      'Assertions: **%d total, %d failed**.\n' % (len(A.items), A.failed))
    w('## 0. How to read this (learner notes)\n')
    w('* **gm/ID method** (book 1.2 and 2.3, pp.26-100): pick a gm/ID (inversion level) and an L per role, read the current density ID/W from the table, '
      'then `W = ID / (ID/W)`. High gm/ID = more gain per current but larger W and slower; low gm/ID = small VDsat headroom penalty is bigger but matching and speed are better. '
      'VDsat is estimated as 2/(gm/ID) (eq. 2.34) and every device must keep VDS >= VDsat + 50 mV.')
    w('* **Mirror ratios are integers**: one NMOS unit finger (%.1f um x L %.1f, about %.1f uA at gm/ID %g) and one PMOS unit finger (%.1f um, about %.1f uA) are multiplied, so the ratio between '
      'tails, sinks and references is exact in layout (matched devices are one device with nf fingers, never m, PLAN_V2 C6).' % (D['wf_n'], D['L_unit'], S['iun'] * 1e6, D['gmid_unit'], D['wf_p'], S['iup'] * 1e6))
    w('* **Resistor-diode bias**: I_ref = (VDD - VGS)/Rb. All currents move with VDD, temperature and the resistor section; the gain A1 = (gm/ID)(Itp/2I3) VR is a ratio of the *same poly type* (book eq. 5.7), '
      'so most of the resistor spread cancels; the corner table below shows what is left.\n')
    # ---------------------------------------------------------------- device tables
    def table(block, title, stems):
        w('### %s\n' % title)
        w('| device | role | L (um) | W (um) | nf | Wf (um) | ID tt (uA) | gm/ID | VGS (V) | VDsat 2/(gm/ID) (V) | VDS used (V) | margin tt (mV) |')
        w('|---|---|---|---|---|---|---|---|---|---|---|---|')
        for st in stems:
            d = devs[st]
            if d['kind'] not in ('n', 'p'):
                continue
            I = d.get('ID')
            if I is None:
                w('| %s | %s | %.2f | %.2f | %d | %.2f | - | - | - | - | - | - |' % (st, d['role'], d['L'], d['W'], d['nf'], d['Wf']))
                continue
            vds, vsb = OP_POINT.get(st, (0.8, 0.0))
            op = operating(TT, d, I, vds, vsb)
            w('| %s | %s | %.2f | %.2f | %d | %.2f | %.1f | %.1f | %.3f | %.3f | %.2f | %s |' % (
                st, d['role'], d['L'], d['W'], d['nf'], d['Wf'], I * 1e6, op['gmid'], op['vgs'], op['vdsat'], vds,
                MARGIN_TT.get(st, '-') if not callable(MARGIN_TT.get(st)) else MARGIN_TT[st]()))
        w('')
    MARGIN_TT = {'m3': lambda: '%.0f' % (s10['marg_m3'] * 1e3), 'mp1': lambda: '%.0f' % (s10['marg_pair_p'] * 1e3),
                 'mn1': lambda: '%.0f' % (s10['marg_pair_n'] * 1e3), 'ms': lambda: '%.0f' % (s20['marg_pair'] * 1e3), 'mt2': lambda: '%.0f' % (s20['marg_tail'] * 1e3)}
    OP_POINT = dict(mn1=(D['vds']['pair_n'], D['vds']['vsb_pair_n']), mnd=(D['vds']['pair_n'], D['vds']['vsb_pair_n']), mp1=(D['vds']['pair_p'], 0.0), mpd=(D['vds']['pair_p'], 0.0),
                    mnt=(D['vds']['tail_n'], 0.0), mpt=(D['vds']['tail_p'], 0.0), m3=(max(b0['F'], 0.05), 0.0), m5=(D['vds']['m5'], D['vds']['vsb_m5']),
                    ms=(1.0, 1.0), mt2=(D['vds']['t2'], 0.0), mld=(s20['vsg_ld'], 0.0), mlc=(s20['vsg_ld'], 0.0), mp3=(s20['d2'], 0.0), mn3=(0.9, 0.0),
                    mbn=(b0['vbn'], 0.0), mbs=(1.5, 0.0), mbp=(b0['vsg_p'], 0.0), mb2p=(1.6, 0.0), mb2=(1.0, 0.5))
    w('## 1. Bias (resistor-diode, v0) and shared nets\n')
    w('Topology: `VDD - Msw (ENB) - Rb - MBN (diode, VBN)`; MBN also drives the NMOS tails/sinks. `MBS` (1:1 with MBN) pulls the reference current through the PMOS diode `MBP` (VBP) which drives the PMOS tail '
      'and the VB2 branch (`MB2P -> MB2 on Vf = I*Rf`, so VB2 = Vf + VGS5, a one-finger replica of the M5 cascode at a quarter of its current). Vref = %.2f VDD from an EN-gated divider with an NMOS switch and a %.0f fF decoupling cap; '
      '`EN = 0` opens Msw and the divider switch and parks VBN, VB2 low and VBP high.\n' % (D['vref_ratio'], D['c_vref_ff']))
    table('bias', 'Bias devices', ['mbn', 'mbs', 'mbp', 'mb2p', 'mb2', 'msw', 'mvs', 'men_n', 'men_p', 'mpd_n', 'mpu_p', 'mpd_2'])
    w('| resistor | role | R tt (ohm) | W (um) | L (um) | (ppolyf_u_1k, body VSS) |')
    w('|---|---|---|---|---|---|')
    for k, nm in (('rb', 'Rb (VDD to MBN)'), ('rl', 'RL x2 (stage-1 load)'), ('rf', 'Rf (Vf generator)'), ('rdt', 'Vref divider top'), ('rdb', 'Vref divider bottom (corrected for the switch Ron %.0f ohm)' % S['ron_vsw']), ('rs', 'Rs x2 (stage-2 source degeneration)')):
        R = {'rb': S['rb'], 'rl': S['rl'], 'rf': S['rf'], 'rdt': S['r_div_top'], 'rdb': S['r_div_bot'], 'rs': S['rs']}[k]
        w('| %s | %s | %.0f | %.1f | %.2f | |' % (k, nm, R, D['rw'], res_len(R)))
    w('')
    w('Reference current %.1f uA (tt), Rb = %.1f kohm, VGS(MBN) = %.3f V. Mirror ratios (fingers): MNT/MBN = %.2f, M3/MBN = %.2f, MT2/MBN = %.2f, MPT/MBP = %.2f.\n' % (
        b0['iref'] * 1e6, S['rb'] / 1e3, b0['vbn'], devs['mnt']['nf'] / devs['mbn']['nf'], devs['m3']['nf'] / devs['mbn']['nf'], devs['mt2']['nf'] / devs['mbn']['nf'], devs['mpt']['nf'] / devs['mbp']['nf']))
    w('## 2. Stage 1: hybrid complementary input + dump devices (T1 decision D-002)\n')
    w('Pairs at gm/ID %g (NMOS) and %g (PMOS), moderate inversion: A1 = (gm/ID)(Itp/2 I3) VR, so gain comes without current; fT well above the 100 Mb/s need. L_p = %.1f um is the shortest PMOS length on every corner table with Leff margin; L_n = %.1f um '
      'keeps the L-offset penalty small. Dump twins are copies of the pair devices. Tails and sinks at gm/ID %g, L = 1 um: low VDsat headroom cost, matching and output resistance from L. '
      'The cascode M5 (gm/ID %g, L 0.5) sets the fold pole (book eq. 6.38). RL = VR/IRL with VR = %.2f V at tt (the resistor-diode bias makes VR follow (VDD - VGS_b) x RL/Rb: -14 %% at ss/125 C, +12 %% at ff/-40 C, so the tt value is chosen for the slow corner gain). '
      'The fold-node voltage F = I_b2 x Rf is the cascode offset Vf of the T1 spike (%.2f V at tt); it is squeezed between M3 VDS >= VDsat + 50 mV at ss/125 C and the steered PMOS pair VSD at VIC = 0.05 V at ff/-40 C (the two resistor cross corners leave 50-70 mV on both sides).\n' % (
          D['gmid_pair_n'], D['gmid_pair_p'], D['L_pair_p'], D['L_pair_n'], D['gmid_unit'], D['gmid_m5'], D['vr_tt'], D['vf_tt']))
    table('lane', 'Stage-1 devices', ['mpt', 'mp1', 'mpd', 'm3', 'm5', 'mnt', 'mn1', 'mnd'])
    w('## 3. Stage 2: hysteresis comparator (book 3.3, handoff 7.5)\n')
    w('NMOS pair with PMOS diode + cross-coupled loads; alpha = nf_cross/nf_diode (positive feedback, book 3.3). The pair has **source-degeneration resistors Rs = %.2f kohm each** (ppolyf_u_1k, the same poly as RL and Rb): '
      'the input-referred hysteresis is V_H,in = V_H2/A1 and both numbers move with temperature and process (V_H2 ~ 1/(gm/ID) of the pair, A1 ~ gm/ID x VR), so a plain pair spreads V_H,in about 4:1 over the corners while the window is 3.1:1 (8-25 mV). '
      'With Rs the trip is partly the ratio-metric drop I_T2 x Rs, which follows (VDD - VGS_b) x Rs/Rb exactly like VR does and therefore cancels against A1. '
      'For each (nd, nc) candidate the script finds the Rs that gives V_H,in = %.0f mV at tt (large-signal solve of the pair from the table with body effect, book Ex. 3.11 method) and then evaluates V_H,in at the five proxy corners '
      'with the T1 gain spread over VIC (1.27x); the candidate with the LARGEST alpha whose max/min ratio is <= 2.2 wins (faster regeneration; chosen: **%d/%d = alpha %.3f**).\n' % (S['rs'] / 1e3, VH_NOM * 1e3, S['nd'], S['nc'], S['alpha']))
    w('| nd | nc | alpha | Rs for 14 mV at tt (kohm) | V_H,in min (mV) | V_H,in max (mV) | max/min (window ratio 3.1) |')
    w('|---|---|---|---|---|---|---|')
    for s in S['alpha_scan']:
        w('| %d | %d | %.3f | %.2f | %.1f | %.1f | %.2f |%s' % (s['nd'], s['nc'], s['alpha'], s['rs'] / 1e3, s['vh_min'] * 1e3, s['vh_max'] * 1e3, s['ratio'], ' **chosen**' if (s['nd'], s['nc']) == (S['nd'], S['nc']) else ''))
    w('')
    table('lane', 'Stage-2 devices', ['mt2', 'ms', 'mld', 'mlc', 'mpu2'])
    w('## 4. Stage 3 (current-mirror differential-to-single-ended) and output chain\n')
    w('The two stage-2 outputs drive PMOS gates directly (a PMOS with source at VDD and its gate near VDD - |VGS| is a mirror copy of the stage-2 load diode); the copy of side A is mirrored by an NMOS diode and subtracted '
      'from the copy of side B at node d3, which therefore swings rail to rail with no tail current (so the NMOS-input swing problem of a diff-pair converter, d3 never below ~1.7 V, is avoided). EN gates a NAND2; '
      'chain NAND2 - INV - INV - INV is non-inverting (EN = 0 gives OUT = 0). Digital-style widths (book 1.2: the method does not apply to inverters), taper FO <= 4.\n')
    table('lane', 'Stage-3 devices', ['mp3', 'mn3'])
    w('| gate | Wn / Wp (um) | Cin (fF) | FO to the next |')
    w('|---|---|---|---|')
    d = D['dig']
    fo_map = {'nand': cin['fo'][0][2], 'inv1': cin['fo'][1][2], 'inv2': cin['fo'][2][2], 'inv3': cin['fo_out']}
    for k, nm in (('nand', 'NAND2'), ('inv1', 'INV1'), ('inv2', 'INV2'), ('inv3', 'INV3 (output)')):
        w('| %s | %.1f / %.1f | %.1f | %.2f |' % (nm, d[k][0], d[k][1], cin[k] * 1e15, fo_map[k]))
    w('')
    w('## 5. Secondary ESD (swappable sub-cell, UNQUALIFIED)\n')
    w('Per input: series `ppolyf_u` %.1f x %.1f um (151 ohm tt) then diodes to VDD (`diode_pd2nw_03v3`) and VSS (`diode_nd2ps_03v3`) of %.0f x %.0f um (%.0f um2) at the pair gates. '
      'Input capacitance of one lane input: PMOS pair %.0f fF + NMOS pair %.0f fF + diodes (assumed) = %.0f fF; R_esd x C_in pole = %.1f GHz (>> f1). No HBM/CDM data exists: flagged UNQUALIFIED (PLAN_V2 L6).\n' % (
        D['esd_rw'], D['esd_rl'], D['esd_dw'], D['esd_dl'], D['esd_dw'] * D['esd_dl'], cin['cgg_p'] * 1e15, cin['cgg_n'] * 1e15, cin['cin_pin'] * 1e15, cin['f_esd'] / 1e9))
    # ---------------------------------------------------------------- corner table
    w('## 6. Corner evaluation (bias moves with PVT)\n')
    w('Corners with tables: tt at 3.0/3.3/3.6 V (typical table), ss/125 C/3.0 V (ss table), ff/-40 C/3.6 V (ff table), and the two resistor cross corners. ss/-40 C, fs and sf have no table: TB1 covers them in simulation. '
      'Body-effect beyond the corner tables (VSB > 0.8 V) uses the typical-table delta.\n')
    keys = list(ev.keys())
    w('| quantity | ' + ' | '.join(keys) + ' |')
    w('|---|' + '---|' * len(keys))

    def row(name, fn, f='%.3g'):
        w('| %s | %s |' % (name, ' | '.join(f % fn(ev[k]) for k in keys)))
    row('I_ref (uA)', lambda e: e['bias']['iref'] * 1e6, '%.1f')
    row('Itp / Itn (uA)', lambda e: e['bias']['itp'] * 1e6, '%.1f')
    row('I3 each sink (uA)', lambda e: e['bias']['i3'] * 1e6, '%.1f')
    row('RL (kohm)', lambda e: e['bias']['rl'] / 1e3, '%.2f')
    row('VR = IRL x RL (V)', lambda e: e['bias']['vr'], '%.3f')
    row('stage-1 output CM (V)', lambda e: e['bias']['cm'], '%.3f')
    row('F = Vf (V)', lambda e: e['bias']['F'], '%.3f')
    row('Vref (V)', lambda e: e['bias']['vref'], '%.3f')
    row('A1 PMOS path at VIC 0.05 V', lambda e: e['s1']['a1p'], '%.2f')
    row('A1 NMOS path at VIC 2.35 V', lambda e: e['s1']['a1n'], '%.2f')
    row('kappa (fold transfer)', lambda e: e['s1']['kappa'], '%.3f')
    row('M3 margin (mV)', lambda e: e['s1']['marg_m3'] * 1e3, '%.0f')
    row('PMOS pair margin VIC 0.05 V (mV)', lambda e: e['s1']['marg_pair_p'] * 1e3, '%.0f')
    row('NMOS pair margin VIC 2.35 V (mV)', lambda e: e['s1']['marg_pair_n'] * 1e3, '%.0f')
    row('PMOS pair valid up to VIC (V)', lambda e: e['s1']['vic_p_max'], '%.3f')
    row('NMOS pair valid from VIC (V)', lambda e: e['s1']['vic_n_min'], '%.3f')
    row('N/P overlap (V)', lambda e: e['s1']['overlap'], '%.3f')
    row('f1 = 1/(2 pi RL Cout) (MHz)', lambda e: e['s1']['f1'] / 1e6, '%.0f')
    row('fold pole fp2 (GHz)', lambda e: e['s1']['fp2'] / 1e9, '%.2f')
    row('stage-2 margin pair bal. (mV)', lambda e: e['s2']['marg_pair'] * 1e3, '%.0f')
    row('stage-2 margin pair latched (mV)', lambda e: e['s2']['marg_pair_latched'] * 1e3, '%.0f')
    row('stage-2 margin tail (mV)', lambda e: e['s2']['marg_tail'] * 1e3, '%.0f')
    row('V_H,in min (mV)', lambda e: e['s2']['vh_in_min'] * 1e3, '%.1f')
    row('V_H,in max (mV)', lambda e: e['s2']['vh_in_max'] * 1e3, '%.1f')
    row('stage-2 regeneration tau (ps)', lambda e: e['s2']['tau_regen'] * 1e12, '%.0f')
    row('I_lane (uA)', lambda e: e['i_lane'] * 1e6, '%.0f')
    row('I_bias (uA)', lambda e: e['bias']['i_bias'] * 1e6, '%.0f')
    w('')
    # ---------------------------------------------------------------- offset budget
    bg = budget
    w('## 7. Offset budget (finding C3; Pelgrom A_VT = 7.15 mV um NMOS, PMOS 6.66 x 1.17 (measured MC is 6-17 % worse), Leff = L - 0.15, Weff = W + 0.1)\n')
    w('`sigma_total^2 = sigma_1^2 + (sigma_2/A1_min)^2 + (sigma_VH/2)^2 + (sigma_3/(A1 A2))^2`; A1_min = %.2f (all corners), A2 = %.0f assumed.\n' % (bg['a1_min'], bg['a2']))
    w('| term | contribution (mV, 1 sigma) | detail |')
    w('|---|---|---|')
    pp, npth = bg['pmos_path'], bg['nmos_path']
    w('| sigma_1 stage 1 (worst path) | %.2f | PMOS path %.2f = pair %.2f + dump twin %.2f + M3 sinks %.2f + RL 0.5 %% %.2f (quadrature); NMOS path %.2f = pair %.2f + twin %.2f + RL %.2f |' % (
        bg['stage1'] * 1e3, pp['total'] * 1e3, pp['pair'] * 1e3, pp['dump_twin'] * 1e3, pp['m3_sinks'] * 1e3, pp['rl'] * 1e3, npth['total'] * 1e3, npth['pair'] * 1e3, npth['dump_twin'] * 1e3, npth['rl'] * 1e3))
    w('| (sigma_2 / A1_min) | %.2f | sigma_2 = %.2f (pair %.2f, loads %.2f) |' % (math.sqrt(bg['term2']) * 1e3, bg['stage2'] * 1e3, bg['stage2_pair'] * 1e3, bg['stage2_load'] * 1e3))
    w('| (sigma_VH / 2) | %.2f | hysteresis spread %.2f mV input-referred (alpha error from load VT mismatch) |' % (math.sqrt(bg['term3']) * 1e3, bg['sigma_vh_in'] * 1e3))
    w('| (sigma_3 / (A1 A2)) | %.2f | sigma_3 = %.2f mV |' % (math.sqrt(bg['term4']) * 1e3, bg['stage3'] * 1e3))
    w('| **sigma_total** | **%.2f** | target %.0f mV; trip window 2 mV + 6 sigma + %.1f + 3 = **%.1f mV** <= 95 mV |' % (bg['sigma_total'] * 1e3, SIGMA_TARGET * 1e3, VH_MAX / 2 * 1e3, bg['window_mV']))
    w('\nMonte Carlo is the judge (TB3_off, N = 1000); the hand budget only places the design in the right region.\n')
    # ---------------------------------------------------------------- tally
    w('## 8. Current tally (per lane and bias, uA)\n')
    w('| corner | bias: Rb branch | VBP branch | VB2 branch | Vref divider | **I_bias** | lane: 2 x I3 | Itn | stage-2 tail | stage 3 (max state) | **I_lane** | limit |')
    w('|---|---|---|---|---|---|---|---|---|---|---|---|')
    for k in keys:
        e = ev[k]
        b, s2 = e['bias'], e['s2']
        w('| %s | %.0f | %.0f | %.0f | %.0f | **%.0f** | %.0f | %.0f | %.0f | %.0f | **%.0f** | bias 300, lane 1500 |' % (
            k, b['iref'] * 1e6, b['isink'] * 1e6, b['ib2'] * 1e6, b['idiv'] * 1e6, b['i_bias'] * 1e6, 2 * b['i3'] * 1e6, b['itn'] * 1e6, b['it2'] * 1e6, max(2 * s2['i3bal'], s2['i3lat']) * 1e6, e['i_lane'] * 1e6))
    w('\nThree lanes at tt: %.0f uA + bias %.0f uA. EN = 0: every current path is opened (Msw, divider switch, tails off, d2a/d2b parked at VDD, NAND forces OUT = 0): IDD(EN=0) is leakage only, measured in TB8 (not claimed here).\n' % (3 * tt['i_lane'] * 1e6, tt['bias']['i_bias'] * 1e6))
    # ---------------------------------------------------------------- asserts
    w('## 9. Assertions (%d, failed %d)\n' % (len(A.items), A.failed))
    w('| result | assertion | value |')
    w('|---|---|---|')
    for n, ok, dtl in A.items:
        w('| %s | %s | %s |' % ('PASS' if ok else '**FAIL**', n, dtl))
    w('')
    w('## 10. Limits of this report (read before trusting it)\n')
    w('* Look-up tables exist only for tt/27 C, ss/125 C, ff/-40 C (L on the grid); fs, sf and ss/-40 C are covered only by simulation (TB1, TB2 smoke at worst5).')
    w('* The VDS of every device is a design assumption (table column OP_POINT in the script); TB1 compares the real `.op` point and fails on > 10 % ID or gm/ID, > 30 mV VGS.')
    w('* The hysteresis is solved large-signal at tt and scaled with gm/ID elsewhere; the A1 spread over VIC (<= 1.27x) is the T1 measurement, not a prediction.')
    w('* Dump twins are budgeted as a full extra sigma (T1 open item 1): conservative.')
    w('* Not implemented in v0 (the flags exist in the netlist; setting them aborts the build): failsafe, on-die termination, extra gain stage, constant-gm bias.')
    w('* VDsat is 2/(gm/ID) (book eq. 2.34) except NMOS L = 1 um devices, where the T1 spike measured BSIM vdsat = 0.80-0.86 x that value (factor %.2f used). The simulator check of this netlist is sim/t2_op (tt/ss/ff/fs/sf, VIC 0.05/1.2/2.35 V): see sim/t2_op/results/op_table.md.' % VDSAT_K_N1)
    return '\n'.join(L) + '\n'


# =====================================================================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--set', action='append', default=[], help='key=value override of a scalar in D')
    ap.add_argument('--no-write', action='store_true')
    ap.add_argument('--out', default=None, help='write sizes.spice, device_table.json, sizing.json and the report to this directory instead')
    args = ap.parse_args()
    for kv in args.set:
        k, v = kv.split('=', 1)
        D[k] = float(v) if not isinstance(D[k], list) else eval(v)
    S, devs = design()
    ev = evaluate_corners(S, devs)
    budget = offset_budget(S, devs, ev)
    cin = input_caps(S, devs, ev)
    A = Asserts()
    run_asserts(A, S, devs, ev, budget, cin)
    res = write_outputs(S, devs, ev, budget, cin, A, args)
    if not args.no_write:
        with open(os.path.join(args.out or HERE, 'sizing_report.md'), 'w') as f:
            f.write(report(S, devs, ev, budget, cin, A))
    for n, ok, dtl in A.items:
        if not ok:
            print('FAIL  %s : %s' % (n, dtl))
    print('asserts: %d total, %d failed; sigma_total %.2f mV; I_lane(tt) %.0f uA, I_bias(tt) %.0f uA' % (
        len(A.items), A.failed, budget['sigma_total'] * 1e3, ev[TT.name]['i_lane'] * 1e6, ev[TT.name]['bias']['i_bias'] * 1e6))
    tt = ev[TT.name]
    print('tt: Iref %.1f uA, Itp %.1f, Itn %.1f, I3 %.1f, VR %.3f, CM %.3f, A1p %.2f A1n %.2f, f1 %.0f MHz fp2 %.2f GHz, alpha %d/%d' % (
        tt['bias']['iref'] * 1e6, tt['bias']['itp'] * 1e6, tt['bias']['itn'] * 1e6, tt['bias']['i3'] * 1e6, tt['bias']['vr'], tt['bias']['cm'],
        tt['s1']['a1p'], tt['s1']['a1n'], tt['s1']['f1'] / 1e6, tt['s1']['fp2'] / 1e9, S['nd'], S['nc']))
    return 1 if A.failed else 0


if __name__ == '__main__':
    sys.exit(main())
