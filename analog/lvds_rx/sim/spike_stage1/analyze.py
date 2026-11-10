#!/usr/bin/env python3
"""analyze.py -- aggregate the stage-1 spike runs (3 variants x corners x 47 VIC points) into numbers, verdicts and plots.

Reads  sim/spike_stage1/results/spike_{A,H0,H1}/results.json
Writes results/spike_stage1.json            (every number, per variant and corner, plus the verdicts)
       sim/spike_stage1/results/tables.md   (generated tables, pasted into docs/SPIKE_STAGE1.md between markers)
       sim/spike_stage1/plots/*.png

Definitions (all from the frozen spec rows "Stage-1", PLAN_V2 3.1; the places where the spec leaves a choice are marked):
  cm(vic)         = (V(oa)+V(ob))/2.  cm_span = max-min over the 47 points.  Verdict on cm_dev_mid = span/2 (the "+-0.15 V" window
                    placed optimally); the stricter reading span <= 0.15 V is reported too.            [choice: reference of the +-]
  a1(vic)         = |V(ob)-V(oa)| for a 1 V differential AC input at 100 kHz.  a1_ext = min over the two single-pair extremes
                    VIC = 0.05 and 2.35 V (spec).  a1_min_all = min over all 47 points (stricter).  spread = max/min a1, over
                    the 47 points and over the 7 TB2 points {0.05,0.3,0.6,1.2,1.8,2.1,2.35}.
  overlap (H0/A)  = the review's definition: width of the VIC window in which the pair TAIL transistors both carry >= 90 % of their
                    plateau current (PMOS valid up to V_P, NMOS valid from V_N, overlap = V_P - V_N; negative = gap).
  overlap (H1)    = with dump devices the tails never leave saturation, so that definition is meaningless; instead
                    np_overlap_v = width of the VIC window where BOTH pairs carry >= 10 % of their tail current (pair share =
                    pair / (pair + dump)).  Also reported: the 50 % crossing VIC of each pair (should sit at Vref) and the
                    gm-sum dip.                                                                              [choice: definition]
  margin          = |VDS| - |VDsat| from the BSIM4 operating point, every device, every VIC; the spec limit is 50 mV (TB1).
  f3db            = -3 dB frequency of the differential gain, load 30 fF per output (assumption).
"""
import json
import os
import sys

import numpy as np

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
RES = os.path.join(ROOT, 'sim', 'spike_stage1', 'results')
PLOTS = os.path.join(ROOT, 'sim', 'spike_stage1', 'plots')
VARIANTS = ('A', 'H0', 'H1')
LIM = dict(cm_half=0.15, a1_min=4.0, a1_spread=2.2, overlap=0.25, margin=0.05, f3db=0.8 * 100e6)
TB2_VIC = (0.05, 0.3, 0.6, 1.2, 1.8, 2.1, 2.35)


def load(v):
    runs = json.load(open(os.path.join(RES, 'spike_%s' % v, 'results.json')))['runs']
    by = {}
    for r in runs:
        by.setdefault(r['corner'], []).append(r)
    for c in by:
        by[c].sort(key=lambda r: r['params']['vic'])
    return by


def arr(rs, key):
    return np.array([r['metrics'].get(key, np.nan) for r in rs], float)


def edge_up(x, y, level):
    """first x where y crosses level going up (linear interpolation), or nan."""
    for i in range(len(x) - 1):
        if y[i] < level <= y[i + 1]:
            return x[i] + (x[i + 1] - x[i]) * (level - y[i]) / (y[i + 1] - y[i])
    return np.nan


def edge_down(x, y, level):
    for i in range(len(x) - 1):
        if y[i] >= level > y[i + 1]:
            return x[i] + (x[i + 1] - x[i]) * (y[i] - level) / (y[i] - y[i + 1])
    return np.nan


def window(x, y, level):
    """(lo, hi) of the single interval where y >= level (edges interpolated; the sweep ends count as edges)."""
    ok = y >= level
    if not ok.any():
        return np.nan, np.nan
    i0, i1 = np.argmax(ok), len(ok) - 1 - np.argmax(ok[::-1])
    lo = x[0] if i0 == 0 else edge_up(x[:i0 + 1], y[:i0 + 1], level)
    hi = x[-1] if i1 == len(x) - 1 else edge_down(x[i1:], y[i1:], level)
    return lo, hi


def summarize(v, by):
    out = {}
    for c, rs in by.items():
        bad = [r for r in rs if r['status'] != 'ok']
        vic = arr(rs, 'vic') if False else np.array([r['params']['vic'] for r in rs])
        s = dict(n=len(rs), n_bad=len(bad), process=rs[0]['process'], temp=rs[0]['temp'], vdd=rs[0]['vdd'])
        if bad:
            s['errors'] = bad[0].get('errors', [])[:3]
        cm = arr(rs, 'cm')
        a1 = arr(rs, 'a1')
        f3 = arr(rs, 'f3db')
        s.update(cm_min=float(np.nanmin(cm)), cm_max=float(np.nanmax(cm)), cm_span=float(np.nanmax(cm) - np.nanmin(cm)),
                 cm_dev_mid=float((np.nanmax(cm) - np.nanmin(cm)) / 2),
                 cm_dev_ref=float(np.nanmax(np.abs(cm - cm[np.argmin(np.abs(vic - 1.5))]))),
                 cm_mean=float(np.nanmean(cm)))
        i05, i235 = int(np.argmin(np.abs(vic - 0.05))), int(np.argmin(np.abs(vic - 2.35)))
        sel = [int(np.argmin(np.abs(vic - t))) for t in TB2_VIC]
        s.update(a1_lo=float(a1[i05]), a1_hi=float(a1[i235]), a1_ext=float(min(a1[i05], a1[i235])),
                 a1_min_all=float(np.nanmin(a1)), a1_max_all=float(np.nanmax(a1)),
                 a1_spread_all=float(np.nanmax(a1) / np.nanmin(a1)),
                 a1_spread_tb2=float(np.nanmax(a1[sel]) / np.nanmin(a1[sel])),
                 vic_a1_min=float(vic[int(np.nanargmin(a1))]), vic_a1_max=float(vic[int(np.nanargmax(a1))]),
                 f3db_min=float(np.nanmin(f3)), f3db_max=float(np.nanmax(f3)), f3db_found_all=bool(np.all(arr(rs, 'f3db_found') == 1)),
                 gpeak_max=float(np.nanmax(arr(rs, 'gpeak_ratio'))), idd_mean=float(np.nanmean(arr(rs, 'idd'))),
                 idd_span=float(np.nanmax(arr(rs, 'idd')) - np.nanmin(arr(rs, 'idd'))))
        # device saturation margins
        mg = {}
        for k in rs[0]['metrics']:
            if k.startswith('mg_'):
                mg[k[3:]] = float(np.nanmin(arr(rs, k)))
        worst = min(mg, key=mg.get)
        s.update(margins=mg, margin_min=mg[worst], margin_dev=worst)
        # overlap
        if v == 'H1':
            ip = arr(rs, 'id_mp1') + arr(rs, 'id_mp2')
            ipd = arr(rs, 'id_mpd1') + arr(rs, 'id_mpd2')
            inn = arr(rs, 'id_mn1') + arr(rs, 'id_mn2')
            ind = arr(rs, 'id_mnd1') + arr(rs, 'id_mnd2')
            shp, shn = ip / (ip + ipd), inn / (inn + ind)
            plo, phi = window(vic, shp, 0.1)
            nlo, nhi = window(vic, shn, 0.1)
            s['share_p'] = shp.tolist()
            s['share_n'] = shn.tolist()
            s['p_share_50'] = float(edge_down(vic, shp, 0.5))
            s['n_share_50'] = float(edge_up(vic, shn, 0.5))
            s['p_top_10'], s['n_bottom_10'] = float(phi), float(nlo)
            s['handover_w10'] = float(phi - nlo)
            s['p_valid90_top'] = float(window(vic, shp, 0.9)[1])
            s['n_valid90_bottom'] = float(window(vic, shn, 0.9)[0])
            gmp = arr(rs, 'gm_mp1') + arr(rs, 'gm_mp2')
            gmn = arr(rs, 'gm_mn1') + arr(rs, 'gm_mn2')
            s['gm_sum_ratio_min_over_max'] = float(np.nanmin(gmp + gmn) / np.nanmax(gmp + gmn))
            # tail-current constancy with VIC (what the dump buys)
            s['itail_p_span_pct'] = float(100 * (np.nanmax(arr(rs, 'id_mpt')) - np.nanmin(arr(rs, 'id_mpt'))) / np.nanmean(arr(rs, 'id_mpt')))
            s['itail_n_span_pct'] = float(100 * (np.nanmax(arr(rs, 'id_mnt')) - np.nanmin(arr(rs, 'id_mnt'))) / np.nanmean(arr(rs, 'id_mnt')))
        else:
            tp = arr(rs, 'id_mpt')
            vp = window(vic, tp, 0.9 * np.nanmax(tp))[1]
            s['p_valid90_top'] = float(vp)
            if v == 'H0':
                tn = arr(rs, 'id_mnt')
                vn = window(vic, tn, 0.9 * np.nanmax(tn))[0]
                s['n_valid90_bottom'] = float(vn)
                s['np_overlap_v'] = float(vp - vn)
        out[c] = s
    return out


def verdict(h1, h0):
    """H1 against the frozen stage-1 criteria, every corner.  N/P overlap is the spec's own quantity (tail-validity windows of the
    two pairs, as measured in review_circuit.md), taken from the dump-free control H0 because with dump devices the tails are valid
    everywhere; the dump gate Vref must sit inside that window with at least half the limit (0.125 V) on each side."""
    v = {}
    for c, s in h1.items():
        vref = 0.48 * s['vdd']
        s['np_overlap_v'] = h0[c]['np_overlap_v']
        s['vref_margin_v'] = float(min(vref - h0[c]['n_valid90_bottom'], h0[c]['p_valid90_top'] - vref))
        v[c] = dict(
            runs_ok=s['n_bad'] == 0,
            cm=s['cm_dev_mid'] <= LIM['cm_half'], cm_strict=s['cm_span'] <= LIM['cm_half'],
            a1_extremes=s['a1_ext'] >= LIM['a1_min'], a1_all=s['a1_min_all'] >= LIM['a1_min'],
            spread=s['a1_spread_all'] <= LIM['a1_spread'], spread_tb2=s['a1_spread_tb2'] <= LIM['a1_spread'],
            overlap=s['np_overlap_v'] >= LIM['overlap'] and s['vref_margin_v'] >= LIM['overlap'] / 2, margin=s['margin_min'] >= LIM['margin'],
            f3db=s['f3db_min'] >= LIM['f3db'])
        v[c]['all_gate'] = all(v[c][k] for k in ('runs_ok', 'cm', 'a1_extremes', 'spread', 'overlap', 'margin'))
    return v


def f(x, fmt='%.3f'):
    return 'nan' if x is None or (isinstance(x, float) and np.isnan(x)) else fmt % x


def tables(summ, verd):
    L = []
    cs = list(summ['H1'])
    L.append('### Hybrid + dump (H1): the candidate, per corner')
    L.append('')
    L.append('| corner | CM min..max (V) | CM span (mV) | A1 at 0.05 / 2.35 V | A1 min..max over VIC | spread (47 pts / TB2 7 pts) | N/P overlap (V) / Vref margin (V) / handover width 10 % (V) | min margin (mV, device) | f3dB min (MHz) | verdict |')
    L.append('|---|---|---|---|---|---|---|---|---|---|')
    for c in cs:
        s, w = summ['H1'][c], verd[c]
        L.append('| %s | %.3f..%.3f | %.0f | %.2f / %.2f | %.2f..%.2f | %.2f / %.2f | %.3f / %.3f / %.3f | %.0f (%s) | %.0f | %s |' % (
            c, s['cm_min'], s['cm_max'], 1e3 * s['cm_span'], s['a1_lo'], s['a1_hi'], s['a1_min_all'], s['a1_max_all'],
            s['a1_spread_all'], s['a1_spread_tb2'], s['np_overlap_v'], s['vref_margin_v'], s['handover_w10'], 1e3 * s['margin_min'], s['margin_dev'], s['f3db_min'] / 1e6,
            'PASS' if w['all_gate'] else 'FAIL'))
    L.append('')
    L.append('### Control without dump devices (H0): what the dump has to cure')
    L.append('')
    L.append('| corner | CM min..max (V) | CM span (V) | A1 at 0.05 / 2.35 V | spread (47 pts) | PMOS tail valid up to (V) | NMOS tail valid from (V) | overlap, review definition (V) |')
    L.append('|---|---|---|---|---|---|---|---|')
    for c in cs:
        s = summ['H0'][c]
        L.append('| %s | %.3f..%.3f | %.3f | %.2f / %.2f | %.2f | %s | %s | %s |' % (
            c, s['cm_min'], s['cm_max'], s['cm_span'], s['a1_lo'], s['a1_hi'], s['a1_spread_all'], f(s['p_valid90_top']),
            f(s['n_valid90_bottom']), f(s['np_overlap_v'])))
    L.append('')
    L.append('### PMOS-only, Option A (shake-down variant)')
    L.append('')
    L.append('| corner | CM min..max (V) | CM span (V) | A1 at 0.05 V | A1 at 1.3 V | PMOS tail valid up to (V) |')
    L.append('|---|---|---|---|---|---|')
    for c in cs:
        s = summ['A'][c]
        rs = BY['A'][c]
        vic = np.array([r['params']['vic'] for r in rs])
        a1 = arr(rs, 'a1')
        L.append('| %s | %.3f..%.3f | %.3f | %.2f | %.2f | %s |' % (c, s['cm_min'], s['cm_max'], s['cm_span'], s['a1_lo'],
                                                             a1[int(np.argmin(np.abs(vic - 1.3)))], f(s['p_valid90_top'])))
    L.append('')
    L.append('### Dump devices at work (H1): where each pair hands over, tail-current constancy')
    L.append('')
    L.append('| corner | Vref (V) | PMOS pair share = 50 % at VIC (V) | NMOS pair share = 50 % at VIC (V) | both pairs >= 10 % from..to (V) | gm(P)+gm(N) min/max | I_tail,P span (%) | I_tail,N span (%) | idd mean (uA) | idd span (uA) |')
    L.append('|---|---|---|---|---|---|---|---|---|---|')
    for c in cs:
        s = summ['H1'][c]
        L.append('| %s | %.3f | %s | %s | %s..%s | %.2f | %.1f | %.1f | %.0f | %.1f |' % (
            c, 0.48 * s['vdd'], f(s['p_share_50']), f(s['n_share_50']), f(s['n_bottom_10']), f(s['p_top_10']),
            s['gm_sum_ratio_min_over_max'], s['itail_p_span_pct'], s['itail_n_span_pct'], 1e6 * s['idd_mean'], 1e6 * s['idd_span']))
    L.append('')
    L.append('### Saturation margins |VDS|-|VDsat| (mV), minimum over the VIC sweep, H1')
    L.append('')
    devs = sorted(summ['H1'][cs[0]]['margins'])
    L.append('| device | ' + ' | '.join(cs) + ' |')
    L.append('|---|' + '---|' * len(cs))
    for d in devs:
        L.append('| %s | ' % d + ' | '.join('%.0f' % (1e3 * summ['H1'][c]['margins'][d]) for c in cs) + ' |')
    return '\n'.join(L) + '\n'


def lut_check(by, sizing):
    """LUT prediction vs SPICE operating point at tt, each device with its pair fully on (PMOS pair VIC=0.05, NMOS pair VIC=2.35,
    the rest at 1.25 V): ID error, gm/ID error, |VGS| error, plus the predicted vs simulated A1 of the two paths."""
    rs = by['H1']['tt_27c_3v30']
    vic = np.array([r['params']['vic'] for r in rs])
    dev = sizing['devices']
    rows = []
    for inst_, key, at in (('mp1', 'MP1', 0.05), ('mpd1', 'MP1', 1.95), ('mn1', 'MN1', 2.35), ('mnd1', 'MN1', 0.05), ('m5a', 'M5', 1.25),
                          ('m3a', 'M3', 1.25), ('mnt', 'MNT', 1.25), ('mpt', 'MPT', 1.25)):
        i = int(np.argmin(np.abs(vic - at)))
        r = rs[i]['metrics']
        d = dev[key]
        idp = d['ID'] * (1.0 if key in ('M3', 'MNT', 'MPT') else 1.0)
        rows.append(dict(device=inst_, vic=float(vic[i]), id_pred_uA=1e6 * idp, id_sim_uA=1e6 * r['id_' + inst_],
                         id_err_pct=100 * (r['id_' + inst_] / idp - 1), gmid_pred=d['gmid'], gmid_sim=r['gm_' + inst_] / r['id_' + inst_],
                         vgs_pred=d.get('VGS'), vgs_sim=r['vgs_' + inst_]))
    pr = sizing['predicted']
    a1 = arr(rs, 'a1')
    return dict(rows=rows, a1_p_pred=pr['a1_p'], a1_p_sim=float(a1[int(np.argmin(np.abs(vic - 0.05)))]),
                a1_n_pred=pr['a1_n'], a1_n_sim=float(a1[int(np.argmin(np.abs(vic - 2.35)))]))


def lut_table(lc):
    L = ['| device (state) | VIC (V) | ID pred (uA) | ID sim (uA) | error | gm/ID pred | gm/ID sim | VGS pred (V) | VGS sim (V) |', '|---|---|---|---|---|---|---|---|---|']
    for r in lc['rows']:
        L.append('| %s | %.2f | %.1f | %.1f | %+.1f %% | %.1f | %.1f | %s | %.3f |' % (
            r['device'], r['vic'], r['id_pred_uA'], r['id_sim_uA'], r['id_err_pct'], r['gmid_pred'], r['gmid_sim'],
            ('%.3f' % r['vgs_pred']) if r['vgs_pred'] else '-', r['vgs_sim']))
    L.append('')
    L.append('A1 predicted / simulated at tt: PMOS path %.2f / %.2f, NMOS path %.2f / %.2f' % (
        lc['a1_p_pred'], lc['a1_p_sim'], lc['a1_n_pred'], lc['a1_n_sim']))
    return '\n'.join(L) + '\n'


def plots(by):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    os.makedirs(PLOTS, exist_ok=True)
    cols = ['#1f77b4', '#d62728', '#9467bd', '#2ca02c', '#ff7f0e', '#17becf', '#8c564b', '#7f7f7f']
    cs = list(by['H1'])
    for key, ylabel, fname in (('cm', 'stage-1 output common mode (V)', 'cm_vs_vic.png'), ('a1', 'differential gain A1', 'gain_vs_vic.png')):
        fig, axs = plt.subplots(1, 3, figsize=(15, 4.2), sharey=(key == 'a1'))
        for ax, v, title in zip(axs, ('A', 'H0', 'H1'), ('PMOS-only (A)', 'hybrid, no dump (H0)', 'hybrid + dump (H1)')):
            for c, col in zip(cs, cols):
                rs = by[v][c]
                ax.plot([r['params']['vic'] for r in rs], arr(rs, key), color=col, lw=1.4, label=c)
            ax.set_title(title)
            ax.set_xlabel('input common mode VIC (V)')
            ax.grid(alpha=.3)
        axs[0].set_ylabel(ylabel)
        if key == 'a1':
            for ax in axs:
                ax.axhline(LIM['a1_min'], color='k', ls='--', lw=.8)
        axs[2].legend(fontsize=7, loc='best')
        fig.tight_layout()
        fig.savefig(os.path.join(PLOTS, fname), dpi=110)
        plt.close(fig)
    # pair shares (H1) at three corners
    fig, ax = plt.subplots(figsize=(6.5, 4))
    for c, col in zip(cs, cols):
        rs = by['H1'][c]
        vic = [r['params']['vic'] for r in rs]
        sp = (arr(rs, 'id_mp1') + arr(rs, 'id_mp2')) / (arr(rs, 'id_mp1') + arr(rs, 'id_mp2') + arr(rs, 'id_mpd1') + arr(rs, 'id_mpd2'))
        sn = (arr(rs, 'id_mn1') + arr(rs, 'id_mn2')) / (arr(rs, 'id_mn1') + arr(rs, 'id_mn2') + arr(rs, 'id_mnd1') + arr(rs, 'id_mnd2'))
        ax.plot(vic, sp, color=col, lw=1.2)
        ax.plot(vic, sn, color=col, lw=1.2, ls='--')
    ax.set_xlabel('VIC (V)')
    ax.set_ylabel('share of tail current in the input pair')
    ax.set_title('H1: PMOS pair (solid) and NMOS pair (dashed), all corners')
    ax.grid(alpha=.3)
    fig.tight_layout()
    fig.savefig(os.path.join(PLOTS, 'pair_share_vs_vic.png'), dpi=110)
    plt.close(fig)
    # tail node and fold node voltages for H0 vs H1 (shows the tails staying in saturation)
    fig, ax = plt.subplots(figsize=(6.5, 4))
    for v, ls in (('H0', ':'), ('H1', '-')):
        rs = by[v]['ss_125c_3v00']
        vic = [r['params']['vic'] for r in rs]
        ax.plot(vic, arr(rs, 'mg_mpt'), color='#1f77b4', ls=ls, label='PMOS tail margin %s' % v)
        ax.plot(vic, arr(rs, 'mg_mnt'), color='#d62728', ls=ls, label='NMOS tail margin %s' % v)
    ax.axhline(0.05, color='k', ls='--', lw=.8)
    ax.set_xlabel('VIC (V)')
    ax.set_ylabel('tail |VDS|-|VDsat| (V), ss 125 C 3.0 V')
    ax.legend(fontsize=7)
    ax.grid(alpha=.3)
    fig.tight_layout()
    fig.savefig(os.path.join(PLOTS, 'tail_margin_ss125.png'), dpi=110)
    plt.close(fig)


BY = {}


def main():
    global BY
    BY = {v: load(v) for v in VARIANTS}
    summ = {v: summarize(v, BY[v]) for v in VARIANTS}
    verd = verdict(summ['H1'], summ['H0'])
    tb = tables(summ, verd)
    sizing = json.load(open(os.path.join(ROOT, 'results', 'spike_stage1_sizing.json')))
    ctl = {}
    for v in ('A', 'H0'):          # negative controls: the same judge applied to the variants that must NOT pass
        ctl[v] = dict(
            cm_fail=[c for c, x in summ[v].items() if x['cm_dev_mid'] > LIM['cm_half']],
            a1_ext_fail=[c for c, x in summ[v].items() if x['a1_ext'] < LIM['a1_min']],
            spread_fail=[c for c, x in summ[v].items() if x['a1_spread_all'] > LIM['a1_spread']],
            worst_cm_span=max(x['cm_span'] for x in summ[v].values()))
    tb += '\n### Same judge on the variants that must not pass (corners failing each criterion)\n\n| variant | CM +-0.15 V | A1 at the extremes >= 4 | spread <= 2.2 | worst CM span (V) |\n|---|---|---|---|---|\n'
    for v in ('A', 'H0'):
        tb += '| %s | %d of 8 | %d of 8 | %d of 8 | %.2f |\n' % (v, len(ctl[v]['cm_fail']), len(ctl[v]['a1_ext_fail']), len(ctl[v]['spread_fail']), ctl[v]['worst_cm_span'])
    lc = lut_check(BY, sizing)
    tb += '\n### LUT prediction vs SPICE at tt (the sizing script against the simulator)\n\n' + lut_table(lc)
    out = dict(limits=LIM, summary=summ, verdict=verd, all_h1_pass=all(w['all_gate'] for w in verd.values()),
               lut_vs_spice=lc, controls=ctl, sizing_tag=sizing.get('tag'), sizing_params=sizing['params'])
    for v in VARIANTS:                       # shares are bulky: keep in the json, but rounded
        for c in out['summary'][v]:
            for k in ('share_p', 'share_n'):
                if k in out['summary'][v][c]:
                    out['summary'][v][c][k] = [round(x, 4) for x in out['summary'][v][c][k]]
    with open(os.path.join(ROOT, 'results', 'spike_stage1.json'), 'w') as fh:
        json.dump(out, fh, indent=1)
    with open(os.path.join(RES, 'tables.md'), 'w') as fh:
        fh.write(tb)
    plots(BY)
    print(tb)
    print('H1 passes every gate at every corner:', out['all_h1_pass'])
    for c, w in verd.items():
        print(c, {k: x for k, x in w.items() if not x})


if __name__ == '__main__':
    main()
