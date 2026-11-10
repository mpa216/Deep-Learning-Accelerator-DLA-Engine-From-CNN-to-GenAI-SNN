#!/usr/bin/env python3
"""dbu.py FILE.gds ...   print the GDS database unit and the top cells (must be 0.001 um for the foundry DRC)."""
import sys

import klayout.db as db

for f in sys.argv[1:]:
    ly = db.Layout()
    ly.read(f)
    status = "OK" if abs(ly.dbu - 0.001) < 1e-12 else "WRONG (expected 0.001)"
    print(f"GDS_DBU {ly.dbu} {status} top={[c.name for c in ly.top_cells()]} file={f}")
