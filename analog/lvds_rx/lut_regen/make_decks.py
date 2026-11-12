#!/usr/bin/env python3
"""make_decks.py - derive regeneration decks from the kit's techsweep_{n,p}fet_03v3.spice.

The kit decks are the ngspice netlists of the kit's xschem schematics.  We never edit the kit
(read-only); we copy the text, and change only:
  1. model/include paths  gf180mcuC -> gf180mcuD   (this machine only has D)
  2. corner name on the .lib line (typical / ss / ff)   and a .temp line
  3. the body-bias sweep  0..-0.4 V (3 points)  ->  0..-2.0 V (11 points)
  4. optionally the list of L values (smaller grid for corner LUTs)
  5. output file names (so nothing overwrites anything)
The design.ngspice include is KEPT: on this install it already sets sw_stat_global=0 and
sw_stat_mismatch=0 (verified), so no statistical variation enters the sweep.

usage: python3 make_decks.py [--kit DIR] [--out DIR]
       -> writes decks/techsweep_<dev>_<corner>_<T>C_<tag>.spice
"""
import argparse, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
# Snapshot of the kit decks as they were on 2026-11-10 (gf180mcuC paths).  The live kit folder is
# read-only for us and the nfet deck there was edited by someone else during this work, so we do not
# depend on it.  (Pass --kit <live simulation dir> to derive from the live files instead; the C->D path
# replacement is then a harmless no-op.)
KIT = os.path.join(HERE, 'decks', 'kit_original')

# key -> (corner, tempC, L list text, vsb stop, tag)
# stop values carry a +0.001 overshoot (same trick the kit uses for 3.301) so that the last
# grid point is never lost to floating-point accumulation in ngspice 'compose'.
FULL_L = '0.28u 0.29u\n+ 0.3u 0.4u 0.5u 0.6u 0.7u 0.8u 0.9u 1u 2u 3u'
SMALL_L = '0.28u 0.3u 0.4u 0.5u 0.7u 1u 2u'
JOBS = {
    'typical': ('typical', 27, FULL_L, '-2.001', 'vsb2'),
    'ss125':   ('ss', 125, SMALL_L, '-2.001', 'vsb2'),     # T2 part 2: VSB 0..2.0 (was 0.8: TB1 found ms and the NMOS pair at VSB 1.1-1.5 V)
    'ff-40':   ('ff', -40, SMALL_L, '-2.001', 'vsb2'),
    'fs27':    ('fs', 27, SMALL_L, '-2.001', 'vsb2'),      # T2 part 2: skew corners for the TB1 LUT-vs-SPICE check at fs, sf
    'sf27':    ('sf', 27, SMALL_L, '-2.001', 'vsb2'),
    # T5: TB1's LUT-vs-SPICE gm/ID check was 20-28 % off at every temperature that has no table (the typical-27C table is a
    # temperature proxy); typical-process tables at the two temperature extremes serve the other processes there.
    'tt125':   ('typical', 125, SMALL_L, '-2.001', 'vsb2'),
    'tt-40':   ('typical', -40, SMALL_L, '-2.001', 'vsb2'),
}
# T5 (second step): the VGS comparison needs the PROCESS too (VT moves 100-150 mV between ss and ff): every process x temperature of the 45 corners
for _proc in ('ss', 'ff', 'fs', 'sf'):
    for _t in (-40, 27, 125):
        JOBS.setdefault('%s%d' % (_proc, _t) if _t != 27 else '%s27' % _proc, (_proc, _t, SMALL_L, '-2.001', 'vsb2'))



def make(dev, key, kit, outdir):
    corner, tc, ltxt, vstop, tag = JOBS[key]
    s = open(os.path.join(kit, f'techsweep_{dev}.spice')).read()
    s = s.replace('/foss/pdks/gf180mcuC/', '/foss/pdks/gf180mcuD/')
    assert 'gf180mcuC' not in s
    s, k = re.subn(r'(\.lib /foss/pdks/gf180mcuD/libs\.tech/ngspice/sm141064\.ngspice) typical',
                   r'\1 %s\n.temp %d' % (corner, tc), s)
    assert k == 1
    s, k = re.subn(r'compose vb_vec start= 0 stop=-0\.4 step=-0\.2',
                   'compose vb_vec start= 0 stop=%s step=-0.2' % vstop, s)
    assert k == 1
    s, k = re.subn(r'compose l_vec  values 0\.28u 0\.29u\n\+ 0\.3u 0\.4u 0\.5u 0\.6u 0\.7u 0\.8u 0\.9u 1u 2u 3u',
                   'compose l_vec  values ' + ltxt, s)
    assert k == 1
    # single-thread ngspice: its OpenMP threads (one per core) only spin-wait on this 1-transistor circuit
    s, k = re.subn(r'\.control\n', '.control\nset num_threads=1\n', s)
    assert k == 1
    base = f'techsweep_{dev}_{corner}_{tc}C_{tag}'
    s, k = re.subn(r'wrdata techsweep_%s\.txt' % dev, 'wrdata %s.txt' % base, s)
    assert k == 1
    s, k = re.subn(r'write techsweep_%s\.raw' % dev, 'write %s.raw' % base, s)
    assert k == 1
    p = os.path.join(outdir, base + '.spice')
    with open(p, 'w') as f:
        f.write('* derived from kit %s by make_decks.py (%s, %dC, %s)\n' % (dev, corner, tc, tag) + s)
    return p


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--kit', default=KIT)
    ap.add_argument('--out', default=os.path.join(HERE, 'decks'))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    for dev in ['nfet_03v3', 'pfet_03v3']:
        for key in JOBS:
            print(make(dev, key, a.kit, a.out))
