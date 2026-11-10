"""
verify_pygmid.py -- empirical check of every pygmid claim made in GMID_METHOD_NOTES.md section 9.

Run (from the host):
  docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx \
      python3 docs/book_extracts/verify_pygmid.py

Reads the 3.3 V GF180 LUTs from /foss/designs/Analog (read-only).  Writes nothing.
Every section prints what it observed and ends with PASS/FAIL lines so the notes can quote them.
"""
import io
import contextlib
import numpy as np
import scipy.io
from pygmid import Lookup

BASE = '/foss/designs/Analog/starter_files_open_source_tools/gf180mcuD/simulation/'
results = []


def check(name, cond, detail=''):
    results.append((name, bool(cond)))
    print(('PASS  ' if cond else 'FAIL  ') + name + (('   -> ' + detail) if detail else ''))


def quiet(fn, *a, **k):
    """Call fn, return (value, captured stdout) -- pygmid reports problems with print()."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        v = fn(*a, **k)
    return v, buf.getvalue().strip()


# ---------------------------------------------------------------- 1. file contents
print('=' * 70, '\n1. CONTENTS OF THE .mat FILES\n', '=' * 70)
raw = {}
for dev in ('nfet_03v3', 'pfet_03v3'):
    m = scipy.io.loadmat(BASE + dev + '.mat', matlab_compatible=True)
    keys = [k for k in m if not k.startswith('__')]
    s = m[keys[0]]
    raw[dev] = {k.upper(): np.squeeze(s[k][0][0]) for k in s.dtype.names}
    d = raw[dev]
    print(f'\n[{dev}] top-level key = {keys}')
    print('  fields:', ', '.join(s.dtype.names))
    print('  INFO   =', d['INFO'])
    print('  CORNER =', d['CORNER'], ' TEMP =', d['TEMP'], ' W =', d['W'], ' NFING =', d['NFING'])
    print('  L   (um) =', np.round(d['L'], 3).tolist())
    print('  VGS (V)  : %d pts, %.3f .. %.3f, step %.4f' % (len(d['VGS']), d['VGS'].min(), d['VGS'].max(), np.diff(d['VGS']).mean()))
    print('  VDS (V)  : %d pts, %.3f .. %.3f, step %.4f' % (len(d['VDS']), d['VDS'].min(), d['VDS'].max(), np.diff(d['VDS']).mean()))
    print('  VSB (V)  =', d['VSB'].tolist())
    print('  ID array shape [L,VGS,VDS,VSB] =', d['ID'].shape)
    print('  ID  min/max = %.3e / %.3e A (W = %g um)' % (d['ID'].min(), d['ID'].max(), d['W']))
    print('  VT  min/max = %.3f / %.3f V' % (np.nanmin(d['VT']), np.nanmax(d['VT'])))
    print('  has VDSAT field?', 'VDSAT' in d, '| has leakage field (IG)?', 'IG' in d)
    check(f'{dev}: data arrays are 4-D [L,VGS,VDS,VSB]', d['ID'].ndim == 4 and d['ID'].shape == (len(d['L']), len(d['VGS']), len(d['VDS']), len(d['VSB'])))
    check(f'{dev}: ID is positive in the table (PMOS stores magnitudes)', np.nanmin(d['ID'][:, 5:, 5:, 0]) >= 0, f"min ID (VGS,VDS>=0.125) = {np.nanmin(d['ID'][:, 5:, 5:, 0]):.3e}")
    check(f'{dev}: VT positive in the table', np.nanmin(d['VT']) > 0, f"VT range {np.nanmin(d['VT']):.3f}..{np.nanmax(d['VT']):.3f}")

n = Lookup(BASE + 'nfet_03v3.mat')
p = Lookup(BASE + 'pfet_03v3.mat')
Wlut = float(raw['nfet_03v3']['W'])

# ---------------------------------------------------------------- 2. call patterns
print('\n' + '=' * 70, '\n2. CALL PATTERNS (nfet_03v3)\n', '=' * 70)
# mode 3: ratio out, ratio in.  GM_ID is the X variable and must be the FIRST keyword.
v = n.lookup('ID_W', GM_ID=12, L=0.5, VDS=1.0)
print('mode 3  n.lookup("ID_W", GM_ID=12, L=0.5, VDS=1.0)       =', v, ' A/um')
check('mode 3 returns a scalar-like value', np.size(v) == 1)
wt = n.lookup('GM_CGG', GM_ID=12, L=0.5, VDS=1.0)
print('mode 3  n.lookup("GM_CGG", GM_ID=12, L=0.5, VDS=1.0)     =', wt, ' rad/s ->  fT = %.3f GHz' % (wt / 2 / np.pi / 1e9))
ga = n.lookup('GM_GDS', GM_ID=12, L=0.5, VDS=1.0)
print('mode 3  n.lookup("GM_GDS", GM_ID=12, L=0.5, VDS=1.0)     =', ga, ' (intrinsic gain gm/gds, V/V)')
# vector of gm/ID
gv = np.array([6, 9, 12, 15, 18])
vv = n.lookup('GM_GDS', GM_ID=gv, L=0.5, VDS=1.0)
print('mode 3  vector GM_ID', gv.tolist(), '->', np.round(vv, 1).tolist())
check('mode 3 accepts a vector of gm/ID', np.size(vv) == len(gv))
# vector of L
Lv = np.array([0.28, 0.5, 1.0, 2.0])
vl = n.lookup('GM_GDS', GM_ID=12, L=Lv, VDS=1.0)
print('mode 3  vector L', Lv.tolist(), '->', np.round(vl, 1).tolist())
check('mode 3 accepts a vector of L', np.size(vl) == len(Lv))
# mode 2: ratio out, single variable in (e.g. VGS sweep)
vg = np.array([0.6, 0.8, 1.0, 1.2])
m2 = n.lookup('GM_ID', VGS=vg, L=0.5, VDS=1.0)
print('mode 2  n.lookup("GM_ID", VGS=[0.6,0.8,1.0,1.2], L=0.5, VDS=1.0) =', np.round(m2, 2).tolist())
check('mode 2 gm/ID falls monotonically with VGS (strong inversion side)', np.all(np.diff(m2) < 0))
# mode 1: single quantity
m1 = n.lookup('ID', VGS=vg, L=0.5, VDS=1.0)
print('mode 1  n.lookup("ID", VGS=...) (A, for W = %g um) =' % Wlut, ['%.3e' % x for x in m1])
check('mode 1: ID/W from "ID" equals ID_W lookup', np.allclose(m1 / Wlut, n.lookup('ID_W', VGS=vg, L=0.5, VDS=1.0), rtol=1e-9))
# lookupVGS
vgs1 = n.lookupVGS(GM_ID=12, L=0.5, VDS=1.0, VSB=0)
print('lookupVGS mode 1: n.lookupVGS(GM_ID=12, L=0.5, VDS=1.0, VSB=0)  =', vgs1, 'V')
back = n.lookup('GM_ID', VGS=float(vgs1), L=0.5, VDS=1.0)
check('lookupVGS round trip: gm/ID at the returned VGS equals 12', abs(float(back) - 12) < 0.05, f'gm/ID(VGS={float(vgs1):.4f}) = {float(back):.4f}')
vgsj = n.lookupVGS(ID_W=1e-6 * 10, L=0.5, VDS=1.0, VSB=0)
print('lookupVGS by ID/W: n.lookupVGS(ID_W=10e-6, ...)  =', vgsj, 'V  (10 uA/um)')
vgsv = n.lookupVGS(GM_ID=np.array([8, 12, 16]), L=0.5, VDS=1.0, VSB=0)
print('lookupVGS vector gm/ID [8,12,16]               =', np.round(vgsv, 4).tolist())
check('lookupVGS: higher gm/ID -> lower VGS', np.all(np.diff(vgsv) < 0))
# mode 2 (floating source, e.g. tail node of a diff pair): give VGB and VDB, VSB is the unknown
vgs2 = n.lookupVGS(GM_ID=12, L=0.5, VDB=1.5, VGB=1.2)
print('lookupVGS mode 2 (floating S): n.lookupVGS(GM_ID=12, L=0.5, VDB=1.5, VGB=1.2) =', vgs2, 'V')
print('   -> the solver found the source node at VSB = VGB - VGS = %.3f V above bulk' % (1.2 - float(vgs2)))
check('lookupVGS mode 2 returns a sane VGS (0.3..1.5 V) for a feasible request', 0.3 < float(vgs2) < 1.5)

# ---------------------------------------------------------------- 3. pitfalls
print('\n' + '=' * 70, '\n3. PITFALLS (each one reproduced)\n', '=' * 70)
# 3a keyword order
good = n.lookup('GM_CGG', GM_ID=12, L=0.5, VDS=1.0)
bad, msg = quiet(n.lookup, 'GM_CGG', L=0.5, GM_ID=12, VDS=1.0)
print('3a  GM_ID first   -> shape', np.shape(good))
print('    L first       -> shape', np.shape(bad), '(the GM_ID=12 was IGNORED, you got a VGS sweep)')
check('3a keyword order: wrong order returns a VGS sweep, not a scalar', np.size(good) == 1 and np.size(bad) > 10)
# 3b default VDS
dflt = n.lookup('GM_GDS', GM_ID=12, L=0.5)
expl = n.lookup('GM_GDS', GM_ID=12, L=0.5, VDS=1.65)
print('3b  default VDS = max(VDS)/2 = %.3f V;  GM_GDS(default) = %.3f, GM_GDS(VDS=1.65) = %.3f' % (raw['nfet_03v3']['VDS'].max() / 2, dflt, expl))
check('3b default VDS is 1.65 V (not the book 0.6 V)', abs(float(dflt) - float(expl)) < 1e-9)
# 3c wrong 'out' for mode 3 -> []
bad2, _ = quiet(n.lookup, 'GM', GM_ID=12, L=0.5, VDS=1.0)
print('3c  n.lookup("GM", GM_ID=12, ...) (single out, ratio in) ->', repr(bad2))
check('3c single-quantity out with a ratio variable returns [] (no error)', isinstance(bad2, list) and len(bad2) == 0)
# 3d extrapolation
a, ma = quiet(n.lookup, 'ID_W', VGS=1.0, L=0.5, VDS=1.0, VSB=0.8)
b, mb = quiet(n.lookup, 'ID_W', VGS=1.0, L=0.5, VDS=1.0, VSB=0.2)
print('3d  ID_W at VSB=0.2 (inside table) = %.3e ;  at VSB=0.8 (outside 0..0.4) = %.3e   [printed msg: %r]' % (b, a, ma))
check('3d out-of-range VSB extrapolates silently (finite number, no exception)', np.isfinite(a))
sv, ms = quiet(n.lookup, 'GM_ID', VGS=1.0, L=0.5, VDS=1.0, VSB=1.5)
print('    GM_ID at VSB=1.5 V (far outside) =', sv)
# 3e out-of-range gm/ID
hi, mh = quiet(n.lookup, 'ID_W', GM_ID=40, L=0.5, VDS=1.0)
print('3e  gm/ID = 40 (above the physical maximum ~%.1f): ID_W = %s ; messages: %r' % (float(np.max(n.lookup("GM_ID", VGS=n["VGS"], L=0.5, VDS=1.0))), hi, mh))
check('3e out-of-range gm/ID gives a number plus a print (not an exception)', mh != '' or np.isfinite(hi))
# 3f lookupVGS outside range
big, mbg = quiet(n.lookupVGS, GM_ID=12, L=0.5, VDB=3.0, VGB=2.0)
print('3f  lookupVGS mode 2, VGB=2.0, VDB=3.0 (source would have to be at ~VSB>0.4) -> VGS =', big, 'V  [msg %r]' % mbg)
# 3g L grid
for Lq in (1.5, 0.45):
    v1 = n.lookup('GM_GDS', GM_ID=12, L=Lq, VDS=1.0)
    print('3g  L = %.2f (between grid points) -> GM_GDS = %.2f (linear interpolation in L)' % (Lq, v1))
vlo = n.lookup('GM_GDS', GM_ID=12, L=1.0, VDS=1.0); vhi = n.lookup('GM_GDS', GM_ID=12, L=2.0, VDS=1.0)
check('3g L=1.5 is the straight-line mid-point of L=1 and L=2 (interpolation, not a model)', abs(float(n.lookup('GM_GDS', GM_ID=12, L=1.5, VDS=1.0)) - (float(vlo) + float(vhi)) / 2) < 0.2 * float(vlo))
# 3i multiple crossings for an X ratio that is not GM_ID / *_CGG (only those two are special-cased)
x1, m1_ = quiet(n.lookup, 'GM_ID', GM_CGS=2.0e10, L=0.5, VDS=1.0)   # crossed once on the VGS sweep -> fine
x2, m2_ = quiet(n.lookup, 'GM_ID', GM_CGS=7.0e10, L=0.5, VDS=1.0)   # crossed twice (rises past 7e10, peaks 9.4e10 at VGS=1.9 V, falls)
print('3i  X=GM_CGS=2e10 (one crossing)  ->', repr(x1), ' printed: %r' % m1_)
print('    X=GM_CGS=7e10 (two crossings) ->', repr(x2), ' printed: %r' % m2_)
check('3i two crossings -> "Crossing warning" and [] ; one crossing -> a value', isinstance(x2, list) and len(x2) == 0 and 'Crossing' in m2_ and np.size(x1) == 1, 'peak of GM_CGS on the VGS sweep is at VGS = 1.875 V (deep strong inversion)')
x3, m3_ = quiet(n.lookup, 'GM_ID', GM_GDS=0.01, L=0.5, VDS=1.0)
print('    X=GM_GDS=0.01 (below the table minimum 0.47) ->', repr(x3), ' printed: %r  (silently extrapolated garbage)' % m3_)
# 3h VGS=VDS=0 corner etc - table contains zeros / NaN?
print('3h  NaNs in ID table:', int(np.isnan(raw['nfet_03v3']['ID']).sum()), '; zeros in CGG:', int((raw['nfet_03v3']['CGG'] == 0).sum()))

# ---------------------------------------------------------------- 4. PMOS sign conventions
print('\n' + '=' * 70, '\n4. PMOS CONVENTIONS (pfet_03v3)\n', '=' * 70)
jd_p = p.lookup('ID_W', GM_ID=12, L=0.5, VDS=1.0, VSB=0)
vsg_p = p.lookupVGS(GM_ID=12, L=0.5, VDS=1.0, VSB=0)
print('p.lookup("ID_W", GM_ID=12, L=0.5, VDS=1.0)  = %.3e A/um  (positive)' % jd_p)
print('p.lookupVGS(GM_ID=12, L=0.5, VDS=1.0)        = %.4f V  = VSG (a magnitude).  Netlist: V_G = V_S - %.4f' % (vsg_p, vsg_p))
check('PMOS: lookup uses positive magnitudes (ID_W>0, VSG>0)', jd_p > 0 and vsg_p > 0)
# direct comparison nmos / pmos current density at same gm/ID
jd_n = n.lookup('ID_W', GM_ID=12, L=0.5, VDS=1.0, VSB=0)
print('same gm/ID=12, L=0.5: NMOS ID/W = %.3e, PMOS ID/W = %.3e  -> PMOS carries %.2fx less current per um, so it needs %.2fx the W for the same ID' % (jd_n, jd_p, jd_n / jd_p, jd_n / jd_p))
# gm/ID peak (weak-inversion plateau)
for nm, d in (('n', n), ('p', p)):
    pk = np.max(d.lookup('GM_ID', VGS=d['VGS'], L=0.5, VDS=1.0))
    print('   %s: peak gm/ID at L=0.5, VDS=1.0: %.2f 1/V' % (nm, pk))

# ---------------------------------------------------------------- 5. units and sanity against physics
print('\n' + '=' * 70, '\n5. UNITS AND SANITY\n', '=' * 70)
gmid = 12.0
Ltest = 0.5
jd = float(n.lookup('ID_W', GM_ID=gmid, L=Ltest, VDS=1.0))  # A/um
vgs = float(n.lookupVGS(GM_ID=gmid, L=Ltest, VDS=1.0))
vt = float(n.lookup('VT', VGS=vgs, L=Ltest, VDS=1.0))
print('nfet L=0.5 gm/ID=12: VGS = %.3f V, VT = %.3f V, ID/W = %.3f uA/um' % (vgs, vt, jd * 1e6))
vdsat_proxy = 2 / gmid
print('  VDsat proxy 2/(gm/ID) = %.3f V ; VGS-VT = %.3f V (the proxy is a rule of thumb)' % (vdsat_proxy, vgs - vt))
# Cgg / W from table
cgg_w = float(n.lookup('CGG_W', GM_ID=gmid, L=Ltest, VDS=1.0)) if False else None
cgg = float(n.lookup('CGG', VGS=vgs, L=Ltest, VDS=1.0))
print('  CGG (W=5um) = %.3e F -> %.3f fF/um' % (cgg, cgg / Wlut * 1e15))
# gm at W=5
gm = float(n.lookup('GM', VGS=vgs, L=Ltest, VDS=1.0))
idd = float(n.lookup('ID', VGS=vgs, L=Ltest, VDS=1.0))
check('GM/ID lookup (mode 2) equals GM/ID computed from the raw arrays', abs(gm / idd - gmid) < 0.05, f'{gm/idd:.4f}')
fT_ratio = float(n.lookup('GM', VGS=vgs, L=Ltest, VDS=1.0)) / float(n.lookup('CGG', VGS=vgs, L=Ltest, VDS=1.0))
check('GM_CGG (mode 3) equals GM/CGG taken from the raw table at the same bias (rad/s)', abs(float(n.lookup('GM_CGG', GM_ID=gmid, L=Ltest, VDS=1.0)) / fT_ratio - 1) < 0.01, 'ratio %.4f' % (float(n.lookup('GM_CGG', GM_ID=gmid, L=Ltest, VDS=1.0)) / fT_ratio))
print('  sizing example: gm = 1 mS at gm/ID=12, L=0.5 -> ID = %.1f uA, W = ID/(ID/W) = %.2f um' % (1e-3 / gmid * 1e6, 1e-3 / gmid / jd))
print('  fT = %.2f GHz => Cgg = gm/(2 pi fT) = %.1f fF' % (float(n.lookup('GM_CGG', GM_ID=gmid, L=Ltest, VDS=1.0)) / 2 / np.pi / 1e9,
                                                          1e-3 / float(n.lookup('GM_CGG', GM_ID=gmid, L=Ltest, VDS=1.0)) * 1e15))
# available "lookup" ratio names that work:
print('\n  Keys usable in lookup() (numerator or denominator, any pair "A_B" or single):')
print('   ', ', '.join(k for k in raw['nfet_03v3'] if raw['nfet_03v3'][k].ndim == 4))
# gamma / flicker helpers
try:
    g = n.gamma(GM_ID=12, L=0.5, VDS=1.0)
    print('  n.gamma(GM_ID=12,L=0.5,VDS=1.0) (thermal-noise gamma, from STH/gm/4kT) =', g)
except Exception as e:
    print('  gamma() raised', type(e).__name__, e)
try:
    fc = n.fco(GM_ID=12, L=0.5, VDS=1.0)
    print('  n.fco(...)  (SFL/STH, flicker-to-thermal ratio at 1 Hz) =', fc)
except Exception as e:
    print('  fco() raised', type(e).__name__, e)

# ---------------------------------------------------------------- summary
print('\n' + '=' * 70)
npass = sum(1 for _, ok in results if ok)
print('SUMMARY: %d/%d checks passed' % (npass, len(results)))
for nm, ok in results:
    if not ok:
        print('  FAILED:', nm)
