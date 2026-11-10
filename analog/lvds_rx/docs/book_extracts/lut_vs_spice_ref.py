"""
lut_vs_spice_ref.py -- prints what the LUT says at the two bias points of lut_vs_spice.spice,
so the numbers can be compared with the ngspice .op output by eye (and by the notes).
Also checks the book's 'CDD_CSS vs CDD_W' oddity (Ex. 6.4 code, Fig6_17.py) on the GF180 tables.

Run:  docker exec apic_headless bash <...>/tools/cx python3 docs/book_extracts/lut_vs_spice_ref.py
"""
import numpy as np
from pygmid import Lookup

B = '/foss/designs/Analog/starter_files_open_source_tools/gf180mcuD/simulation/'
n = Lookup(B + 'nfet_03v3.mat')
p = Lookup(B + 'pfet_03v3.mat')

print('LUT values at the lut_vs_spice.spice bias points (all for the W = 5 um, nf = 1 table device):')
for name, d, vgs in (('NMOS', n, 0.8015774), ('PMOS', p, 0.9006965)):
    out = {}
    for q in ('ID', 'GM', 'GDS', 'CGG', 'VT'):
        out[q] = float(d.lookup(q, VGS=vgs, L=0.5, VDS=1.0, VSB=0))
    print('  %s: ID=%.4e A  gm=%.4e S  gds=%.4e S  Cgg=%.4e F  Vth=%.4f V' % (name, out['ID'], out['GM'], out['GDS'], out['CGG'], out['VT']))

print('\nBook oddity: Ex. 6.4 computes cdd_w3/cdd_w2 with CDD_CSS where CDD_W was probably meant.')
print('Fold-pole denominator (1 + 2*cdd_css3 * 2*(cdd_w2/cdd_w3)) evaluated with GF180 NMOS tables, gm/ID=15, L=0.4,')
print('M3 at VDS=0.4 V, VSB=0.2 V; M2 at VDS=0.2 V, VSB=0 (same bias points as the book code):')
g, L = 15, 0.4
cdd_css3 = float(n.lookup('CDD_CSS', GM_ID=g, VDS=0.4, VSB=0.2, L=L))
w3_book = float(n.lookup('CDD_CSS', GM_ID=g, VDS=0.4, VSB=0.2, L=L))
w2_book = float(n.lookup('CDD_CSS', GM_ID=g, VDS=0.2, VSB=0.0, L=L))
w3_fix = float(n.lookup('CDD_W', GM_ID=g, VDS=0.4, VSB=0.2, L=L))
w2_fix = float(n.lookup('CDD_W', GM_ID=g, VDS=0.2, VSB=0.0, L=L))
gm_css3 = float(n.lookup('GM_CSS', GM_ID=g, VDS=0.4, VSB=0.2, L=L))
gmb_gm3 = float(n.lookup('GMB_GM', GM_ID=g, VDS=0.4, VSB=0.2, L=L))
for lab, r in (('as printed (CDD_CSS twice)', w2_book / w3_book), ('with CDD_W', w2_fix / w3_fix)):
    fp2 = gm_css3 * (1 + gmb_gm3) / (1 + 2 * cdd_css3 * 2 * r) / 2 / np.pi
    print('  %-28s cdd_w2/cdd_w3 = %.4f  -> fp2 = %.3f GHz' % (lab, r, fp2 / 1e9))
print('  (Cdd/Css is a ratio of two caps, Cdd/W a cap per width; both are W-independent, so the two')
print('   readings give different numbers whenever Css/W differs between the two VDS points.)')
