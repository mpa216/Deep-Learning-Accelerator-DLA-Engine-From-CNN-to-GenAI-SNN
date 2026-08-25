#!/usr/bin/env python3
# v4 power-pin connector for the A56/ACV block -- NEW west-edge padframe
# (auditor template 2026-08-24: DVSS moved from the NORTH edge to the WEST edge,
# default quiet-grounds removed, so DVDD=W21 and DVSS=W22 are now a west-edge pair).
#
# Both template power pins are bare Metal2 fingers on the WEST die margin:
#   DVDD  x[0,1]  y[906.36 .. 978.64]   (6 fingers)   -> own INNER ring
#   DVSS  x[0,1]  y[1006.36 .. 1078.64] (6 fingers)   -> own OUTER ring
# The regenerated PDN core ring (concentric, DVSS OUTER / DVDD INNER) west segments:
#   DVSS outer  Metal4 x[29.42,31.02]  (full height)
#   DVDD INNER  Metal4 x[32.72,34.32]  (full height)
#
# Fix: weld each west power pin EAST to its OWN-net M4 ring, entirely within the
# empty west die margin (x<35, outside CORE_AREA x>=40 -- no signal routing). Two
# changes vs v3 (which handled DVSS from the north with a thin strip + single via):
#   (1) SYMMETRIC + CURRENT-ROBUST: a FULL-HEIGHT Metal2 plate per pin (both nets),
#       and a vertical COLUMN of via2_3+via3_4 stacks per pin (many cuts) instead of
#       one 2-cut via -- fixes the thin-DVSS-strip / 2-cut EM/IR weakness.
#   (2) Lands on the M4 ring (M2->M3->M4); no M5 hop needed now that DVSS is west.
# DVDD's plate passes UNDER the DVSS outer M4 ring (Metal2 vs Metal4 = no short).
# Vias land in the clean y-gaps between the existing M5-strap->ring via4_5 pads
# (avoids Magic's "layer can't abut/partially overlap between subcells").
# Shapes go straight onto the DVDD/DVSS SPECIALNETs -> extraction sees them
# connected, no connect-by-label needed.
#
#   openroad-librelane -no_init -exit -python connect_power_v4.py <in.odb> <out.odb> <out.def>
import sys, odb
IN, OUT_ODB, OUT_DEF = sys.argv[1], sys.argv[2], sys.argv[3]
db = odb.dbDatabase.create(); odb.read_db(db, IN)
block = db.getChip().getBlock(); tech = db.getTech()
dbu = block.getDbUnitsPerMicron()
UM = lambda um: int(round(um*dbu))
u  = lambda v: round(v/dbu, 3)

M = {n: tech.findLayer(n) for n in ("Metal2","Metal3","Metal4")}
assert all(M.values()), "missing metal layer"

def find_via(prefix):
    v = block.findVia(prefix + "_2500_1200_1_2_1040_1040")
    if v: return v
    for vv in block.getVias():                       # fallback: any master with this prefix
        if vv.getName().startswith(prefix):
            return vv
    return None
V23 = find_via("via2_3"); V34 = find_via("via3_4")
assert V23 and V34, "missing via master(s)"
print(f"using vias: {V23.getName()} , {V34.getName()}")

# via3_4 Metal4 landing-pad half-extents (um), centred on the stamp point
V34_M4 = (0.625, 0.19)

try: WS = odb.dbWireShapeType("STRIPE")
except Exception: WS = "STRIPE"
def sw(net): return net.getSWires()[0]
def rect(net, layer, x0,y0,x1,y1): odb.dbSBox.create(sw(net), layer, x0,y0,x1,y1, WS)
def via(net, v, x, y): odb.dbSBox.create(sw(net), v, x, y, WS)

# own-net west M4 ring x-centre (um) -- DVSS outer @30.22, DVDD inner @33.52
RINGX = {"DVDD": 33.52, "DVSS": 30.22}
OPP   = {"DVDD": "DVSS", "DVSS": "DVDD"}
MINCLR = 0.30            # required opposite-net gap (um); gf180 M2..M4 spacing ~0.28
VPITCH = 1.20            # um between stacked via centres (>> min cut spacing)
AVOIDV = 1.60            # um: keep connector via clear of an existing ring via centre

def opp_m4_boxes(oppname):
    """opposite-net Metal4 rects + via M4 pads (bbox+0.3um), for short clearance."""
    out = []
    for s in block.findNet(oppname).getSWires():
        for b in s.getWires():
            if b.isVia():
                v = b.getBlockVia() or b.getTechVia()
                if v and M["Metal4"] in (v.getBottomLayer(), v.getTopLayer()):
                    out.append((b.xMin()-UM(0.3), b.yMin()-UM(0.3),
                                b.xMax()+UM(0.3), b.yMax()+UM(0.3)))
            elif b.getTechLayer().getName() == "Metal4":
                out.append((b.xMin(), b.yMin(), b.xMax(), b.yMax()))
    return out

def own_ring_via_ys(net, xc):
    """y-centres (dbu) of EXISTING vias on this net whose pad sits on the west ring."""
    ys = []; xlo, xhi = UM(xc-1.2), UM(xc+1.2)
    for s in net.getSWires():
        for b in s.getWires():
            if not b.isVia(): continue
            cx = (b.xMin()+b.xMax())//2; cy = (b.yMin()+b.yMax())//2
            if xlo <= cx <= xhi: ys.append(cy)
    return sorted(set(ys))

def min_gap(rect_dbu, boxes):
    x0,y0,x1,y1 = rect_dbu; best = 1e18
    for bx0,by0,bx1,by1 in boxes:
        dx = max(bx0-x1, x0-bx1); dy = max(by0-y1, y0-by1)
        if dx < 0 and dy < 0: g = max(dx, dy)
        elif dx < 0:          g = dy
        elif dy < 0:          g = dx
        else:                 g = (dx*dx+dy*dy)**0.5
        best = min(best, g)
    return round(best/dbu, 3)

report = []
for netname in ("DVDD", "DVSS"):
    net  = block.findNet(netname)
    xc   = RINGX[netname]; xcv = UM(xc)
    oppm4 = opp_m4_boxes(OPP[netname])
    exist = own_ring_via_ys(net, xc)
    x_east = UM(xc + V34_M4[0] + 0.20)                 # plate east edge, just past via M4 pad
    for bp in block.findBTerm(netname).getBPins():
        for box in bp.getBoxes():
            px0,py0,px1,py1 = box.xMin(),box.yMin(),box.xMax(),box.yMax()
            # (1) full-height Metal2 reach plate: pin (x=0) -> east of the M4 ring
            rect(net, M["Metal2"], px0, py0, x_east, py1)
            # (2) column of via2_3+via3_4 stacks up the pin height, in clean gaps
            worst = 1e18; placed = 0
            y = py0 + UM(0.55); ytop = py1 - UM(0.55)
            while y <= ytop:
                near = min((abs(y-ey) for ey in exist), default=UM(99))
                pad = (xcv-UM(V34_M4[0]), y-UM(V34_M4[1]),
                       xcv+UM(V34_M4[0]), y+UM(V34_M4[1]))
                g = min_gap(pad, oppm4)
                if near > UM(AVOIDV) and g >= MINCLR:
                    via(net, V23, xcv, y); via(net, V34, xcv, y)
                    placed += 1; worst = min(worst, g)
                y += UM(VPITCH)
            ok = placed >= 3                            # want a robust stack per finger
            report.append((netname, u(px0), u((py0+py1)//2), placed,
                           round(worst,3) if placed else None, ok))  # min_gap already um

allok = all(r[5] for r in report)
for r in report:
    print(f"  {'OK ' if r[5] else 'BAD'} {r[0]} pin@y={r[2]:<8}  vias={r[3]:<2} "
          f"opp-M4gap={r[4]}um")
tot = sum(r[3] for r in report)
print(f"\nfingers={len(report)}  total_via_stacks={tot}  all_robust(>=3)={allok}")
if not allok:
    print("!! not every finger got a robust via column -- NOT writing outputs"); sys.exit(2)
odb.write_db(db, OUT_ODB); odb.write_def(block, OUT_DEF)
print(f"WROTE {OUT_ODB}")
