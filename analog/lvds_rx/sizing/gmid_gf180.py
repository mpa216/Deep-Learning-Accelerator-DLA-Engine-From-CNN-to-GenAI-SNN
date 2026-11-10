"""gmid_gf180.py - thin, guarded wrapper around pygmid for the GF180MCU kit LUTs.
Tested (research session 2026-10-05): Python 3.11, pygmid 1.2.12, numpy 2.4, scipy 1.16.
Re-tested on this machine 2026-11-10 (container apic_headless, Python 3.12.3, pygmid 1.2.12).
LUT convention (all kit tables): W = 5 um, NFING = 1, TEMP = 300 K, CORNER = 'NOM' (typical),
grids: L (um) | VGS, VDS 0..3.3 (5.0) V step 25 mV | VSB = {0, 0.2, 0.4} V in the KIT tables
(the regenerated tables in analog/lvds_rx/luts go to VSB = 2.0 V, see lut_regen/README.md).
PMOS tables store MAGNITUDES: VGS=VSG, VDS=VSD, VSB=VBS, ID>0, VT>0.  ID_W is in A/um.

Where the .mat files are looked for (first match wins, per table name):
  1. $GF180_LUT_DIR                      (explicit override; kit folder or any regenerated folder)
  2. analog/lvds_rx/luts                 (our regenerated tables: wider VSB, corner tables)
  3. the kit's simulation folder         (/foss/designs/Analog/starter_files_open_source_tools/gf180mcuD/simulation)
"""
import os
import warnings
import numpy as np
from pygmid import Lookup

_HERE = os.path.dirname(os.path.abspath(__file__))
KIT_DIR = '/foss/designs/Analog/starter_files_open_source_tools/gf180mcuD/simulation'
LUT_DIRS = [d for d in (os.environ.get('GF180_LUT_DIR'),
                        os.path.normpath(os.path.join(_HERE, '..', 'luts')),
                        KIT_DIR) if d]
LUT_DIR = LUT_DIRS[0]            # kept for backward compatibility (the first candidate)
_cache = {}


def lut_path(name):
    for d in LUT_DIRS:
        p = os.path.join(d, name + '.mat')
        if os.path.isfile(p):
            return p
    raise FileNotFoundError(f'{name}.mat not found in any of {LUT_DIRS}')


def lut(name):                      # 'nfet_03v3' | 'pfet_03v3' | 'nfet_05v0' | 'pfet_05v0' | e.g. 'nfet_03v3_ss_125C'
    if name not in _cache:
        _cache[name] = Lookup(lut_path(name))
    return _cache[name]


def _guard(t, L, VDS, VSB):
    Lg, Vd, Vb = t['L'], t['VDS'], t['VSB']
    if not (Lg.min() <= L <= Lg.max()):
        raise ValueError(f'L={L} outside LUT {Lg.min()}..{Lg.max()} um')
    if not (0.05 <= VDS <= Vd.max()):
        raise ValueError(f'VDS={VDS} outside 0.05..{Vd.max()} V')
    if not (0.0 <= VSB <= Vb.max()):
        raise ValueError(f'VSB={VSB} outside LUT 0..{Vb.max()} V (pygmid would silently extrapolate)')
    if not np.isclose(Lg, L).any():
        warnings.warn(f'L={L} not on grid {list(Lg)}: linear interpolation in L')


def gmid_max(t, L, VDS, VSB=0.0):
    return float(np.nanmax(t.lookup('GM_ID', L=L, VGS=t['VGS'], VDS=VDS, VSB=VSB)))


def at_gmid(name, ratio, gmid, L, VDS, VSB=0.0):
    """Any ratio ('GM_CGG','GM_GDS','ID_W','CGG_W','CDD_W','CGD_W','STH_GM',...) at a gm/ID (strong-inversion branch)."""
    t = lut(name)
    _guard(t, L, VDS, VSB)
    gmax = gmid_max(t, L, VDS, VSB)
    if gmid >= gmax:
        raise ValueError(f'gm/ID={gmid} >= max {gmax:.1f} at L={L},VDS={VDS},VSB={VSB}')
    return float(t.lookup(ratio, GM_ID=gmid, L=L, VDS=VDS, VSB=VSB))   # GM_ID MUST be the first kwarg


def vgs_at_gmid(name, gmid, L, VDS, VSB=0.0):
    t = lut(name)
    _guard(t, L, VDS, VSB)
    v = float(t.lookupVGS(GM_ID=gmid, L=L, VDS=VDS, VSB=VSB))
    chk = float(t.lookup('GM_ID', VGS=v, L=L, VDS=VDS, VSB=VSB))       # forward check
    if abs(chk - gmid) > 0.02 * gmid:
        raise RuntimeError(f'lookupVGS inconsistent: {chk:.2f} vs {gmid}')
    return v


def size(name, gm, gmid, L, VDS, VSB=0.0, wf_max=5.0):
    """Size one device for transconductance gm [S] at gm/ID [S/A], length L [um]."""
    ID = gm / gmid
    jd = at_gmid(name, 'ID_W', gmid, L, VDS, VSB)           # A/um
    W = ID / jd                                             # um (total width)
    nf = max(1, int(np.ceil(W / wf_max)))                   # keep finger width near the 5 um LUT width
    r = dict(dev=name, ID=ID, gm=gm, gmid=gmid, L=L, W=W, nf=nf, Wf=W / nf,
             VGS=vgs_at_gmid(name, gmid, L, VDS, VSB),
             fT=at_gmid(name, 'GM_CGG', gmid, L, VDS, VSB) / (2 * np.pi),
             gm_gds=at_gmid(name, 'GM_GDS', gmid, L, VDS, VSB),
             Cgg=at_gmid(name, 'CGG_W', gmid, L, VDS, VSB) * W,
             Cgd=at_gmid(name, 'CGD_W', gmid, L, VDS, VSB) * W,
             Cdd=at_gmid(name, 'CDD_W', gmid, L, VDS, VSB) * W,
             VDsat=2.0 / gmid)                              # book eq. (2.34), PDF p.82
    r['gds'] = gm / r['gm_gds']
    return r


def spice_line(inst, d, g, s, b, r):
    """Emit a gf180 instance line in the exact xschem/ngspice convention used by the kit.
    For the LUT prediction to hold (ID/gm/Cgg within ~0.1 %), put '.option wnflag=1' in the netlist so the BSIM4
    width bin follows the per-finger width (~5 um, as in the LUT).  Without it the bin follows the TOTAL W:
    ID/gm are still ~1 % off, but Cgg can be ~10 % off at L=0.28 um once W > 10 um (verified 2026-11-11)."""
    m = '_'.join(r['dev'].split('_')[:2])                   # 'nfet_03v3_ss_125C' -> 'nfet_03v3'
    L = r['L']
    # VERIFIER FIX 2026-11-11: ngspice picks the BSIM4 width bin from the instance's TOTAL W (bins end at
    # 100 um unless '.option wnflag=1' is set), so W > 100 um (e.g. the 1 mS PMOS of sec. 6.3, W=107.9 um,
    # nf=22) gives "could not find a valid modelname".  Split into mm identical instances (multiplier m=).
    mm = max(1, int(np.ceil(r['W'] / 99.0)))
    W = round(r['W'] / mm, 2)
    nf = max(1, int(np.ceil(r['nf'] / mm)))
    return (f"X{inst} {d} {g} {s} {b} {m} L={L}u W={W}u nf={nf} "
            "ad='int((nf+1)/2) * W/nf * 0.18u' as='int((nf+2)/2) * W/nf * 0.18u' "
            "pd='2*int((nf+1)/2) * (W/nf + 0.18u)' ps='2*int((nf+2)/2) * (W/nf + 0.18u)' "
            f"nrd='0.18u / W' nrs='0.18u / W' sa=0 sb=0 sd=0 m={mm}")


def write_params(path, sizes):
    """Book App. A.2.6 (PDF p.432) adapted to ngspice: emit a .param file that netlists .include; use W={w_in}."""
    with open(path, 'w') as f:
        f.write('* AUTO-GENERATED by lvds_rx_sizing.py - do not edit by hand\n')
        for k, v in sizes.items():
            f.write(f'.param {k} = {v:.6g}\n')


if __name__ == '__main__':          # self-test; expected output (kit LUTs) in handoff sec. 6.3
    for name in ['nfet_03v3', 'pfet_03v3']:
        r = size(name, gm=1e-3, gmid=12, L=0.5, VDS=1.0)
        print(f"{name}: ID={r['ID']*1e6:.1f}uA W={r['W']:.1f}um nf={r['nf']} |VGS|={r['VGS']:.3f}V "
              f"fT={r['fT']/1e9:.2f}GHz gm/gds={r['gm_gds']:.0f} Cgg={r['Cgg']*1e15:.1f}fF "
              f"Cgd={r['Cgd']*1e15:.1f}fF Cdd={r['Cdd']*1e15:.1f}fF")
        print('  ', spice_line('M1', 'd', 'g', 's', 'b', r))
    t = lut('nfet_03v3')
    vsb_max = float(t['VSB'].max())
    for bad in [dict(VSB=vsb_max + 0.4), dict(gmid=29)]:
        try:
            size('nfet_03v3', 1e-3, bad.get('gmid', 12), 0.5, 1.0, VSB=bad.get('VSB', 0.0))
        except ValueError as e:
            print('guard OK:', e)
