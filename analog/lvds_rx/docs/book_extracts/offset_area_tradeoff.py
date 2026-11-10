"""
offset_area_tradeoff.py -- book Sec. 4.3 offset formula (4.56/4.57) turned into numbers on the GF180 LUTs.

For a differential pair with current-mirror/active load, per branch current ID:
    sigma_Vos^2 = sigma_dVT1^2 + r^2 * sigma_dVT2^2 ,   r = (gm/ID)2 / (gm/ID)1          [eq. 4.57]
    sigma_dVT   = AVT / sqrt(W L)                                                          [eq. 4.45]
AVT for GF180 is NOT in the book; it is kept symbolic here as 'k' = sigma in units of AVT_n (um^-1).
Prints, for the input pair (nfet) and the load (pfet): W, gate area, 1/sqrt(WL) (= sigma_VT per unit AVT),
Cgg, fT and fan-out for a representative branch current, to show the area-vs-speed trade.

Run: docker exec apic_headless bash <...>/tools/cx python3 docs/book_extracts/offset_area_tradeoff.py
"""
import numpy as np
from pygmid import Lookup

B = '/foss/designs/Analog/starter_files_open_source_tools/gf180mcuD/simulation/'
n = Lookup(B + 'nfet_03v3.mat')
p = Lookup(B + 'pfet_03v3.mat')
ID = 50e-6      # branch current, A
VDS = 1.0
print('Branch current ID = %.0f uA, VDS = %.1f V.   k = sigma_dVT / AVT = 1/sqrt(W*L) in 1/um (multiply by AVT in mV*um)' % (ID * 1e6, VDS))
print('\nInput pair (nfet): area, 1/sqrt(WL), Cgg, fT')
print('  L(um) gm/ID    W(um)  WL(um^2)  k=1/sqrt(WL)   Cgg(fF)  fT(GHz)  gm(mS)')
for L in (0.5, 1.0, 2.0):
    for g in (8, 12, 16):
        jd = float(n.lookup('ID_W', GM_ID=g, L=L, VDS=VDS))
        W = ID / jd
        cgg = W * float(n.lookup('CGG_W', GM_ID=g, L=L, VDS=VDS))
        ft = float(n.lookup('GM_CGG', GM_ID=g, L=L, VDS=VDS)) / 2 / np.pi
        print('  %.1f    %2d   %8.1f  %8.1f   %.3f        %7.1f  %7.2f  %.3f' % (L, g, W, W * L, 1 / np.sqrt(W * L), cgg * 1e15, ft / 1e9, g * ID * 1e3))
print('\nLoad / mirror (pfet) at the same current: area and the weight r = (gm/ID)2/(gm/ID)1 of its mismatch in the offset')
print('  L(um) gm/ID(load)   W(um)  WL(um^2)  k2=1/sqrt(WL)   r for (gm/ID)1=12   r*k2')
for L in (0.5, 1.0, 2.0):
    for g in (5, 8, 10):
        jd = float(p.lookup('ID_W', GM_ID=g, L=L, VDS=VDS))
        W = ID / jd
        k2 = 1 / np.sqrt(W * L)
        r = g / 12.0
        print('  %.1f    %2d        %8.1f  %8.1f   %.3f            %.2f           %.3f' % (L, g, W, W * L, k2, r, r * k2))
print('\nExample: nfet pair L=1.0 gm/ID=12, pfet load L=1.0 gm/ID=8:  sigma_Vos/AVT = sqrt(k1^2 + (r k2)^2)  (if AVTn = AVTp)')
jd1 = float(n.lookup('ID_W', GM_ID=12, L=1.0, VDS=VDS)); W1 = ID / jd1
jd2 = float(p.lookup('ID_W', GM_ID=8, L=1.0, VDS=VDS)); W2 = ID / jd2
k1 = 1 / np.sqrt(W1 * 1.0); k2 = 1 / np.sqrt(W2 * 1.0); r = 8 / 12
print('  k1=%.3f  k2=%.3f  r=%.2f  ->  sigma_Vos = %.3f * AVT  (pair alone: %.3f * AVT)' % (k1, k2, r, np.hypot(k1, r * k2), k1))
