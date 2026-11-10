#!/usr/bin/env python3
"""spot_check.py - independent check of a LUT against direct ngspice operating points.

usage: python3 spot_check.py <lut.mat> <device> [--n 6] [--seed 1] [--corner typical --temp 27]
For N random (L, VGS, VDS, VSB) points (continuous values, NOT on the LUT grid, so the LUT
interpolation is exercised too) a one-transistor deck in the kit's style is simulated with
`.op` and ID, gm, gds, CGG(+overlap, as the converter defines it) are compared with a multilinear
interpolation of the LUT (scipy RegularGridInterpolator on the raw 4-D arrays).
Deck conventions are the kit's: NMOS source at 0, bulk at -VSB; PMOS source at 0, gate at -VGS,
drain at -VDS, bulk at +VSB (so the LUT magnitudes VSG, VSD, VBS apply directly).
"""
import argparse
import os
import re
import subprocess
import tempfile
import numpy as np
from scipy.io import loadmat
from scipy.interpolate import RegularGridInterpolator

ap = argparse.ArgumentParser()
ap.add_argument('lut')
ap.add_argument('device')
ap.add_argument('--n', type=int, default=6)
ap.add_argument('--seed', type=int, default=1)
ap.add_argument('--corner', default='typical')
ap.add_argument('--temp', type=float, default=27)
ap.add_argument('--tol', type=float, default=0.02)
ap.add_argument('--min-id', type=float, default=1e-6, help='offgrid mode: skip points whose LUT ID is below this [A] (0 = keep weak inversion)')
ap.add_argument('--mode', choices=['grid', 'offgrid', 'lmid'], default='grid',
                help='grid: every coordinate is a LUT grid node (tests the DATA, expect ~0.1-0.5%%, limited by the 4-digit '
                     'text the sweep writes). offgrid: VGS/VDS are random continuous values (L and VSB stay on grid because '
                     'the L grid is coarse, so interpolating across L is not meaningful) -> also exercises interpolation.')
a = ap.parse_args()

s = loadmat(a.lut, squeeze_me=True, struct_as_record=False)[a.device]
ax = [np.asarray(s.L, float), np.asarray(s.VGS, float), np.asarray(s.VDS, float), np.asarray(s.VSB, float)]
fields = {k: np.asarray(getattr(s, k), float) for k in ('ID', 'GM', 'GDS', 'CGG')}
interp = {k: RegularGridInterpolator(ax, v) for k, v in fields.items()}
isp = a.device.startswith('p')

rng = np.random.default_rng(a.seed)
pts = []
while len(pts) < a.n:
    L = float(rng.choice(ax[0]))
    if a.mode == 'lmid':      # fact 9: L midway between two grid nodes -> linear interpolation in L
        i = int(rng.integers(0, len(ax[0]) - 1)); L = float(np.round((ax[0][i] + ax[0][i + 1]) / 2, 4))
    vsb = float(np.round(abs(rng.choice(ax[3])), 4))
    if a.mode == 'grid':
        vgs = float(np.round(rng.choice(ax[1][ax[1] >= 0.3]), 4))
        vds = float(np.round(rng.choice(ax[2][ax[2] >= 0.1]), 4))
    else:                    # offgrid and lmid
        vgs = float(np.round(rng.uniform(0.9, 2.5), 4))   # moderate-to-strong inversion: interpolation error is small there
        vds = float(np.round(rng.uniform(0.3, 3.0), 4))
    if a.mode == 'offgrid' and a.min_id > 0:
        # Linear interpolation of an exponential (weak inversion, ID < ~1 uA for W=5 um) is
        # inherently a few % off between 25 mV grid nodes; that is interpolation, not LUT error.
        # Keep only moderate/strong-inversion points here (weak inversion has its own informative run).
        if float(interp['ID']([L, vgs, vds, vsb])[0]) < a.min_id:
            continue
    pts.append((L, vgs, vds, vsb))


def deck(L, vgs, vds, vsb):
    if isp:
        src = (f"vg 0 g DC {vgs}\nvd 0 d {vds}\nvb 0 b {-vsb}\n")
    else:
        src = (f"vg g 0 DC {vgs}\nvd d 0 {vds}\nvb b 0 {-vsb}\n")
    return f"""* spot check
{src}XM1 d g 0 b {a.device} L={L}u W=5u nf=1 ad='int((nf+1)/2) * W/nf * 0.18u' as='int((nf+2)/2) * W/nf * 0.18u' pd='2*int((nf+1)/2) * (W/nf + 0.18u)'
+ ps='2*int((nf+2)/2) * (W/nf + 0.18u)' nrd='0.18u / W' nrs='0.18u / W' sa=0 sb=0 sd=0 m=1
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice {a.corner}
.temp {a.temp:g}
.save @m.xm1.m0[id] @m.xm1.m0[gm] @m.xm1.m0[gds] @m.xm1.m0[cgg] @m.xm1.m0[cgdo] @m.xm1.m0[cgso]
.control
set noaskquit
op
print @m.xm1.m0[id] @m.xm1.m0[gm] @m.xm1.m0[gds] @m.xm1.m0[cgg] @m.xm1.m0[cgdo] @m.xm1.m0[cgso]
quit
.endc
.end
"""


def run(p):
    with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR', '/tmp')) as d:
        f = os.path.join(d, 'sc.spice')
        open(f, 'w').write(deck(*p))
        out = subprocess.run(['ngspice', '-b', f], capture_output=True, text=True, env=dict(os.environ, OMP_NUM_THREADS='1')).stdout
    v = {}
    for k in ('id', 'gm', 'gds', 'cgg', 'cgdo', 'cgso'):
        m = re.search(r'@m\.xm1\.m0\[%s\]\s*=\s*([-+0-9.eE]+)' % k, out)
        assert m, f'could not parse {k} from ngspice output:\n{out[-800:]}'
        v[k] = float(m.group(1))
    return dict(ID=v['id'], GM=v['gm'], GDS=v['gds'], CGG=v['cgg'] + v['cgdo'] + v['cgso'])


worst = 0
print(f'mode={a.mode}  {a.device}  LUT={os.path.basename(a.lut)}  corner={a.corner} T={a.temp:g}C   tol={a.tol*100:.0f}%')
print(f'{"L":>6s} {"VGS":>7s} {"VDS":>7s} {"VSB":>6s} | ' + ' | '.join(f'{k:>4s} spice      lut     rel%' for k in fields))
allok = True
for p in pts:
    ref = run(p)
    row = []
    for k in fields:
        lutv = float(interp[k]([p[0], p[1], p[2], p[3]])[0])
        rel = abs(lutv - ref[k]) / abs(ref[k])
        worst = max(worst, rel)
        allok &= rel <= a.tol
        row.append(f'{k:>4s} {ref[k]:9.3e} {lutv:9.3e} {rel*100:5.2f}')
    print(f'{p[0]:6.3f} {p[1]:7.4f} {p[2]:7.4f} {p[3]:6.4f} | ' + ' | '.join(row))
print(f'WORST relative difference = {worst*100:.3f} %   -> {"PASS" if allok else "FAIL"} (tol {a.tol*100:.0f} %)')
raise SystemExit(0 if allok else 1)
