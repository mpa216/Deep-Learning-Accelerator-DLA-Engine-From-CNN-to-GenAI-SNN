"""hooks.py (TB1): turns the raw `RESULT` lines of tb1_op into the gate metrics of spec/gates.yaml (TB1) and writes lutcmp.json (per-device table) in every run dir.

Metric definitions (all per run = corner x VIC x VID):
  min_headroom_v   min over the analog devices carrying > 1 uA of (VDS - BSIM vdsat).  Switches, the digital chain, the stage-3 mirror (rail-to-rail by design) and the cross-coupled loads mlc (triode when latched) are excluded.
  gmid_err         worst signed relative error (gm/ID SPICE - LUT) / LUT over the same devices; LUT read at the SIMULATED bias (ID/W, VDS, VSB) of the corner's table.
  vgs_err_v        worst signed (VGS SPICE - VGS LUT at the simulated ID/W, VDS, VSB).
  id_err           worst signed (ID SPICE - ID script) / script over the fixed-current devices (reference, tails, sinks, stage-2 tail; the script's corner solution
                   `bias_corner`).  Pair, dump, cascode, stage-2 and stage-3 devices change current with VIC / VID / latch state: no script value, reported only.
  s1_cm_dev_v      stage-1 output common mode (oa + ob)/2 minus the mid-range over the 7 VIC points of the same corner and VID (decision D-002: span/2).
  np_overlap_v     dump-free control, see np_overlap(): min(window, 2 x Vref margin); the same number for every run of a corner.
  vnode_min_v, vnode_over_vdd_v   lowest node voltage, highest node voltage minus VDD.
  model_warnings   number of 'warning' lines in ngspice.log (the 'Comments and warnings go to log-file' banner is not one).
  i_bias_a, i_lane_a   bias block current (Rb branch + VBP branch + VB2 branch + Vref divider) and (IDD - I_bias)/3.
LUT tables: one per process x temperature of the 45 corners (15; T5 added the 8 + 2 that were missing), lutcmp.json: lut_table names it.
"""
import glob
import json
import math
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
for p in (os.path.join(ROOT, 'sizing'), os.path.join(ROOT, 'flow')):
    if p not in sys.path:
        sys.path.insert(0, p)
import lvds_rx_sizing as Z  # noqa: E402

# mlc (cross-coupled load) is in triode by design on the conducting side of the latched stage 2: no saturation requirement, no LUT comparison there
ANALOG = {'mbn', 'mbs', 'mbp', 'mb2p', 'mb2', 'mpt', 'mp1', 'mpd', 'mnt', 'mn1', 'mnd', 'm3', 'm5', 'mt2', 'ms', 'mld', 'mlc', 'm3a'}
FIXED = {'mbn': 'iref', 'mbs': 'isink', 'mbp': 'isink', 'mb2p': 'ib2', 'mb2': 'ib2', 'mpt': 'itp', 'mnt': 'itn', 'm3': 'i3', 'mt2': 'it2'}
IMIN = 1e-6            # devices below this current are off or in weak inversion: not compared
_state = {}


def _ctx(variant='base'):
    if variant not in _state.setdefault('dj', {}):
        _state['dj'][variant] = json.load(open(os.path.join(HERE, 'devices%s.json' % ('_pmos' if variant == 'pmos' else ''))))
    if 'S' not in _state:
        _state['S'], _state['devs'] = Z.design()
        _state['dev_json'] = {}
        _state['table'] = {d['stem']: d for d in json.load(open(os.path.join(ROOT, 'layout', 'device_table.json')))['devices']}
    return _state


def zcorner(c):
    """sizing-script Corner for a harness corner (LUT suffix by process / temperature, resistor factor by passive section)."""
    # one table per process x temperature (T5: all 15 exist; tt/27C is the unsuffixed typical table)
    tn = {-40: 'n40C', 27: '27C', 125: '125C'}[int(c.temp)]
    suf = '' if (c.process == 'tt' and c.temp == 27) else '_%s_%s' % (c.process, tn)
    res = {'res_typical': 'typ', 'res_ss': 'ss', 'res_ff': 'ff'}[c.res]
    zc = Z.Corner(c.name, suf, c.vdd, int(c.temp), res)
    zc.lut_table = suf[1:] if suf else 'tt_27C'
    return zc


def _siblings(run_dir):
    base = os.path.dirname(run_dir)
    name = os.path.basename(run_dir)
    m = re.match(r'^(.*)__vic([-\d.eE+]+)_vid([-\d.eE+]+)$', name)
    out = {}
    if not m:
        return out
    for d in glob.glob(os.path.join(base, '%s__vic*_vid%s' % (m.group(1), m.group(3)))):
        mm = re.match(r'^.*__vic([-\d.eE+]+)_vid', d)
        try:
            r = json.load(open(os.path.join(d, 'result.json')))['measures']
            out[float(mm.group(1))] = 0.5 * (r['v_xl0_oa'] + r['v_xl0_ob'])
        except (OSError, KeyError, ValueError):
            pass
    return out


def window(x, y, thr):
    """(low edge, high edge) of the contiguous region around the maximum of y where y >= thr (linear interpolation)."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    k = int(np.argmax(y))
    lo = hi = None
    i = k
    while i > 0 and y[i - 1] >= thr:
        i -= 1
    lo = x[0] if i == 0 else x[i - 1] + (thr - y[i - 1]) * (x[i] - x[i - 1]) / (y[i] - y[i - 1])
    j = k
    while j < len(y) - 1 and y[j + 1] >= thr:
        j += 1
    hi = x[-1] if j == len(y) - 1 else x[j] + (y[j] - thr) * (x[j + 1] - x[j]) / (y[j] - y[j + 1])
    return float(lo), float(hi)


def np_overlap(corner_name):
    """Dump-free control (sim/tb1_op/results/tb1_np): returns dict(np_window_v, np_vref_margin_v, np_overlap_v) for a corner, NaN if the control was not run."""
    nan = dict(np_window_v=float('nan'), np_vref_margin_v=float('nan'), np_overlap_v=float('nan'))
    try:
        rs = [r for r in json.load(open(os.path.join(HERE, 'results', 'tb1_np', 'results.json')))['runs']
              if r['corner'] == corner_name and r['status'] == 'ok']
    except OSError:
        return nan
    if len(rs) < 40:
        return nan
    rs.sort(key=lambda r: r['params']['vic'])
    vic = [r['params']['vic'] for r in rs]
    ip = [r['metrics']['id_mpt'] for r in rs]
    inn = [r['metrics']['id_mnt'] for r in rs]
    vp = window(vic, ip, 0.9 * max(ip))[1]          # PMOS tail valid up to vp
    vn = window(vic, inn, 0.9 * max(inn))[0]        # NMOS tail valid from vn
    vref = rs[0]['metrics']['v_vref']
    width = vp - vn
    margin = min(vref - vn, vp - vref)
    return dict(np_window_v=width, np_vref_margin_v=margin, np_overlap_v=min(width, 2 * margin))


def post_tb1(ctx):
    variant = ctx.get('vars', {}).get('variant', 'base')
    S = _ctx(variant)
    S['dev_json'] = S['dj'][variant]
    m = ctx['measures']
    c = ctx['corner']
    zc = zcorner(c)
    b = Z.bias_corner(zc, S['S'], S['devs'])
    rows, merr, verr, ierr, heads = {}, [], [], [], []
    for d in S['dev_json']:
        k, stem, kind = d['key'], d['stem'], d['kind']
        if stem not in ANALOG:
            continue
        idv = m['id_' + k]
        if idv < IMIN:
            rows[k] = dict(stem=stem, id=idv, off=True)
            continue
        if stem not in S['table']:                      # m3a (PMOS-only variant sink) has no row in the sizing script's table: headroom only
            rows[k] = dict(stem=stem, id=idv, mg=m['mg_' + k], vds=m['vds_' + k], no_lut=True)
            heads.append(m['mg_' + k])
            continue
        row = S['table'][stem]
        W, L = row['W_um'], row['L_um']
        vds, vsb, vgs, gm, mg = m['vds_' + k], m['vsb_' + k], m['vgs_' + k], m['gm_' + k], m['mg_' + k]
        if mg < 0:                                      # triode: the saturation LUT does not apply (only mlc may be here; any other device fails the headroom check)
            rows[k] = dict(stem=stem, id=idv, vds=vds, mg=mg, triode=True)
            if stem != 'mlc':
                heads.append(mg)
            continue
        jdv = idv / W
        gm_lut = Z.gmid_of_jd(kind, zc, L, jdv, max(vds, 0.05), vsb)
        vgs_lut = Z.vgs_of_jd(kind, zc, L, jdv, max(vds, 0.05), vsb)
        r = dict(stem=stem, id=idv, gmid=gm / idv, gmid_lut=gm_lut, vgs=vgs, vgs_lut=vgs_lut, vds=vds, vsb=vsb, mg=mg,
                 gmid_err=(gm / idv - gm_lut) / gm_lut, vgs_err=vgs - vgs_lut)
        if stem in FIXED:
            r['id_script'] = b[FIXED[stem]]
            r['id_err'] = idv / b[FIXED[stem]] - 1.0
            ierr.append(r['id_err'])
        rows[k] = r
        merr.append(r['gmid_err'])
        verr.append(r['vgs_err'])
        if stem != 'mlc':
            heads.append(mg)
    nodes = [v for kk, v in m.items() if kk.startswith('v_')]
    vdd = c.vdd
    idd = m['idd']
    i_bias = m['id_xbias_xmsw'] + m['id_xbias_xmbs'] + m['id_xbias_xmb2p'] + m['id_xbias_xmvs']
    nlines = 0
    try:
        for ln in open(os.path.join(ctx['run_dir'], 'ngspice.log'), errors='replace'):
            low = ln.lower()
            if 'warning' in low and 'comments and warnings go to log-file' not in low and 'stepping failed' not in low:   # T5 (D-013): a gmin / source stepping failure that the run recovered from (status ok) is a convergence-aid note, not a model warning
                nlines += 1
    except OSError:
        nlines = float('nan')
    cms = _siblings(ctx['run_dir'])
    cm = 0.5 * (m['v_xl0_oa'] + m['v_xl0_ob'])
    mid = 0.5 * (max(cms.values()) + min(cms.values())) if len(cms) >= 2 else float('nan')
    worst = lambda a: max(a, key=abs) if a else float('nan')
    out = dict(min_headroom_v=min(heads), gmid_err=worst(merr), vgs_err_v=worst(verr), id_err=worst(ierr),
               s1_cm_v=cm, s1_cm_dev_v=cm - mid, s1_cm_span_v=(max(cms.values()) - min(cms.values())) if len(cms) >= 2 else float('nan'),
               vnode_min_v=min(nodes), vnode_over_vdd_v=max(nodes) - vdd, model_warnings=nlines,
               i_bias_a=i_bias, i_lane_a=(idd - i_bias) / 3.0, idd_a=idd, i_bias_script_a=b['i_bias'],
               vout_v=m['v_rx0_o'])
    if variant != 'pmos':               # the N/P overlap is a property of the hybrid input; the PMOS-only variant has no NMOS pair
        out.update(np_overlap(c.name))
    json.dump(dict(corner=c.name, lut_table=zc.lut_table, vic=ctx['params']['vic'], vid=ctx['params']['vid'], metrics=out, devices=rows),
              open(os.path.join(ctx['run_dir'], 'lutcmp.json'), 'w'), indent=1)
    return out
