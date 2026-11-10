#!/usr/bin/env python3
"""gen_lvs_ref.py -- LVS reference netlists of lvds_rx_x3 with gf180mcuD device names and numeric W/L/nf/R values.

    python3 netlist/gen_lvs_ref.py [--flags nmos_pair=0,dump_devices=1]

Writes netlist/lvds_rx_lvs_ref.spice (hierarchical, subckts lvds_bias lvds_esd2 lvds_pre lvds_hyst lvds_out lvds_lane lvds_rx_x3)
and netlist/lvds_rx_lvs_ref_flat.spice (the same circuit flattened into one lvds_rx_x3).  Numbers come from layout/device_table.json
(written by sizing/lvds_rx_sizing.py), connectivity from netlist/lvds_circuit.py.  Dummy fingers and taps are added by the layout tasks.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lvds_circuit as K  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--flags', default='', help='comma list key=0/1 overriding the flags of the device table (nmos_pair, dump_devices)')
    ap.add_argument('--out-dir', default=HERE)
    a = ap.parse_args()
    tab, _, _ = K.load_table()
    flags = dict(tab['flags'])
    for kv in filter(None, a.flags.split(',')):
        k, v = kv.split('=')
        flags[k] = int(v)
    for flat, name in ((False, 'lvds_rx_lvs_ref.spice'), (True, 'lvds_rx_lvs_ref_flat.spice')):
        p = os.path.join(a.out_dir, name)
        with open(p, 'w') as f:
            f.write(K.emit_lvs(flags=flags, flat=flat))
        print('wrote', os.path.relpath(p, K.ROOT))
    return 0


if __name__ == '__main__':
    sys.exit(main())
