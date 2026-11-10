#!/usr/bin/env python3
"""bbox.py GDS CELL   print the bounding box of a cell in microns (width x height)."""
import sys

import klayout.db as db

ly = db.Layout()
ly.read(sys.argv[1])
c = ly.cell(sys.argv[2])
b = c.dbbox()
print(f"BBOX {sys.argv[2]}: {b.width():.2f} x {b.height():.2f} um  (x {b.left:.2f}..{b.right:.2f}, y {b.bottom:.2f}..{b.top:.2f})")
