"""
gf180_fom_table.py -- GF180 3.3 V equivalent of the book's Table 1.1 (figures of merit versus gm/ID).
Every number comes from pygmid on nfet_03v3.mat / pfet_03v3.mat (typical corner, 27 C, VSB = 0).

Run: docker exec apic_headless bash <...>/tools/cx python3 docs/book_extracts/gf180_fom_table.py
"""
import numpy as np
from pygmid import Lookup

B = '/foss/designs/Analog/starter_files_open_source_tools/gf180mcuD/simulation/'
dev = {'nfet': Lookup(B + 'nfet_03v3.mat'), 'pfet': Lookup(B + 'pfet_03v3.mat')}
VDS = 1.0
print('GF180 3.3 V devices, typical corner, VDS = %.1f V, VSB = 0.  (jd = ID/W in uA/um; fT in GHz; caps in fF/um)' % VDS)
for name, d in dev.items():
    print('\n[%s]' % name)
    print(' L(um) gm/ID  VDsat~2/(gm/ID)   jd(uA/um)  gm/W(uS/um)  gm/gds   fT(GHz)  Cgg/W   Cdd/W  VGS(V)')
    for L in (0.28, 0.5, 1.0):
        for g in (5, 10, 15, 20):
            jd = float(d.lookup('ID_W', GM_ID=g, L=L, VDS=VDS))
            gmw = jd * g
            av = float(d.lookup('GM_GDS', GM_ID=g, L=L, VDS=VDS))
            ft = float(d.lookup('GM_CGG', GM_ID=g, L=L, VDS=VDS)) / 2 / np.pi / 1e9
            # CGG_W / CDD_W : per-um capacitance (the LUT device is W = 5 um)
            cgg_w = float(d.lookup('CGG_W', GM_ID=g, L=L, VDS=VDS)) * 1e15
            cdd_w = float(d.lookup('CDD_W', GM_ID=g, L=L, VDS=VDS)) * 1e15
            vgs = float(d.lookupVGS(GM_ID=g, L=L, VDS=VDS))
            print('  %.2f   %2d      %.3f          %7.3f   %8.2f   %7.1f  %7.2f  %6.3f  %6.3f   %.3f' % (L, g, 2 / g, jd * 1e6, gmw * 1e6, av, ft, cgg_w, cdd_w, vgs))
