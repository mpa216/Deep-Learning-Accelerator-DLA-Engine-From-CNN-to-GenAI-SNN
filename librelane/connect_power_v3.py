#!/usr/bin/env python3
# v3 power-pin connector for the A56/ACV block.
#
# Problem: FP_TEMPLATE_COPY_POWER_PINS drops the padframe's DVDD/DVSS power as
# bare Metal2 boxes in the die margin (DVDD west edge x~0-1um; DVSS north edge
# y~1109-1110um), but the block PDN delivers power on a Metal4/Metal5 core ring
# ~33um inland -> the pins are electrically islanded (LVS: DVDD/DVSS each split).
#
# Fix (community-endorsed connector-cell idea, done as an in-margin weld): for
# each template pin, run a short Metal2 reach through the EMPTY die margin to a
# point over its OWN-net ring, then a vertical via stack up to that ring.  The
# reaches live entirely in the die-to-core margin (DVDD x<35, DVSS y>1075) where
# there is no signal routing, and every via pad lands on same-net metal with a
# checked clearance to the opposite net -- unlike the prior core-edge stamp that
# shorted (via4 M4-pad onto a DVDD M4 strap).
#
# Concentric ring ordering (from introspection): DVSS is the OUTER ring
# everywhere; DVDD is INNER.
#   DVDD west M4 ring x[32.72,34.32]  (DVSS west M4 ring x[29.42,31.02] = outer)
#   DVSS north M5 ring y[1075.54,1077.14] (DVDD north M5 ring y[1072.24,1073.84]=inner)
#
#   openroad-librelane -no_init -exit -python connect_power_v3.py <in.odb> <out.odb> <out.def>
import sys, odb
IN, OUT_ODB, OUT_DEF = sys.argv[1], sys.argv[2], sys.argv[3]
db = odb.dbDatabase.create(); odb.read_db(db, IN)
block = db.getChip().getBlock(); tech = db.getTech()
dbu = block.getDbUnitsPerMicron()
UM = lambda um: int(round(um*dbu))
u  = lambda v: round(v/dbu, 3)

M = {n: tech.findLayer(n) for n in ("Metal2","Metal3","Metal4","Metal5")}
# small connector vias (pad sizes from getViaParams; see _via_dims.py):
#  via2_3_2500: M2 0.8x0.38 -> M3 0.9x0.28 ; via3_4_2500: M3 0.9x0.28 -> M4 1.25x0.38
#  via4_5_3200: M4 1.6x1.42 -> M5 1.42x1.6
V23 = block.findVia("via2_3_2500_1200_1_2_1040_1040")
V34 = block.findVia("via3_4_2500_1200_1_2_1040_1040")
V45 = block.findVia("via4_5_3200_3200_3_3_1040_1040")
assert all(M.values()) and V23 and V34 and V45, "missing layer/via master"
# via pad half-extents (um) centred on the stamp point, per layer
PAD = {  # via -> {layer: (halfW, halfH)}
    "V23": {"Metal2": (0.40,0.19), "Metal3": (0.45,0.14)},
    "V34": {"Metal3": (0.45,0.14), "Metal4": (0.625,0.19)},
    "V45": {"Metal4": (0.80,0.71), "Metal5": (0.71,0.80)},
}
try: WS = odb.dbWireShapeType("STRIPE")
except Exception: WS = "STRIPE"

def sw(net): return net.getSWires()[0]
def rect(net, layer, x0,y0,x1,y1): odb.dbSBox.create(sw(net), layer, x0,y0,x1,y1, WS)
def via(net, v, x, y): odb.dbSBox.create(sw(net), v, x, y, WS)

def opp_boxes(netname):
    """opposite-net blocking rects per layer name: plain metal exactly, vias as
    bbox+0.3um on both their metal layers (conservative)."""
    d = {n: [] for n in M}
    net = block.findNet(netname)
    for s in net.getSWires():
        for b in s.getWires():
            if b.isVia():
                bb=(b.xMin()-UM(0.3), b.yMin()-UM(0.3), b.xMax()+UM(0.3), b.yMax()+UM(0.3))
                v = b.getBlockVia() or b.getTechVia()
                if v is None: continue
                for L in (v.getBottomLayer(), v.getTopLayer()):
                    if L and L.getName() in d: d[L.getName()].append(bb)
            else:
                L=b.getTechLayer().getName()
                if L in d: d[L].append((b.xMin(),b.yMin(),b.xMax(),b.yMax()))
    return d

def min_gap(rect_dbu, boxes):
    """min edge gap (um) from rect to any box; negative => overlap."""
    x0,y0,x1,y1 = rect_dbu; best = 1e9
    for (bx0,by0,bx1,by1) in boxes:
        dx = max(bx0 - x1, x0 - bx1)   # >0 if separated in x
        dy = max(by0 - y1, y0 - by1)
        if dx < 0 and dy < 0:  g = max(dx, dy)     # overlap: negative
        elif dx < 0:           g = dy
        elif dy < 0:           g = dx
        else:                  g = (dx*dx+dy*dy)**0.5
        best = min(best, g)
    return round(best/dbu, 3)

def pad_rect(x, y, vkey, layer):
    hw,hh = PAD[vkey][layer]; return (x-UM(hw), y-UM(hh), x+UM(hw), y+UM(hh))

report = []
MINCLR = 0.30   # required opposite-net gap (um); gf180 M2-M4 spacing ~0.28

# ---------------- DVDD: 6 west pins -> DVDD inner M4 ring ----------------
XR = UM(33.52)                     # DVDD M4 west-ring centre
oppD = opp_boxes("DVSS")           # opposite net = DVSS
dvdd = block.findNet("DVDD")
for bp in block.findBTerm("DVDD").getBPins():
    for box in bp.getBoxes():
        px0,py0,px1,py1 = box.xMin(),box.yMin(),box.xMax(),box.yMax()
        cy = (py0+py1)//2
        # M2 reach from pin (x0=0) east to just past the via2_3 M2 pad (x~33.9);
        # kept short (34.5) so the DVSS north strips have M2 room in the NW corner
        rect(dvdd, M["Metal2"], px0, py0, UM(34.5), py1)
        # stacked via2_3 + via3_4 at ring centre, pin-y
        via(dvdd, V23, XR, cy); via(dvdd, V34, XR, cy)
        g4 = min_gap(pad_rect(XR,cy,"V34","Metal4"), oppD["Metal4"])
        g2 = min_gap((px0,py0,UM(35.0),py1), oppD["Metal2"])
        report.append(("DVDD", u(px0),u(cy), f"M4gap={g4} M2gap={g2}", g4>=MINCLR and g2>=MINCLR))

# ---------------- DVSS: 6 north pins -> DVSS outer M5 ring ----------------
YR = UM(1076.34)                   # DVSS M5 north-ring centre
oppV = opp_boxes("DVDD")           # opposite net = DVDD (now incl. DVDD reaches)
ownV = opp_boxes("DVSS")           # own net (for same-net M4 straps)
# Metal4 shapes crossing y=YR: DVDD = short blockers; DVSS = same-net straps the
# via M4 pad must sit fully-inside or fully-clear of (never straddle -> Magic
# "can't abut/partially overlap between subcells").
dvdd_m4 = [b for b in oppV["Metal4"] if b[1] <= YR <= b[3]]   # opposite (short)
# EVERY M4 strap crossing the ring carries an existing strap->ring PDN via at that
# crossing. Land the connector BETWEEN straps (pad fully clear of them all) so we
# never sit on a strap (opposite-net short) NOR over an existing via ("layer can't
# abut/partially overlap between subcells" -- what went 8->16 when we landed on/in
# the DVSS strap). This mirrors why the DVDD vias land clean: between existing vias.
ring_m4 = [b for b in (oppV["Metal4"]+ownV["Metal4"]) if b[1] <= YR <= b[3]]
dvss = block.findNet("DVSS")
HP = UM(0.8)                       # via4_5 M4 pad half-width

def clear_x(px0, px1):
    """pick via x near the pin whose M4 pad (+/-0.8) sits FULLY CLEAR (>=0.4um) of
    every M4 strap (both nets) -> a clean ring gap with no existing via; the narrow
    reach strip must still overlap the pin and clear DVDD M2 by >=MINCLR. Prefer the
    landing closest to the pin centre (shortest strip). Window allows +/-2um lateral
    so the middle pin (whose own x-span is fully covered by straps) can reach a gap."""
    # Two passes: (1) land WITHIN the pin (solid strip overlap); (2) only if the
    # pin's whole x-span is strap-covered (middle pin) allow +/-2um lateral with a
    # >=0.3um pin overlap. Each pass maximises min(strap-clear g4, reach-clear g2).
    for lo, hi, need_ov in ((px0+HP, px1-HP, 0), (px0-UM(2.0), px1+UM(2.0), UM(0.3))):
        best=None; x=lo
        while x <= hi:
            p0,p1 = x-HP, x+HP
            pad=(p0, YR-UM(0.71), p1, YR+UM(0.71))
            strip=(x-UM(1.5), UM(1075.0), x+UM(1.5), UM(1110.0))
            gm=min_gap(pad, ring_m4); g4=min_gap(pad, dvdd_m4)
            g2=min_gap(strip, oppV["Metal2"])
            ov=min(x+UM(1.5),px1)-max(x-UM(1.5),px0)
            if gm>=0.4 and g4>=MINCLR and g2>=MINCLR and ov>=need_ov:
                score=min(g4,g2)
                if best is None or score>best[0]: best=(score, x, g4, g2)
            x += UM(0.1)
        if best: return (best[1], None, best[2], best[3])
    return None

for bp in block.findBTerm("DVSS").getBPins():
    for box in bp.getBoxes():
        px0,py0,px1,py1 = box.xMin(),box.yMin(),box.xMax(),box.yMax()
        c = clear_x(px0,px1)
        if c is None:
            report.append(("DVSS", u(px0),u(py0), "NO CLEAR X", False)); continue
        vx = c[0]
        # M2 reach strip: pin (y1=1110) down to just past the M5 ring. Normally a
        # narrow +/-1.5um strip (solid pin overlap since the via is in/near the
        # pin); for the lateral middle pin, whose via sits just outside the pin,
        # extend the strip toward the pin so it overlaps by >=1um for a solid tie.
        sx0, sx1 = vx-UM(1.5), vx+UM(1.5)
        if min(sx1,px1)-max(sx0,px0) < UM(1.0):
            if vx >= (px0+px1)//2: sx0 = min(sx0, px1-UM(1.0))   # via east of pin
            else:                  sx1 = max(sx1, px0+UM(1.0))   # via west of pin
        rect(dvss, M["Metal2"], sx0, UM(1075.0), sx1, py1)
        via(dvss, V23, vx, YR); via(dvss, V34, vx, YR); via(dvss, V45, vx, YR)
        report.append(("DVSS", u(vx),u(py1), f"g4={c[2]} g2={c[3]}", True))

ok = all(r[4] for r in report)
for r in report: print(f"  {'OK ' if r[4] else 'BAD'} {r[0]} @({r[1]},{r[2]}) {r[3]}")
print(f"\nstamps={len(report)}  all_clear={ok}")
if not ok:
    print("!! clearance check FAILED -- not writing outputs"); sys.exit(2)
odb.write_db(db, OUT_ODB); odb.write_def(block, OUT_DEF)
print(f"WROTE {OUT_ODB}")
