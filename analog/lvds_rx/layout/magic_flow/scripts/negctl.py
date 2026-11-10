#!/usr/bin/env python3
"""negctl.py GDS CELL KIND OUT.gds    make a deliberately broken copy of a layout (negative control for DRC / LVS).
KIND = sliver (0.10 um wide Metal1 stripe away from everything: DRC must flag it)
       short  (Metal3 bar joining the INP and OUT pin wires: LVS must fail)
       open   (cuts the Metal3 INN wire with a 0.6 um gap: LVS must fail)
Pin wires are located from the label text in the GDS (pins are labels on Metal3)."""
import sys
import klayout.db as db

gds, cell, kind, out = sys.argv[1:5]
ly = db.Layout()
ly.read(gds)
top = ly.cell(cell)
dbu = ly.dbu
M1, M3 = ly.layer(34, 0), ly.layer(42, 0)
labels = {}
for li in ly.layer_indexes():
    for s in top.shapes(li).each():
        if s.is_text():
            labels[s.text_string] = s.text_dpos
print("labels:", {k: (round(v.x, 2), round(v.y, 2)) for k, v in labels.items()})
bb = top.dbbox()
if kind == "sliver":
    top.shapes(M1).insert(db.DBox(bb.right + 3, bb.bottom, bb.right + 3.1, bb.bottom + 3))
elif kind == "short":
    a, b = labels["INP"], labels["OUT"]
    top.shapes(M3).insert(db.DBox(min(a.x, b.x) - 0.2, a.y - 0.2, max(a.x, b.x) + 0.2, a.y + 0.2))
elif kind == "open":
    p = labels["INN"]
    r = db.Region(top.shapes(M3))
    cut = db.Region(db.Box(int((p.x - 1) / dbu), int((p.y + 5) / dbu), int((p.x + 1) / dbu), int((p.y + 5.6) / dbu)))
    r = r - cut
    top.shapes(M3).clear()
    top.shapes(M3).insert(r)
else:
    raise SystemExit("bad kind")
ly.write(out)
