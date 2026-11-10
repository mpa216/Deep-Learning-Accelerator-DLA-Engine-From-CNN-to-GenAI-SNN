#!/usr/bin/env python3
"""techsweep_txt2mat.py - CLI port of techsweep_txt_to_mat.ipynb (same column handling),
plus corner/temp metadata and a NON-overwriting output name.
usage: python techsweep_txt2mat.py techsweep_nfet_03v3_ss_125C.txt nfet_03v3 --corner SS --temp-c 125 --out nfet_03v3_ss_125C.mat
"""
import argparse
import numpy as np
import pandas as pd
from scipy.io import savemat

ap = argparse.ArgumentParser()
ap.add_argument('txt')
ap.add_argument('device')
ap.add_argument('--corner', default='NOM')
ap.add_argument('--temp-c', type=float, default=27.0)
ap.add_argument('--width', type=float, default=5.0)
ap.add_argument('--nfing', type=int, default=1)
ap.add_argument('--out', required=True)
a = ap.parse_args()

df_raw = pd.read_csv(a.txt, sep=r'\s+')
fet_name = df_raw.columns.to_list()[1].split('[')[0]               # e.g. '@m.xm1.m0'
df = df_raw.drop([c for c in df_raw.columns if c.startswith('frequency')], axis=1).apply(pd.to_numeric)
c = df.columns
c = c.str.replace(fet_name, '', regex=False).str.replace(fet_name[1:], '', regex=False)
c = c.str.replace('[dc]', '', regex=False).str.replace('onoise..', 'n', regex=False)
df.columns = c.str.removeprefix('@').str.removeprefix('[').str.removesuffix(']')

l = np.round(np.unique(df['l']) * 1e6, 2)
vgs = np.unique(df['vg'])
vds = np.unique(df['vd'])
vsb = np.unique(-df['vb'])
dims = [len(l), len(vgs), len(vds), len(vsb)]                      # ngspice loop order: L, VGS, VDS, VSB
assert np.prod(dims) == len(df), f'rows {len(df)} != {dims} -> incomplete/duplicated sweep'


def R(k):
    return np.reshape(df[k].values, dims)


# reshape-order self-check: the swept columns must reproduce their own grids
assert np.allclose(R('vg')[0, :, 0, 0], vgs) and np.allclose(R('vd')[0, 0, :, 0], vds)
assert np.allclose(-R('vb')[0, 0, 0, :], vsb) and np.allclose(np.round(R('l')[:, 0, 0, 0] * 1e6, 2), l)
dic = {"INFO": "GlobalFoundries, 180nm MCU CMOS , BSIM4", "CORNER": a.corner, "TEMP": a.temp_c + 273.15,
       "VGS": vgs, "VDS": vds, "VSB": vsb, "L": l, "W": a.width, "NFING": a.nfing,
       "ID": R('id'), "VT": R('vth'), "GM": R('gm'), "GMB": R('gmbs'), "GDS": R('gds'),
       "CGG": R('cgg') + R('cgdo') + R('cgso'), "CGB": -R('cgb'),
       "CGD": -R('cgd') + R('cgdo'), "CGS": -R('cgs') + R('cgso'),
       "CDD": R('cdd') + R('capbd') + R('cgdo'), "CSS": R('css') + R('capbs') + R('cgso'),
       "STH": R('nid') ** 2, "SFL": R('n1overf') ** 2}
savemat(a.out, {a.device: dic})
print(f'wrote {a.out}: dims {dims}, L={l}, VSB={vsb}, corner={a.corner}, T={a.temp_c} C')
