#!/usr/bin/env python3
"""gen_core.py -- write netlist/lvds_rx_core.spice (simulation netlist) from netlist/lvds_circuit.py.

    python3 netlist/gen_core.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lvds_circuit as K  # noqa: E402


def main():
    path = os.path.join(HERE, 'lvds_rx_core.spice')
    with open(path, 'w') as f:
        f.write(K.emit_sim() + '\n')
    print('wrote', os.path.relpath(path, K.ROOT))
    return 0


if __name__ == '__main__':
    sys.exit(main())
