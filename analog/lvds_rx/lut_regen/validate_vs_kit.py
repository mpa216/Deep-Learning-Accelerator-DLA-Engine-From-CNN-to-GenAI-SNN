#!/usr/bin/env python3
"""validate_vs_kit.py - compare a regenerated LUT with the kit LUT on the shared grid.

usage: python3 validate_vs_kit.py <regenerated.mat> <kit.mat> [device]
Compares ID, GM, GDS, CGG, CDD (and VT, CGD, STH for information) at every (L, VGS, VDS) that both
tables have and for VSB values present in BOTH (0, 0.2, 0.4).  Relative difference
|new - kit| / |kit|, reported (a) over the 'useful' region where the kit drain current is above 1 nA
(deep-cutoff points are dominated by 4-digit text rounding of tiny numbers and are not what a gm/ID
design ever uses), (b) over the 'moderate/strong inversion' region ID_kit > 1 uA, (c) over all points
where |kit| > 1e-6 of that quantity's maximum.  Also prints where the single worst point is.
"""
import sys
import numpy as np
from scipy.io import loadmat


def load(path, dev):
    d = loadmat(path, squeeze_me=True, struct_as_record=False)
    s = d[dev]
    return {k: np.asarray(getattr(s, k)) for k in s._fieldnames if k not in ('INFO', 'CORNER')} | \
           {'CORNER': str(getattr(s, 'CORNER')), 'TEMP': float(getattr(s, 'TEMP'))}


def main(new_p, kit_p, dev):
    a, b = load(new_p, dev), load(kit_p, dev)
    print(f'new : {new_p}\n      corner={a["CORNER"]} TEMP={a["TEMP"]} K  L={len(a["L"])} VGS={len(a["VGS"])} VDS={len(a["VDS"])} VSB={list(np.round(a["VSB"], 3))}')
    print(f'kit : {kit_p}\n      corner={b["CORNER"]} TEMP={b["TEMP"]} K  L={len(b["L"])} VGS={len(b["VGS"])} VDS={len(b["VDS"])} VSB={list(np.round(b["VSB"], 3))}')
    for k in ('L', 'VGS', 'VDS'):
        assert a[k].shape == b[k].shape and np.allclose(a[k], b[k], atol=1e-6), f'{k} grids differ'
    ia = [int(np.argmin(abs(a['VSB'] - v))) for v in b['VSB']]
    assert np.allclose(a['VSB'][ia], b['VSB'], atol=1e-6), 'VSB points of kit not all in new table'
    print('shared grid: L', list(a['L']), '\n  VGS/VDS 0..%.3f (%d pts), VSB kit points found in new table at indices %s' % (a['VGS'].max(), len(a['VGS']), ia))
    idk = b['ID']
    masks = {'ID_kit>1nA': idk > 1e-9, 'ID_kit>1uA': idk > 1e-6}
    print()
    hdr = f'{"field":6s} | ' + ' | '.join(f'{m:>12s} max / rms' for m in list(masks) + ['|kit|>1e-6*max'])
    print(hdr)
    out = {}
    for f in ('ID', 'GM', 'GDS', 'CGG', 'CDD', 'VT', 'CGD', 'STH'):
        new = a[f][:, :, :, ia]
        kit = b[f]
        with np.errstate(all='ignore'):
            rel = np.abs(new - kit) / np.abs(kit)
        cells = []
        m3 = np.abs(kit) > 1e-6 * np.nanmax(np.abs(kit))
        for mname, m in list(masks.items()) + [('all', m3)]:
            r = rel[m & np.isfinite(rel)]
            cells.append((float(np.max(r)), float(np.sqrt(np.mean(r ** 2)))))
        out[f] = cells
        print(f'{f:6s} | ' + ' | '.join(f'{c[0]:9.3e} / {c[1]:9.3e}' for c in cells))
    # worst point for ID in the useful region
    with np.errstate(all='ignore'):
        rel = np.abs(a['ID'][:, :, :, ia] - idk) / np.abs(idk)
    rel[~(idk > 1e-9)] = 0
    w = np.unravel_index(np.argmax(rel), rel.shape)
    print(f'\nworst ID point (ID_kit>1nA): L={a["L"][w[0]]} VGS={a["VGS"][w[1]]} VDS={a["VDS"][w[2]]} VSB={b["VSB"][w[3]]:.1f}: '
          f'new={a["ID"][w[0], w[1], w[2], ia[w[3]]]:.5e} kit={idk[w]:.5e} rel={rel[w]:.3e}')
    # per-VSB split of the ID error (does the 0.4 V plane differ more than 0?)
    for j, v in enumerate(b['VSB']):
        m = idk[..., j] > 1e-6
        r = np.abs(a['ID'][..., ia[j]] - idk[..., j])[m] / idk[..., j][m]
        print(f'  VSB={v:.1f}: ID rel diff (ID>1uA)  max {r.max():.3e}  rms {np.sqrt(np.mean(r**2)):.3e}')
    # gm/ID and fT based (what the design actually reads) at gm/ID in strong/moderate region
    return out


if __name__ == '__main__':
    dev = sys.argv[3] if len(sys.argv) > 3 else ('pfet_03v3' if 'pfet' in sys.argv[2] else 'nfet_03v3')
    main(sys.argv[1], sys.argv[2], dev)
