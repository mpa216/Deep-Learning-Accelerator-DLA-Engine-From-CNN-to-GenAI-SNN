#!/usr/bin/env python3
"""facts_check.py - live evidence for the 'ten facts that bite' of handoff sec. 6.1 (facts 1, 2, 4, 8
and the file-name/key behaviour; facts 3, 5, 6, 7, 9, 10 are covered by validate_vs_kit.py,
spot_check.py, sizing/selftest_gmid.py and the README text).

usage: python3 facts_check.py <dir-with-mat-files> [suffix-of-mat-name]
       e.g. python3 lut_regen/facts_check.py luts            (regenerated tables)
            python3 lut_regen/facts_check.py <kit simulation dir>
"""
import contextlib
import io
import os
import shutil
import sys
import tempfile
import numpy as np
from scipy.io import loadmat
from pygmid import Lookup

d = sys.argv[1]
for dev in ('nfet_03v3', 'pfet_03v3', 'nfet_05v0', 'pfet_05v0'):
    p = os.path.join(d, dev + '.mat')
    if not os.path.isfile(p):
        print(f'--- {dev}: {p} not present, skipped')
        continue
    m = loadmat(p)
    keys = [k for k in m if not k.startswith('__')]
    s = m[keys[0]][0, 0]
    names = s.dtype.names
    print(f'--- {dev}  ({p})')
    print(f'fact 1: loadmat keys={keys}; struct fields={list(names)}')
    for want in ('ID', 'VT', 'GM', 'GMB', 'GDS', 'CGG', 'CGB', 'CGD', 'CGS', 'CDD', 'CSS', 'STH', 'SFL'):
        assert want in names, want
    print('        no leakage/VDSAT field:', not any(n in names for n in ('IG', 'IGATE', 'VDSAT', 'VDS_SAT')))
    print('        ID shape', s['ID'].shape, '(= [L, VGS, VDS, VSB])')
    L = np.ravel(s['L'])
    vgs = np.ravel(s['VGS'])
    vds = np.ravel(s['VDS'])
    vsb = np.ravel(s['VSB'])
    print(f'fact 2: CORNER={"".join(np.ravel(s["CORNER"]))} TEMP={float(s["TEMP"][0,0]):.2f} K W={float(s["W"][0,0])} NFING={int(s["NFING"][0,0])}')
    print(f'        L={list(np.round(L, 3))}')
    print(f'        VGS {vgs.min():.3f}..{vgs.max():.3f} step {np.diff(vgs).mean()*1000:.1f} mV ({len(vgs)} pts); '
          f'VDS {vds.min():.3f}..{vds.max():.3f} ({len(vds)} pts); VSB={list(np.round(np.abs(vsb), 3))}')
    if dev.startswith('p'):
        idm = np.nanmin(s['ID'])
        print(f'fact 4: PMOS stored as magnitudes: min(ID)={idm:.3e} (>=0 expected), min(VT)={np.nanmin(s["VT"]):.3f} (>0), '
              f'VGS min {vgs.min()} (>=0)')

# fact 8: non-monotonic ratios
t = Lookup(os.path.join(d, 'nfet_03v3.mat'))
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    a = t.lookup('GM_CGG', GM_ID=12, L=0.5, VDS=1.0, VSB=0)
    b = t.lookup('GM_ID', GM_GDS=100, L=0.5, VDS=1.0, VSB=0)
    c = t.lookup('ID_W', GM_CGG=2 * np.pi * 3e9, L=0.5, VDS=1.0, VSB=0)
print('fact 8: GM_ID as X -> scalar', float(a), '(strong-inversion branch);')
print(f'        X=GM_GDS (non-monotonic in VGS) -> {np.asarray(b).ravel()[:3]} ; captured prints: {buf.getvalue().strip()[:200]!r}')
print(f'        X=GM_CGG=2*pi*3GHz -> ID_W {np.asarray(c).ravel()[:3]}')

# file name differs from struct key
with tempfile.TemporaryDirectory() as tmp:
    q = os.path.join(tmp, 'totally_different_name.mat')
    shutil.copy(os.path.join(d, 'nfet_03v3.mat'), q)
    x = Lookup(q)
    print('file-name test: Lookup(totally_different_name.mat) works, VSB =', list(np.round(np.abs(x['VSB']), 3)))
