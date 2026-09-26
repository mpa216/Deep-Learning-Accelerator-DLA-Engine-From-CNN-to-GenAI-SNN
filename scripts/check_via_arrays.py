#!/usr/bin/env python3
# GF180 rule Vn.2b -- "via space in 4x4 or larger via arrays >= 0.36 um" -- is NOT coded in the
# open-source KLayout DRC deck (Chipathon Week-37 slide "Integration problems: missing open source
# rules: via array spacing for arrays 4x4 or larger"). The tech LEF does carry it
# (ARRAYSPACING CUTSPACING 0.36 ARRAYCUTS 4 SPACING 0.36), so the router/PDN honour it, but nothing
# checks the final GDS. This does.
#
# Method: grow every via cut by 0.179 um, so cuts closer than 0.358 um fuse into one cluster. A
# cluster holding >= 16 cuts spread over >= 4 distinct columns AND >= 4 distinct rows is a dense
# (spacing < 0.36 um) array of 4x4 or larger -> violation. Arrays spaced >= 0.36 um stay separate
# clusters, so two small arrays placed too close together (forming one big dense array) are caught
# too. Controls (checked 2026-09-26): 4x4 @0.26 um -> flagged; two 3x4 @0.26 um butted 0.26 apart
# -> flagged; 4x4 @0.36 um and 3x9 @0.26 um -> clean.
#
# Run where the KLayout Python module is available (e.g. the apic_headless container):
#   python3 scripts/check_via_arrays.py gds/dla_engine_chip.gds dla_engine_chip
# Exit code 1 if any violation is found (outside or inside the SRAM IP).
import sys
import klayout.db as db

gds, top_name = sys.argv[1], sys.argv[2]
ly = db.Layout(); ly.read(gds)
top = ly.cell(top_name)
dbu = ly.dbu
GROW = int(round(0.179/dbu))
VIAS = {"Via1": (35, 0), "Via2": (38, 0), "Via3": (40, 0), "Via4": (41, 0), "Via5": (82, 0)}
SRAM = "gf180mcu_ocd_ip_sram__sram256x8m8wm1*"     # foundry IP: reported separately

def check(li, exclude_sram):
    it = top.begin_shapes_rec(li)
    if exclude_sram: it.unselect_cells(SRAM)
    cuts = db.Region(it); cuts.merged_semantics = False
    clusters = cuts.sized(GROW).merged()
    big = [p for p in clusters.each() if p.bbox().width()*dbu >= 2.0 and p.bbox().height()*dbu >= 2.0]
    bad = []
    for p in big:                                  # exact count only for the few big clusters
        inside = cuts.interacting(db.Region(p))
        xs = {b.bbox().center().x for b in inside.each()}
        ys = {b.bbox().center().y for b in inside.each()}
        if inside.count() >= 16 and len(xs) >= 4 and len(ys) >= 4:   # a real 4x4 needs >= 16 cuts
            bad.append((p.bbox(), len(xs), len(ys), inside.count()))
    return cuts.count(), clusters.count(), len(big), bad

nbad = 0
for name, (l, d) in VIAS.items():
    li = ly.find_layer(l, d)
    if li is None:
        print(f"{name}: layer {l}/{d} not present"); continue
    for excl in (True, False):
        n, nc, nbig, bad = check(li, excl)
        scope = "design (SRAM IP excluded)" if excl else "incl. SRAM IP"
        print(f"{name} [{scope}]: cuts={n} clusters={nc} big={nbig} VIOLATIONS={len(bad)}")
        for bb, nx, ny, k in bad[:5]:
            print(f"   dense {nx}x{ny} array ({k} cuts) at {bb.left*dbu:.2f},{bb.bottom*dbu:.2f}"
                  f" .. {bb.right*dbu:.2f},{bb.top*dbu:.2f}")
        nbad += len(bad)
sys.exit(1 if nbad else 0)
