#!/usr/bin/env python3
# Stamp DRC-clean power connections from the ACV template power pins (bare Metal2
# boxes placed in the die margin by FP_TEMPLATE_COPY_POWER_PINS) into the routed
# PDN grid.  Net-safe: only ties each pin to SAME-NET grid metal, reusing the
# PDN's own via masters (DRC-correct by construction).
#   DVDD (west edge, Metal2)  -> extend Metal2 east to the DVDD Metal1 rails, Via1.
#   DVSS (north edge, Metal2) -> extend Metal2 into the overlapping DVSS Metal4
#                                strap, Via2+Via3 stack.
# Usage: openroad -no_init -exit -python connect_power_pins.py <in.odb> <out.odb> <out.def>
import sys, odb

IN, OUT_ODB, OUT_DEF = sys.argv[1], sys.argv[2], sys.argv[3]
db = odb.dbDatabase.create()
odb.read_db(db, IN)
block = db.getChip().getBlock(); tech = db.getTech(); dbu = block.getDbUnitsPerMicron()
M2 = tech.findLayer("Metal2")
VIA1 = block.findVia("via1_2_10000_1200_1_9_1040_1040")
VIA2 = block.findVia("via2_3_10000_1200_1_9_1040_1040")
VIA3 = block.findVia("via3_4_10000_1200_1_9_1040_1040")
assert M2 and VIA1 and VIA2 and VIA3, "missing layer/via masters"
UM = lambda v: int(round(v*dbu))

def wst():
    # dbWireShapeType STRIPE, tolerant of binding differences
    try: return odb.dbWireShapeType("STRIPE")
    except Exception: return "STRIPE"
WS = wst()

def add_rect(net, layer, x0, y0, x1, y1):
    sw = net.getSWires()[0] if net.getSWires() else odb.dbSWire.create(net, odb.dbWireType("ROUTED"))
    odb.dbSBox.create(sw, layer, x0, y0, x1, y1, WS)

def add_via(net, via, x, y):
    sw = net.getSWires()[0]
    odb.dbSBox.create(sw, via, x, y, WS)

def grid_boxes(net_name, layer_name):
    net = block.findNet(net_name); out=[]
    for sw in net.getSWires():
        for b in sw.getWires():
            if b.isVia(): continue
            if b.getTechLayer().getName()==layer_name:
                out.append((b.xMin(),b.yMin(),b.xMax(),b.yMax()))
    return out

def overlaps(a0,a1,b0,b1): return not (a1 < b0 or a0 > b1)

report=[]
for name in ("DVDD","DVSS"):
    net = block.findNet(name)
    bt = block.findBTerm(name)
    for bp in bt.getBPins():
        for box in bp.getBoxes():
            px0,py0,px1,py1 = box.xMin(),box.yMin(),box.xMax(),box.yMax()
            if name=="DVDD":
                rails=[r for r in grid_boxes("DVDD","Metal1")
                       if overlaps(r[1],r[3],py0,py1) and r[0] < px1 + UM(12)]
                if not rails:
                    report.append(("DVDD",px0/dbu,py0/dbu,"NO RAIL")); continue
                east = max(r[0] for r in rails) + UM(1.0)      # reach past rail west end
                add_rect(net, M2, px0, py0, east, py1)          # Metal2 bridge patch
                for r in rails:
                    vx = r[0] + UM(0.5); vy = (r[1]+r[3])//2
                    add_via(net, VIA1, vx, vy)                  # M1<->M2 on the DVDD rail
                report.append(("DVDD",px0/dbu,(py0+py1)/2/dbu,f"{len(rails)} Via1 -> x{east/dbu:.1f}"))
            else:  # DVSS north edge: extend Metal2 sideways in the empty north
                   # margin to the NEAREST DVSS Metal4 strap, then Via2+Via3 stack.
                straps=[s for s in grid_boxes("DVSS","Metal4") if (s[3]-s[1]) > UM(100)]
                if not straps:
                    report.append(("DVSS",px0/dbu,py0/dbu,"NO STRAP")); continue
                pcx=(px0+px1)//2
                s=min(straps, key=lambda s: abs(((s[0]+s[2])//2)-pcx))
                vx=min(max(pcx, s[0]+UM(0.5)), s[2]-UM(0.5))    # via x inside strap
                y_lo=max(py0-UM(5), UM(1095.0))                 # stay in north margin
                vy=(y_lo+py1)//2
                mx0=min(px0, vx)-UM(0.6); mx1=max(px1, vx)+UM(0.6)
                add_rect(net, M2, mx0, y_lo, mx1, py1)          # Metal2 patch pin->strap
                add_via(net, VIA2, vx, vy)                      # M2<->M3
                add_via(net, VIA3, vx, vy)                      # M3<->M4 (stacked)
                report.append(("DVSS",px0/dbu,(py0+py1)/2/dbu,f"stack@x{vx/dbu:.1f} (strap dx={abs(((s[0]+s[2])//2)-pcx)/dbu:.1f}um)"))

for r in report: print("  stamped", r)
odb.write_db(db, OUT_ODB)
odb.write_def(block, OUT_DEF)
print(f"WROTE {OUT_ODB} / {OUT_DEF} ; total stamps={len(report)}")
