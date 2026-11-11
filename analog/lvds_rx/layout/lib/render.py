#!/usr/bin/env python3
"""render.py GDS CELL OUT.png [x1 y1 x2 y2] [--px 1600]

Batch picture of a layout with KLayout (no GUI): uses the PDK layer-property file for the colours.
The optional box is in microns (zoom window); default = whole cell.  Run through tools/cx:
  docker exec apic_headless bash .../tools/cx python3 layout/magic_flow/scripts/render.py work/lf_toy.gds lf_toy work/lf_toy.png
"""
import glob
import os
import sys

import klayout.db as db
import klayout.lay as lay

args = [a for a in sys.argv[1:] if not a.startswith("--")]
px = 1600
if "--px" in sys.argv:
    px = int(sys.argv[sys.argv.index("--px") + 1])
    args = [a for a in args if a != str(px)]
gds, cell, out = args[0], args[1], args[2]
box = [float(v) for v in args[3:7]] if len(args) >= 7 else None

lyp = None
for cand in glob.glob("/foss/pdks/gf180mcuD/libs.tech/klayout/tech/*.lyp"):
    lyp = cand
    break

view = lay.LayoutView()
view.load_layout(gds, True)
if lyp:
    view.load_layer_props(lyp)
view.max_hier()
view.select_cell(view.active_cellview().layout().cell_by_name(cell), 0)
cv = view.active_cellview()
if box:
    bb = db.DBox(*box)
else:
    bb = cv.layout().cell(cv.cell_index).dbbox()
    m = 0.03 * max(bb.width(), bb.height())
    bb = db.DBox(bb.left - m, bb.bottom - m, bb.right + m, bb.top + m)
view.zoom_box(bb)
w = bb.width()
h = bb.height()
if w <= 0:
    w = 1
height = max(200, int(px * h / w))
view.save_image(out, px, min(height, 4000))
print("wrote", out, "layer props:", lyp)
