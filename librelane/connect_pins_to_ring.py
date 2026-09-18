#!/usr/bin/env python3
# Connect the ACV die-edge power pins to the PDN core ring, across the clean die
# margin (no congested core edge -> no shorts).  Reuses the PDN's DRC-correct via
# masters. DVDD pin (west, Metal2) -> DVDD Metal4 ring (east of pin), Via2+Via3.
# DVSS pin (north, Metal2) -> DVSS Metal5 ring (south of pin), Via2+Via3+Via4.
# Run with the librelane OpenROAD (schema 0.126):
#   openroad-librelane -no_init -exit -python connect_pins_to_ring.py <in.odb> <out.odb> <out.def>
import sys, odb
IN, OUT_ODB, OUT_DEF = sys.argv[1], sys.argv[2], sys.argv[3]
db = odb.dbDatabase.create(); odb.read_db(db, IN)
block = db.getChip().getBlock(); tech = db.getTech(); dbu = block.getDbUnitsPerMicron()
UM = lambda v: int(round(v*dbu))
M2 = tech.findLayer("Metal2")
VIA2 = block.findVia("via2_3_10000_1200_1_9_1040_1040")
VIA3 = block.findVia("via3_4_10000_1200_1_9_1040_1040")
VIA4 = block.findVia("via4_5_3200_3200_3_3_1040_1040")
assert M2 and VIA2 and VIA3 and VIA4
try: WS = odb.dbWireShapeType("STRIPE")
except Exception: WS = "STRIPE"
def sw(net): return net.getSWires()[0]
def rect(net, x0,y0,x1,y1): odb.dbSBox.create(sw(net), M2, x0,y0,x1,y1, WS)
def via(net, v, x, y): odb.dbSBox.create(sw(net), v, x, y, WS)
def ring_segs(net_name, layer):
    out=[]
    for s in block.findNet(net_name).getSWires():
        for b in s.getWires():
            if b.isVia() or b.getTechLayer().getName()!=layer: continue
            out.append((b.xMin(),b.yMin(),b.xMax(),b.yMax()))
    return out

rep=[]
# --- DVDD: west pins -> DVDD Metal4 vertical ring segment (east of pin) ---
segs = [s for s in ring_segs("DVDD","Metal4") if (s[3]-s[1])>UM(100)]
for bp in block.findBTerm("DVDD").getBPins():
    for box in bp.getBoxes():
        px0,py0,px1,py1 = box.xMin(),box.yMin(),box.xMax(),box.yMax(); pcy=(py0+py1)//2
        # ring segment overlapping the pin's y-RANGE, within the clean margin (<45um east)
        c=[s for s in segs if not(s[3]<py0 or s[1]>py1) and s[0]>=px1 and s[0] < px1+UM(45)]
        if not c: rep.append(("DVDD",px0/dbu,pcy/dbu,"NO RING")); continue
        r=min(c, key=lambda s:s[0]); rcx=(r[0]+r[2])//2
        vy=min(max(pcy, max(py0,r[1])+UM(0.6)), min(py1,r[3])-UM(0.6))  # via y in pin AND ring
        rect(net:=block.findNet("DVDD"), px0, vy-UM(0.9), rcx+UM(1.0), vy+UM(0.9))
        via(net, VIA2, rcx, vy); via(net, VIA3, rcx, vy)
        rep.append(("DVDD",px0/dbu,pcy/dbu,f"->M4 ring x{rcx/dbu:.1f}@y{vy/dbu:.1f}"))

# --- DVSS: north pins -> DVSS Metal5 horizontal ring segment (south of pin) ---
# The via stack has a wide Via4 (M4-M5, 3.2um) Metal4 pad -> place it at an x
# inside the pin that clears the DVDD Metal4 straps (75um pitch), else it shorts.
segs = [s for s in ring_segs("DVSS","Metal5") if (s[2]-s[0])>UM(100)]
dvdd_m4 = [(s[0],s[2]) for s in ring_segs("DVDD","Metal4") if (s[3]-s[1])>UM(100)]
HALF = UM(2.1)   # half via4 pad + spacing
def clear_x(px0,px1):
    best=None; x=px0+UM(2)
    while x <= px1-UM(2):
        lo,hi = x-HALF, x+HALF
        if not any(hi>=a and lo<=b for (a,b) in dvdd_m4):
            cl=min([min(abs(lo-b),abs(hi-a)) for (a,b) in dvdd_m4] or [1e9])
            if best is None or cl>best[1]: best=(x,cl)
        x += UM(0.5)
    return best[0] if best else None
for bp in block.findBTerm("DVSS").getBPins():
    for box in bp.getBoxes():
        px0,py0,px1,py1 = box.xMin(),box.yMin(),box.xMax(),box.yMax(); pcx=(px0+px1)//2
        c=[s for s in segs if s[0]<=pcx<=s[2] and s[3]<=py1 and s[3] > py0-UM(60)]
        if not c: rep.append(("DVSS",pcx/dbu,py0/dbu,"NO RING")); continue
        r=max(c, key=lambda s:s[3]); rcy=(r[1]+r[3])//2
        vx=clear_x(px0,px1)
        if vx is None: rep.append(("DVSS",pcx/dbu,py0/dbu,"NO CLEAR X")); continue
        rect(net:=block.findNet("DVSS"), vx-UM(1.9), rcy-UM(0.5), vx+UM(1.9), py1)
        via(net, VIA2, vx, rcy); via(net, VIA3, vx, rcy); via(net, VIA4, vx, rcy)
        rep.append(("DVSS",pcx/dbu,py0/dbu,f"->M5 y{rcy/dbu:.1f} @x{vx/dbu:.1f}"))

for r in rep: print("  stamp", r)
odb.write_db(db, OUT_ODB); odb.write_def(block, OUT_DEF)
print(f"WROTE {OUT_ODB} ; stamps={len(rep)}")
