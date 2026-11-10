#!/usr/bin/env python3
"""selftest_gmid.py - self-test of sizing/gmid_gf180.py against the numbers recorded in the handoff
(sec. 6.3 expected output, sec. 6.6 sanity tables, sec. 6.1 'facts that bite').

usage:  python3 sizing/selftest_gmid.py            # uses $GF180_LUT_DIR / luts / kit (see gmid_gf180.py)
        GF180_LUT_DIR=<kit simulation dir> python3 sizing/selftest_gmid.py   # force the original kit tables

Exit code 0 only if every hard check passes.  The VSB = 0 values of the regenerated tables and of
the kit tables must both pass the same tolerances (kit and regenerated agree to ~0.1 %).
"""
import os
import sys
import warnings
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gmid_gf180 as g

fails = []
total = 0


def check(label, got, exp, rel=None, absol=None):
    """pass if |got-exp| <= max(rel*|exp|, absol)."""
    global total
    total += 1
    tol = max((rel or 0) * abs(exp), absol or 0)
    ok = abs(got - exp) <= tol
    if not ok:
        fails.append(f'{label}: got {got:.5g} expected {exp:.5g} (tol {tol:.3g})')
    return ok


print('LUT files:', g.lut_path('nfet_03v3'), '|', g.lut_path('pfet_03v3'))
nf, pf = g.lut('nfet_03v3'), g.lut('pfet_03v3')
print('nfet VSB grid:', list(np.round(nf['VSB'], 3)), ' L grid:', list(nf['L']))

# ---------------------------------------------------------------------------------------------
# 1. sec. 6.3: the one-line sizing example
# ---------------------------------------------------------------------------------------------
exp63 = {'nfet_03v3': dict(ID=83.3, W=30.8, nf=7, VGS=0.802, fT=3.30, gm_gds=153, Cgg=48.3, Cgd=5.2, Cdd=28.1),
         'pfet_03v3': dict(ID=83.3, W=107.9, nf=22, VGS=0.901, fT=0.78, gm_gds=220, Cgg=203.8, Cgd=16.7, Cdd=89.6)}
for name, e in exp63.items():
    r = g.size(name, gm=1e-3, gmid=12, L=0.5, VDS=1.0)
    got = dict(ID=r['ID'] * 1e6, W=r['W'], nf=r['nf'], VGS=r['VGS'], fT=r['fT'] / 1e9, gm_gds=r['gm_gds'],
               Cgg=r['Cgg'] * 1e15, Cgd=r['Cgd'] * 1e15, Cdd=r['Cdd'] * 1e15)
    for k in e:
        check(f'6.3 {name} {k}', got[k], e[k], rel=0.02 if k != 'nf' else 0, absol=0.0015 if k == 'VGS' else 0.01)
    print(f"6.3 {name}: " + ' '.join(f'{k}={got[k]:.4g}' for k in e))

# guards
for label, kw, frag in [('VSB too large', dict(VSB=float(nf['VSB'].max()) + 0.4), 'outside LUT'),
                        ('gm/ID too large', dict(gmid=29), 'gm/ID=29')]:
    total += 1
    try:
        g.size('nfet_03v3', 1e-3, kw.get('gmid', 12), 0.5, 1.0, VSB=kw.get('VSB', 0.0))
        fails.append(f'guard {label}: no exception')
    except ValueError as ex:
        ok = frag in str(ex)
        print(f'guard OK ({label}):', ex)
        if not ok:
            fails.append(f'guard {label}: wrong message {ex}')
for label, kw in [('L off the grid (info)', dict(L=1.5))]:
    total += 1
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        g.at_gmid('nfet_03v3', 'ID_W', 12, kw['L'], 1.0)
    if not any('not on grid' in str(x.message) for x in w):
        fails.append('L-off-grid warning missing')
    else:
        print('guard OK (L=1.5 -> warning "not on grid")')

# ---------------------------------------------------------------------------------------------
# 2. sec. 6.6 sanity tables (VDS=1.0, VSB=0)
# ---------------------------------------------------------------------------------------------
GMIDS = [5, 8, 10, 12, 15, 18, 20]
def row(s): return [float(x) for x in s.split('/')]
N = {   # L: (fT GHz, gm/gds, ID/W uA/um, VGS V)
    0.28: ('16.2 / 11.9 / 9.48 / 7.38 / 4.75 / 2.68 / 1.61', '25 / 28 / 28 / 29 / 29 / 29 / 29', '24.8 / 10.9 / 6.73 / 4.24 / 2.09 / 0.94 / 0.49', '0.938 / 0.807 / 0.754 / 0.712 / 0.659 / 0.610 / 0.576'),
    0.4:  ('10.1 / 7.22 / 5.77 / 4.54 / 3.01 / 1.78 / 1.09', '67 / 82 / 88 / 91 / 93 / 93 / 91', '19.8 / 8.43 / 5.17 / 3.24 / 1.61 / 0.73 / 0.38', '1.013 / 0.877 / 0.823 / 0.780 / 0.728 / 0.680 / 0.646'),
    0.5:  ('7.32 / 5.17 / 4.14 / 3.30 / 2.24 / 1.36 / 0.85', '100 / 133 / 145 / 153 / 159 / 158 / 155', '17.0 / 7.10 / 4.32 / 2.70 / 1.33 / 0.60 / 0.31', '1.038 / 0.900 / 0.844 / 0.802 / 0.749 / 0.701 / 0.667'),
    1.0:  ('2.23 / 1.48 / 1.17 / 0.93 / 0.64 / 0.41 / 0.26', '232 / 304 / 330 / 344 / 350 / 340 / 325', '9.29 / 3.67 / 2.21 / 1.38 / 0.69 / 0.32 / 0.17', '1.038 / 0.891 / 0.834 / 0.791 / 0.739 / 0.693 / 0.660'),
    2.0:  ('0.58 / 0.37 / 0.28 / 0.22 / 0.15 / 0.09 / 0.06', '372 / 476 / 510 / 526 / 527 / 506 / 481', '4.67 / 1.75 / 1.03 / 0.63 / 0.31 / 0.14 / 0.07', '1.033 / 0.877 / 0.818 / 0.773 / 0.720 / 0.672 / 0.639'),
}
P = {
    0.28: ('5.89 / 4.08 / 3.22 / 2.49 / 1.58 / 0.86 / 0.47', '33 / 43 / 48 / 51 / 54 / 56 / 57', '9.37 / 3.99 / 2.48 / 1.58 / 0.79 / 0.35 / 0.17', '1.069 / 0.933 / 0.881 / 0.839 / 0.787 / 0.738 / 0.699'),
    0.4:  ('3.03 / 2.04 / 1.58 / 1.22 / 0.77 / 0.43 / 0.24', '70 / 103 / 120 / 134 / 149 / 160 / 164', '6.29 / 2.59 / 1.60 / 1.01 / 0.50 / 0.22 / 0.11', '1.127 / 0.986 / 0.932 / 0.890 / 0.838 / 0.789 / 0.751'),
    0.5:  ('1.99 / 1.32 / 1.02 / 0.78 / 0.50 / 0.27 / 0.15', '102 / 160 / 192 / 220 / 253 / 276 / 285', '4.93 / 2.00 / 1.23 / 0.77 / 0.38 / 0.17 / 0.08', '1.141 / 0.998 / 0.943 / 0.901 / 0.849 / 0.799 / 0.761'),
    1.0:  ('0.49 / 0.31 / 0.24 / 0.18 / 0.11 / 0.06 / 0.03', '222 / 365 / 450 / 526 / 619 / 681 / 699', '2.19 / 0.86 / 0.52 / 0.32 / 0.16 / 0.07 / 0.03', '1.148 / 0.999 / 0.943 / 0.899 / 0.846 / 0.796 / 0.757'),
}
worst = {}
for name, tab in [('nfet_03v3', N), ('pfet_03v3', P)]:
    for L, (sft, sgg, sid, svg) in tab.items():
        eft, egg, eid, evg = map(row, (sft, sgg, sid, svg))
        for i, gm in enumerate(GMIDS):
            got = dict(fT=g.at_gmid(name, 'GM_CGG', gm, L, 1.0) / (2 * np.pi) / 1e9,
                       gg=g.at_gmid(name, 'GM_GDS', gm, L, 1.0),
                       id=g.at_gmid(name, 'ID_W', gm, L, 1.0) * 1e6,
                       vg=g.vgs_at_gmid(name, gm, L, 1.0))
            exps = dict(fT=eft[i], gg=egg[i], id=eid[i], vg=evg[i])
            # table digits are 3 significant digits -> allow half a digit (<=0.6 %) plus 2 % model/grid slack;
            # the tiny ID/W entries (0.03-0.17) are printed with 1-2 digits so get an absolute 0.006 floor
            for k in got:
                lab = f'6.6 {name} L={L} gm/ID={gm} {k}'
                absol = {'fT': 0.006, 'gg': 0.6, 'id': 0.006, 'vg': 0.0015}[k]
                ok = check(lab, got[k], exps[k], rel=0.02, absol=absol)
                rel = abs(got[k] - exps[k]) / max(abs(exps[k]), 1e-9) if k != 'vg' else abs(got[k] - exps[k])
                if k not in worst or rel > worst[k][0]:
                    worst[k] = (rel, lab, got[k], exps[k])
print('6.6 worst deviations per quantity (fT/gg/id relative, vg absolute V):')
for k, (rel, lab, got, exp) in worst.items():
    print(f'   {k}: {rel:.4g}  at {lab} (got {got:.4g}, table {exp:.4g})')

# other 6.6 facts
check('6.6 max gm/ID nfet L=0.5', g.gmid_max(nf, 0.5, 1.0), 27.9, rel=0.01)
check('6.6 max gm/ID pfet L=0.5', g.gmid_max(pf, 0.5, 1.0), 27.0, rel=0.02)
for name, exp in [('nfet_03v3', (0.802, 0.869, 0.930)), ('pfet_03v3', (0.901, 0.985, 1.060))]:
    for vsb, e in zip((0.0, 0.2, 0.4), exp):
        check(f'6.6 body effect {name} VSB={vsb}', g.vgs_at_gmid(name, 12, 0.5, 1.0, vsb), e, absol=0.0025)
for name, exp in [('nfet_03v3', (1.10, 1.37, 1.57, 2.82)), ('pfet_03v3', None)]:
    if exp:
        for L, e in zip((0.28, 0.4, 0.5, 1.0), exp):
            check(f'6.6 Cgg/W {name} L={L}', g.at_gmid(name, 'CGG_W', 12, L, 1.0) * 1e15, e, rel=0.03)  # F/um -> fF/um
for L, (en, ep) in {0.28: (7.38, 2.49), 0.4: (4.54, 1.22), 0.5: (3.30, 0.78), 1.0: (0.93, 0.18)}.items():
    fn = g.at_gmid('nfet_03v3', 'GM_CGG', 12, L, 1.0) / 6.2832e9
    fp = g.at_gmid('pfet_03v3', 'GM_CGG', 12, L, 1.0) / 6.2832e9
    check(f'6.6 N/P fT ratio L={L}', fn / fp, en / ep, rel=0.04)
print('6.6 N/P fT ratio at gm/ID=12:', [round(g.at_gmid('nfet_03v3', 'GM_CGG', 12, L, 1.0) / g.at_gmid('pfet_03v3', 'GM_CGG', 12, L, 1.0), 2)
                                       for L in (0.28, 0.4, 0.5, 1.0)], '(table: 3.0 3.7 4.2 5.2)')

# ---------------------------------------------------------------------------------------------
# 3. cross-check WITHOUT pygmid: a plain numpy slice (L=0.5, VDS=1.0, VSB=0)
# ---------------------------------------------------------------------------------------------
t = nf
iL = int(np.argmin(abs(t['L'] - 0.5)))
iD = int(np.argmin(abs(t['VDS'] - 1.0)))
iB = 0
gm = t['GM'][iL, :, iD, iB]
idr = t['ID'][iL, :, iD, iB]
with np.errstate(all='ignore'):
    ratio = gm / idr
k = int(np.nanargmax(ratio))
# strong-inversion branch: right of the peak in VGS, i.e. VGS > VGS(peak); find gm/ID = 12
vgs = t['VGS']
sel = np.arange(len(vgs)) > k
x = np.interp(12.0, ratio[sel][::-1], vgs[sel][::-1])
jd = np.interp(x, vgs, idr / float(t['W']))
ft = np.interp(x, vgs, gm / (t['CGG'][iL, :, iD, iB])) / (2 * np.pi)
ggds = np.interp(x, vgs, gm / t['GDS'][iL, :, iD, iB])
print(f'numpy slice : VGS={x:.5f} ID/W={jd*1e6:.4f} uA/um fT={ft/1e9:.4f} GHz gm/gds={ggds:.2f}')
pv = g.vgs_at_gmid('nfet_03v3', 12, 0.5, 1.0)
pj = g.at_gmid('nfet_03v3', 'ID_W', 12, 0.5, 1.0)
pt = g.at_gmid('nfet_03v3', 'GM_CGG', 12, 0.5, 1.0) / (2 * np.pi)
pg = g.at_gmid('nfet_03v3', 'GM_GDS', 12, 0.5, 1.0)
print(f'pygmid      : VGS={pv:.5f} ID/W={pj*1e6:.4f} uA/um fT={pt/1e9:.4f} GHz gm/gds={pg:.2f}')
check('numpy vs pygmid VGS', x, pv, absol=0.002)
check('numpy vs pygmid ID/W', jd, pj, rel=0.01)
check('numpy vs pygmid fT', ft, pt, rel=0.01)
check('numpy vs pygmid gm/gds', ggds, pg, rel=0.01)

# ---------------------------------------------------------------------------------------------
# 4. the pygmid 'facts that bite' (6.1) as live probes (informational unless noted)
# ---------------------------------------------------------------------------------------------
print('--- facts that bite (6.1), live probes ---')
import io, contextlib
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    a_ok = nf.lookup('GM_CGG', GM_ID=12, L=0.5, VDS=1.0)
    a_bad = nf.lookup('GM_CGG', L=0.5, GM_ID=12)
total += 2
if np.size(a_ok) != 1:
    fails.append('fact5: ratio-first lookup is not a scalar')
if np.size(a_bad) < 100:
    fails.append(f'fact5: wrong keyword order did not return a sweep (size {np.size(a_bad)})')
print(f'fact 5: GM_ID first -> size {np.size(a_ok)}; GM_ID second -> size {np.size(a_bad)} (silently a VGS sweep)')
with contextlib.redirect_stdout(buf):
    d_def = float(nf.lookup('ID_W', GM_ID=12, L=0.5, VSB=0))
    d_165 = float(nf.lookup('ID_W', GM_ID=12, L=0.5, VDS=1.65, VSB=0))
    d_1 = float(nf.lookup('ID_W', GM_ID=12, L=0.5, VDS=1.0, VSB=0))
total += 1
if abs(d_def - d_165) > 1e-3 * d_165:
    fails.append('fact6: default VDS is not VDSmax/2')
print(f'fact 6: ID/W default VDS={d_def*1e6:.4f}  VDS=1.65 -> {d_165*1e6:.4f}  VDS=1.0 -> {d_1*1e6:.4f} uA/um')
vbx = float(nf['VSB'].max()) + 0.4
with contextlib.redirect_stdout(buf):
    ex = float(nf.lookup('ID_W', GM_ID=12, L=0.5, VDS=1.0, VSB=vbx))
print(f'fact 7: unguarded ID/W at VSB={vbx:.1f} V (outside table) = {ex*1e6:.4f} uA/um (extrapolated, never trust)')

print()
print(f'{total - len(fails)}/{total} checks passed')
for f in fails:
    print('FAIL', f)
sys.exit(1 if fails else 0)
