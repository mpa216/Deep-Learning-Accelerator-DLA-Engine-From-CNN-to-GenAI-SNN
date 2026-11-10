#!/usr/bin/env python3
"""spike_stage1.py -- gm/ID sizing + netlist generator for the STAGE-1 SPIKE (task T1, PLAN_V2 S0).

Question the spike answers: does the hybrid complementary input stage (PMOS pair folded through NMOS cascodes into NMOS
sinks, NMOS pair pulling straight from the resistor-load nodes, tail-"dump" devices gated by Vref = 0.48*VDD) hold its
output common mode and its gain over VIC = 0.05 .. 2.35 V?  Bias is ideal: ideal reference currents into diode-connected
replicas (so the real mirror ratios and VGS tracking are there), an ideal Vref = 0.48*VDD and an ideal cascode-offset
voltage Vf.  Nothing here is the final design: the sizes are for the spike only.

Method (book via docs/GMID_METHOD_NOTES.md): every W comes from  W = ID / (ID/W)(gm/ID, L, VDS, VSB)  (book eq. 3.8/3.9,
p.110-112) through gmid_gf180.size()/at_gmid(); L is on the LUT grid.  The per-device choices are in DEVICES below, each with
its reason.  Nothing is hand-tuned in the SPICE: the netlists in sim/spike_stage1/ are written by this script from the
numbers it prints.

Variants written (all share the same sizes):
  A   PMOS pair only (Option A, flow shake-down):   no NMOS pair, no dump;  M3 sinks reduced so RL carries the same current
  H0  hybrid, NO dump (control experiment):         shows what the dump devices have to cure
  H1  hybrid + dump (candidate):                    dump = a third pair of identical devices with both gates at Vref,
                                                    drains into the same two nodes the pair drives
Usage:   python3 sizing/spike_stage1.py [--set key=value ...] [--tag name]   (writes sim/spike_stage1/*.spice + results/spike_stage1_sizing.json)
"""
import argparse
import hashlib
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, HERE)
import gmid_gf180 as G  # noqa: E402

# --------------------------------------------------------------------------------------------------------------------
# Choices (each one with the reason; the book section is in docs/SPIKE_STAGE1.md)
# --------------------------------------------------------------------------------------------------------------------
P = dict(
    vdd=3.3,                 # sizing point; the corners are checked in simulation (LUT is typical 27 C)
    vref_ratio=0.48,         # Vref = 0.48*VDD (review_circuit.md item 2: centre of the N/P window at every corner)
    vf=0.45,                 # fold-node voltage F set by the cascode bias (iter2: 0.5->0.45): M3 VDS = F >= VDsat3 + margin, PMOS pair VSD at VIC=0.05 gets +50 mV
    vr=1.00,                 # RL drop at tt (iter2: 0.9->1.0): out CM = VDD - 1.0 V = 2.3 V; A1 ~ (gm/ID) * VR, so this is the gain knob
    tail_n=100e-6, tail_p=100e-6,   # tail currents (sum over the pair's two devices)
    i3_ratio=1.2,            # I(M3 each) / Itp.  M5 current = I3 - Itp/2 must stay > 0 when the PMOS pair steers fully
    # gm/ID and L per role.  pair = input pair AND its dump twins (identical W/L, else the switch point is not at Vref)
    gmid_pair_n=15.0, L_pair_n=0.5,    # pair: moderate inversion; steering and A1 (A1 ~ gm/ID * VR), fT ~ 3 GHz (handoff 7.3 item 5)
    gmid_pair_p=15.0, L_pair_p=0.4,    # PMOS: shortest L that keeps PMOS fT (0.8 GHz) usable and is on the LUT grid in every corner table
    gmid_tail=7.0, L_tail=1.0,         # tails: low VDsat headroom and matching/output resistance from L=1 (handoff 7.3 item 5)
    gmid_m3=7.0, L_m3=1.0,             # sinks: same inversion/L as the NMOS tail so ONE diode (VBN) biases both
    gmid_m5=10.0, L_m5=0.5,            # cascode: short L for the fold pole, gm/ID 10 (handoff 7.3 item 5)
    # operating points used for the LUT look-ups (design point VIC = Vref = 1.58 V at VDD 3.3)
    vds_pair_n=1.2, vsb_pair_n=0.7,    # NMOS pair: CM_out(2.4) - VS(~1.2), body effect VSB ~ VS = VIC - VGS
    vds_pair_p=1.4, vsb_pair_p=0.0,    # PMOS pair: VSD ~ tail(~2.5) - F(0.5)... ~1.4-2 V, well tied to the source
    vds_tail_n=0.8, vds_tail_p=0.8,
    vds_m3=0.5, vds_m5=1.8, vsb_m5=0.5,
    wf_unit_n=2.5, wf_unit_p=5.0,      # finger width (um) of the mirror unit: integer multiples give exact mirror ratios
    wf_pair=5.0,                       # finger width of the pair devices (LUT width)
    cl=30e-15,               # load per output (ASSUMPTION: stage-2 pair Cgg ~ 20 fF + wiring)
    rw=2.0,                  # RL width (um), ppolyf_u_1k
    # ideal-bias scale factor emulating the resistor-diode / constant-gm bias spread (book Table 5.15 style, C7b of PLAN_V2)
    ibs={'ss_hot': 1.33, 'ff_cold': 0.78},
)

# resistor model facts (docs/ENV_REPORT.md section 3): ppolyf_u_1k rsh_eff*W = 1013 ohm*um (tt/27 C), Rends = 85 ohm
RSH_1K, R_ENDS = 1013.0, 85.0


def _nf_for(W, wf):
    return max(1, int(math.ceil(W / wf - 1e-9)))


def design(p):
    """Return the device table (dict of dicts) and the predicted small-signal numbers."""
    d = {}
    jd = lambda name, gmid, L, vds, vsb=0.0: G.at_gmid(name, 'ID_W', gmid, L, vds, vsb)   # A/um

    # ---- mirror unit devices (NMOS: one diode VBN biases tail MNT and sinks M3; PMOS: VBP biases MPT)
    jdn = jd('nfet_03v3', p['gmid_tail'], p['L_tail'], p['vds_tail_n'])
    jdp = jd('pfet_03v3', p['gmid_tail'], p['L_tail'], p['vds_tail_p'])
    wun, wup = p['wf_unit_n'], p['wf_unit_p']
    iun, iup = jdn * wun, jdp * wup                         # unit currents (A)
    a_n = max(1, round(p['tail_n'] / iun))                   # tail multiple (NMOS)
    a_p = max(1, round(p['tail_p'] / iup))
    itn, itp = a_n * iun, a_p * iup                          # ACTUAL tail currents
    b3 = max(1, round(p['i3_ratio'] * itp / iun))            # sink multiple
    i3 = b3 * iun
    d['MNT'] = dict(dev='nfet_03v3', W=a_n * wun, nf=a_n, L=p['L_tail'], role='NMOS tail', ID=itn, gmid=p['gmid_tail'], mult=a_n)
    d['MPT'] = dict(dev='pfet_03v3', W=a_p * wup, nf=a_p, L=p['L_tail'], role='PMOS tail', ID=itp, gmid=p['gmid_tail'], mult=a_p)
    d['M3'] = dict(dev='nfet_03v3', W=b3 * wun, nf=b3, L=p['L_m3'], role='NMOS sink x2', ID=i3, gmid=p['gmid_m3'], mult=b3)
    d['MBN'] = dict(dev='nfet_03v3', W=wun, nf=1, L=p['L_tail'], role='VBN diode (unit)', ID=iun, gmid=p['gmid_tail'], mult=1)
    d['MBP'] = dict(dev='pfet_03v3', W=wup, nf=1, L=p['L_tail'], role='VBP diode (unit)', ID=iup, gmid=p['gmid_tail'], mult=1)
    # ---- pairs (+ dump twins) : each device carries tail/2
    for key, name, tail, L, gmid, vds, vsb in (
            ('N', 'nfet_03v3', itn, p['L_pair_n'], p['gmid_pair_n'], p['vds_pair_n'], p['vsb_pair_n']),
            ('P', 'pfet_03v3', itp, p['L_pair_p'], p['gmid_pair_p'], p['vds_pair_p'], p['vsb_pair_p'])):
        idev = tail / 2
        r = G.size(name, gm=gmid * idev, gmid=gmid, L=L, VDS=vds, VSB=vsb, wf_max=p['wf_pair'])
        d['M%s1' % key] = dict(dev=name, W=r['W'], nf=r['nf'], L=L, role='%sMOS pair' % ('N' if key == 'N' else 'P'),
                               ID=idev, gmid=gmid, sz=r)
    # ---- cascode M5: carries I3 - Itp/2 at the common mode
    i5 = i3 - itp / 2 + 0.0
    r5 = G.size('nfet_03v3', gm=p['gmid_m5'] * i5, gmid=p['gmid_m5'], L=p['L_m5'], VDS=p['vds_m5'], VSB=p['vsb_m5'], wf_max=5.0)
    d['M5'] = dict(dev='nfet_03v3', W=r5['W'], nf=r5['nf'], L=p['L_m5'], role='NMOS cascode x2', ID=i5, gmid=p['gmid_m5'], sz=r5)
    # ---- load resistor: RL carries I3 - Itp/2 + Itn/2 (= I3 when the tails are equal)
    irl = i3 - itp / 2 + itn / 2
    rl = p['vr'] / irl
    rl_len = (rl - R_ENDS) * p['rw'] / RSH_1K                # um
    # ---- predictions (typical, LUT): small-signal gain of each path
    gm_p = p['gmid_pair_p'] * (itp / 2)
    gm_n = p['gmid_pair_n'] * (itn / 2)
    gm5 = d['M5']['sz']['gm']
    gm_gds_3 = G.at_gmid('nfet_03v3', 'GM_GDS', p['gmid_m3'], p['L_m3'], p['vds_m3'])
    gm_gds_p = G.at_gmid('pfet_03v3', 'GM_GDS', p['gmid_pair_p'], p['L_pair_p'], p['vds_pair_p'])
    gds3 = i3 * p['gmid_m3'] / gm_gds_3
    gdsp = gm_p / gm_gds_p
    kappa = gm5 / (gm5 + gds3 + gdsp)
    pred = dict(rl=rl, rl_len_um=rl_len, irl=irl, i5=i5, i3=i3, itn=itn, itp=itp, iun=iun, iup=iup, a_n=a_n, a_p=a_p, b3=b3,
                gm_p=gm_p, gm_n=gm_n, gm5=gm5, kappa=kappa, a1_p=kappa * gm_p * rl, a1_n=gm_n * rl,
                vgs_pair_n=d['MN1']['sz']['VGS'], vgs_pair_p=d['MP1']['sz']['VGS'],
                i_vdd=2 * i3 + itn, fT_pair_n=d['MN1']['sz']['fT'], fT_pair_p=d['MP1']['sz']['fT'])
    return d, pred


def _w(x):
    return '%.4g' % x


def inst(name, dd, drain, gate, source, bulk, mult=None):
    """Instance line in the kit convention (spice_line), with explicit nf; matched devices use nf, never m."""
    W, nf, L = dd['W'], dd['nf'], dd['L']
    m = dd['dev']
    return ("X%s %s %s %s %s %s L=%su W=%su nf=%d "
            "ad='int((nf+1)/2) * W/nf * 0.18u' as='int((nf+2)/2) * W/nf * 0.18u' "
            "pd='2*int((nf+1)/2) * (W/nf + 0.18u)' ps='2*int((nf+2)/2) * (W/nf + 0.18u)' "
            "nrd='0.18u / W' nrs='0.18u / W' sa=0 sb=0 sd=0" % (name, drain, gate, source, bulk, m, _w(L), _w(W), nf))


def netlist(variant, d, pred, p):
    """Return (netlist text, list of (instance, kind, d, g, s) for the per-device report)."""
    L = []
    devs = []

    def add(name, dd, dr, g, s, b):
        L.append(inst(name, dd, dr, g, s, b))
        devs.append((name.lower(), 'p' if dd['dev'].startswith('pfet') else 'n', dr, g, s))
    hyb = variant in ('H0', 'H1')
    dump = variant == 'H1'
    # sinks: in A the NMOS pair is absent, RL must carry the same current: sink current reduced by Itn/2
    m3 = dict(d['M3'])
    if variant == 'A':
        b = max(1, round((pred['i3'] - pred['itn'] / 2) / pred['iun']))
        m3.update(W=b * p['wf_unit_n'], nf=b, mult=b)
    L.append('* ---- load resistors (ppolyf_u_1k, body VSS), W=%su L=%su -> %.0f ohm at tt/27C' % (_w(p['rw']), _w(pred['rl_len_um']), pred['rl']))
    for n, o in (('RLa', 'oa'), ('RLb', 'ob')):
        L.append('X%s vdd %s 0 ppolyf_u_1k r_width=%su r_length=%su' % (n, o, _w(p['rw']), _w(pred['rl_len_um'])))
    L.append('* ---- PMOS path: tail, pair (own n-well = tail node), fold nodes fa/fb, NMOS cascodes M5 into oa/ob, sinks M3')
    add('Mpt', d['MPT'], 'tp', 'vbp', 'vdd', 'vdd')
    add('Mp1', d['MP1'], 'fa', 'inp', 'tp', 'tp')
    add('Mp2', d['MP1'], 'fb', 'inn', 'tp', 'tp')
    if dump:
        add('Mpd1', d['MP1'], 'fa', 'vref', 'tp', 'tp')
        add('Mpd2', d['MP1'], 'fb', 'vref', 'tp', 'tp')
    add('M3a', m3, 'fa', 'vbn', '0', '0')
    add('M3b', m3, 'fb', 'vbn', '0', '0')
    add('M5a', d['M5'], 'oa', 'vb2', 'fa', '0')
    add('M5b', d['M5'], 'ob', 'vb2', 'fb', '0')
    if hyb:
        L.append('* ---- NMOS path: tail, pair drains straight into the RL nodes' + (', dump twins gated by Vref' if dump else ''))
        add('Mnt', d['MNT'], 'tn', 'vbn', '0', '0')
        add('Mn1', d['MN1'], 'oa', 'inp', 'tn', '0')
        add('Mn2', d['MN1'], 'ob', 'inn', 'tn', '0')
        if dump:
            add('Mnd1', d['MN1'], 'oa', 'vref', 'tn', '0')
            add('Mnd2', d['MN1'], 'ob', 'vref', 'tn', '0')
    L.append('* ---- ideal bias: reference currents into diode-connected replicas (mirror ratios are real); ibs = corner scale')
    L.append('Ibn vdd vbn dc {%.6g*ibs}' % pred['iun'])
    L.append(inst('Mbn', d['MBN'], 'vbn', 'vbn', '0', '0'))
    L.append('Ibp vbp 0 dc {%.6g*ibs}' % pred['iup'])
    L.append(inst('Mbp', d['MBP'], 'vbp', 'vbp', 'vdd', 'vdd'))
    L.append('Ib2 vdd vb2 dc {%.6g*ibs}' % pred['i5'])
    L.append(inst('Mb2', d['M5'], 'vb2', 'vb2', 'vf', '0'))
    L.append('Vf vf 0 dc %g' % p['vf'])
    L.append('Vref vref 0 dc {%g*vddv}' % p['vref_ratio'])
    L.append('Cla oa 0 %g' % p['cl'])
    L.append('Clb ob 0 %g' % p['cl'])
    return '\n'.join(L), devs


DECK = """* tb_spike_{variant}: stage-1 spike, variant {variant} ({vdesc}).  GENERATED by sizing/spike_stage1.py -- do not edit.
* one run = one (corner, VIC) point: op (currents, saturation margins) + ac (differential gain, -3 dB frequency)
{{header}}
{{seed_line}}
.include {{run_dir}}/ibs.inc
.param vddv = {{vdd}}
Vsup vdd 0 {{vdd}}
Vcm cm 0 dc {{vic}}
Vip inp cm dc 0 ac 0.5
Vin inn cm dc 0 ac -0.5
{net}
.control
op
let cm = (v(oa)+v(ob))/2
let vod = v(ob)-v(oa)
let idd = -i(Vsup)
echo RESULT cm $&cm
echo RESULT vod_dc $&vod
echo RESULT idd $&idd
echo RESULT vfa $&v(fa)
echo RESULT vfb $&v(fb)
echo RESULT vtp $&v(tp)
{vtn}
echo RESULT vbn $&v(vbn)
echo RESULT vbp $&v(vbp)
echo RESULT vb2 $&v(vb2)
{devecho}
ac dec 20 1e5 1e10
let vac = v(ob)-v(oa)
let g = mag(vac)
let a1 = g[0]
let thr = a1/1.41421356
let n = length(g)
let fr = frequency
let k = 0
let f3 = 1e10
let found = 0
while k < n-1
  if found = 0
    if g[k+1] < thr
      let f3 = fr[k]*exp(ln(fr[k+1]/fr[k])*(g[k]-thr)/(g[k]-g[k+1]))
      let found = 1
    end
  end
  let k = k+1
end
let gpk = vecmax(g)
echo RESULT a1 $&a1
echo RESULT f3db $&f3
echo RESULT f3db_found $&found
let gpr = gpk/a1
echo RESULT gpeak_ratio $&gpr
.endc
.end
"""

VDESC = {'A': 'PMOS pair only, Option A', 'H0': 'hybrid, no dump devices (control)', 'H1': 'hybrid + dump devices (candidate)'}


def deck(variant, d, pred, p):
    net, devs = netlist(variant, d, pred, p)
    ec = []
    V = lambda x: '0' if x == '0' else 'v(%s)' % x
    for n, k, dr, g, s in devs:
        ec.append('let vds_%s = abs(%s-%s)' % (n, V(dr), V(s)))
        ec.append('let mg_%s = vds_%s - abs(@m.x%s.m0[vdsat])' % (n, n, n))
        ec.append('let id_%s = abs(@m.x%s.m0[id])' % (n, n))
        ec.append('let gm_%s = abs(@m.x%s.m0[gm])' % (n, n))
        ec.append('let vgs_%s = abs(%s-%s)' % (n, V(g), V(s)))
        for q in ('mg', 'id', 'gm', 'vgs'):
            ec.append('echo RESULT %s_%s $&%s_%s' % (q, n, q, n))
    vtn = 'echo RESULT vtn $&v(tn)' if variant != 'A' else 'echo RESULT vtn 0'
    return DECK.format(variant=variant, vdesc=VDESC[variant], net=net, vtn=vtn, devecho='\n'.join(ec)), devs


def spec_json(variant):
    vic = [round(0.05 + 0.05 * i, 2) for i in range(47)]
    return dict(
        name='spike_%s' % variant, description='T1 stage-1 spike, variant %s: %s. Metrics are per (corner, VIC); sim/spike_stage1/analyze.py aggregates.' % (variant, VDESC[variant]),
        deck='tb_spike_%s.spice' % variant,
        corners=['tt:27:3.3', 'ss:125:3.0', 'ss:-40:3.0', 'fs:27:3.0', 'sf:125:3.0', 'ff:-40:3.6',
                 'ss:125:3.0:res=res_ff', 'ff:-40:3.6:res=res_ss'],
        grid={'vic': vic}, vars={'variant': variant}, limits={}, prep='hooks.py:prep_bias', timeout=120, jobs=6)


def sha(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--set', action='append', default=[], help='key=value override of a parameter in P')
    ap.add_argument('--tag', default='')
    ap.add_argument('--outdir', default=os.path.join(ROOT, 'sim', 'spike_stage1'))
    a = ap.parse_args()
    p = dict(P)
    for kv in a.set:
        k, v = kv.split('=', 1)
        p[k] = float(v)
    d, pred = design(p)
    os.makedirs(a.outdir, exist_ok=True)
    lut_hash = hashlib.sha256(b''.join(open(G.lut_path(n), 'rb').read() for n in ('nfet_03v3', 'pfet_03v3'))).hexdigest()[:16]
    head = '* HASH sizing_script=%s luts=%s\n' % (sha(os.path.abspath(__file__)), lut_hash)
    for v in ('A', 'H0', 'H1'):
        txt, _ = deck(v, d, pred, p)
        with open(os.path.join(a.outdir, 'tb_spike_%s.spice' % v), 'w') as f:
            f.write(head + txt)
        with open(os.path.join(a.outdir, 'spike_%s.json' % v), 'w') as f:
            json.dump(spec_json(v), f, indent=1)
    table = {k: {kk: vv for kk, vv in v.items() if kk != 'sz'} for k, v in d.items()}
    for k in ('M5', 'MN1', 'MP1'):
        sz = d[k]['sz']
        table[k].update(VGS=sz['VGS'], fT=sz['fT'], gm_gds=sz['gm_gds'], Cgg=sz['Cgg'], Cdd=sz['Cdd'], VDsat_rule=sz['VDsat'])
    out = dict(params={k: v for k, v in p.items()}, devices=table, predicted=pred, tag=a.tag)
    os.makedirs(os.path.join(ROOT, 'results'), exist_ok=True)
    with open(os.path.join(ROOT, 'results', 'spike_stage1_sizing.json'), 'w') as f:
        json.dump(out, f, indent=1)
    print('device table (W, nf in um / -; each pair device carries tail/2):')
    for k, v in table.items():
        print('  %-4s %-9s %-18s W=%7.2f nf=%-3d L=%.2f ID=%6.1f uA gm/ID=%g' % (k, v['dev'][:4], v['role'], v['W'], v['nf'], v['L'], v['ID'] * 1e6, v['gmid']))
    print('predicted (typical, LUT):')
    for k, v in pred.items():
        print('  %-12s %.5g' % (k, v))


if __name__ == '__main__':
    main()
