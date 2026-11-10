"""
vdsat_check.py -- how good is the book's VDsat = 2/(gm/ID) rule (eq. 2.34) on the GF180 3.3 V tables?
For a device biased at fixed VGS (chosen so that gm/ID = g at VDS = 1.0 V), compare the drain current at
VDS = 2/g with the current at VDS = 1.0 V, and the small-signal gds/gm there.
Also derives the subthreshold slope factor n from the weak-inversion plateau gm/ID = 1/(n UT)  (book eq. 1.9 / 2.x).

Run: docker exec apic_headless bash <...>/tools/cx python3 docs/book_extracts/vdsat_check.py
"""
import numpy as np
from pygmid import Lookup

B = '/foss/designs/Analog/starter_files_open_source_tools/gf180mcuD/simulation/'
UT = 1.380649e-23 * 300 / 1.602176634e-19
for name in ('nfet_03v3', 'pfet_03v3'):
    d = Lookup(B + name + '.mat')
    print('\n[%s]  UT(300 K) = %.2f mV' % (name, UT * 1e3))
    for L in (0.28, 0.5, 1.0):
        pk = float(np.max(d.lookup('GM_ID', VGS=d['VGS'], L=L, VDS=1.0)))
        print('  L=%.2f: weak-inversion plateau gm/ID = %.2f 1/V  ->  n = 1/(UT*gmID_max) = %.3f ; VDsat(WI) = 2nUT = %.0f mV' % (L, pk, 1 / (UT * pk), 2 / pk * 1e3))
    L = 0.5
    print('  L = 0.5 um: current at VDS = 2/(gm/ID) relative to current at VDS = 1.0 V (same VGS), and gm/gds there')
    for g in (5, 10, 15, 20):
        vgs = float(d.lookupVGS(GM_ID=g, L=L, VDS=1.0))
        vds = 2.0 / g
        i_sat = float(d.lookup('ID', VGS=vgs, VDS=vds, L=L))
        i_1 = float(d.lookup('ID', VGS=vgs, VDS=1.0, L=L))
        a_sat = float(d.lookup('GM_GDS', VGS=vgs, VDS=vds, L=L))
        a_1 = float(d.lookup('GM_GDS', VGS=vgs, VDS=1.0, L=L))
        vt = float(d.lookup('VT', VGS=vgs, VDS=1.0, L=L))
        print('    gm/ID=%2d  VGS=%.3f  VGS-VT=%+.3f  VDsat~%.3f V :  ID(VDsat)/ID(1V)=%.2f   gm/gds(VDsat)=%.0f vs %.0f at 1 V' % (g, vgs, vgs - vt, vds, i_sat / i_1, a_sat, a_1))
