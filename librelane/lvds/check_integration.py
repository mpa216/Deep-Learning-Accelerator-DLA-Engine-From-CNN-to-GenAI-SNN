#!/usr/bin/env python3
"""Integration checks on a LibreLane ODB of the LVDS-integrated ACV chip.

    openroad-librelane -no_init -exit -python librelane/lvds/check_integration.py <design.odb> [out.json]

Checks (each prints expected vs actual):
  1. u_lvds is placed at the configured origin, orientation R0, and FIRM/LOCKED/PLACED.
  2. every pin of the template exists; the 9 LVDS-integration pins carry the template's boxes.
  3. each LVDS_* net connects exactly its port and one u_lvds pin (no buffer, diode or other cell).
  4. u_lvds VDD/VSS are on DVDD/DVSS, and PDN vias land on the macro's Metal3 power straps.
  5. no standard cell overlaps the macro or its 10 um halo ("the cut" is respected).
  6. the macro outputs drive a nearby load (short nets), EN is connected.
  7. (routed designs) each LVDS_* net is a short drop under its own pad.
  8. (routed designs) no foreign signal wire inside the macro obstructions, and no switching net on Metal1-3 beside its RX
     input strips (top margin); all other crossings reported per layer and side.
"""
import json
import re
import sys

import odb

ODB = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else None
MACRO = "u_lvds"
ORIGIN_UM = (121.05, 875.80)
HALO_UM = 10.0
TEMPLATE = __file__.replace("lvds/check_integration.py", "A56_ACV_lvds.def")
LVDS_PORTS = {"LVDS_SCLK_P": "RX0_P", "LVDS_SCLK_N": "RX0_N", "LVDS_MOSI_P": "RX1_P",
              "LVDS_MOSI_N": "RX1_N", "LVDS_CSN_P": "RX2_P", "LVDS_CSN_N": "RX2_N"}

db = odb.dbDatabase.create()
odb.read_db(db, ODB)
block = db.getChip().getBlock()
dbu = block.getDbUnitsPerMicron()
um = lambda v: v / dbu
res = {"odb": ODB, "checks": {}}
fails = 0


def report(name, ok, expected, actual):
    global fails
    fails += 0 if ok else 1
    res["checks"][name] = {"ok": bool(ok), "expected": expected, "actual": actual}
    print(f"[{'PASS' if ok else 'FAIL'}] {name}\n        expected: {expected}\n        actual:   {actual}")


# 1. macro placement
inst = block.findInst(MACRO)
if inst is None:
    report("macro_placed", False, f"{MACRO} present", "missing")
    sys.exit(1)
x, y = inst.getLocation()
bb = inst.getBBox()
mw, mh = um(bb.xMax() - bb.xMin()), um(bb.yMax() - bb.yMin())
report("macro_placed",
       abs(um(x) - ORIGIN_UM[0]) < 1e-3 and abs(um(y) - ORIGIN_UM[1]) < 1e-3 and inst.getOrient() == "R0"
       and inst.getPlacementStatus() in ("FIRM", "LOCKED", "PLACED", "COVER"),
       f"origin {ORIGIN_UM} um, R0, fixed, 650 x 194.2 um",
       f"origin ({um(x):.3f}, {um(y):.3f}) um, {inst.getOrient()}, {inst.getPlacementStatus()}, {mw:.1f} x {mh:.1f} um, "
       f"master {inst.getMaster().getName()}")

# 2. pins against the template
tmpl = open(TEMPLATE).read()
tdbu = int(re.search(r"UNITS DISTANCE MICRONS (\d+)", tmpl).group(1))
tpins = {}
for blk in tmpl.split("\nPINS ", 1)[1].split("END PINS")[0].split(" ;\n"):
    m = re.search(r"-\s+(\S+)\s+\+\s+NET", blk)
    if m:
        tpins[m.group(1)] = sorted((l, round(int(a) * dbu / tdbu), round(int(b) * dbu / tdbu),
                                    round(int(c) * dbu / tdbu), round(int(d) * dbu / tdbu))
                                   for l, a, b, c, d in re.findall(
                                       r"LAYER\s+(\S+)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)", blk))
bterms = {bt.getName(): bt for bt in block.getBTerms()}
missing = [n for n in tpins if n not in bterms]
new_pins = ["LINK_SEL", "LINK_SEL_PU", "LINK_SEL_PD"] + list(LVDS_PORTS)
geo_bad = []
for n in new_pins:
    if n not in bterms:
        continue
    boxes = sorted((bx.getTechLayer().getName(), bx.xMin(), bx.yMin(), bx.xMax(), bx.yMax())
                   for bp in bterms[n].getBPins() for bx in bp.getBoxes())
    if boxes != tpins[n]:
        geo_bad.append(n)
report("template_pins", not missing and not geo_bad,
       f"all {len(tpins)} template pins present; the 9 new ones with the template's boxes (1 per pin; an analog pin is one bar under its pad's 8 fingers)",
       f"{len(tpins) - len(missing)} present (missing {missing}); new-pin geometry mismatches {geo_bad}; "
       f"boxes per analog pin {[sum(len(bp.getBoxes()) for bp in bterms[n].getBPins()) for n in LVDS_PORTS if n in bterms]}")

# 3. analog nets touch only their port and the macro pin
bad = {}
for port, mpin in LVDS_PORTS.items():
    net = block.findNet(port)
    if net is None:
        bad[port] = "net missing"
        continue
    its = [(it.getInst().getName(), it.getMTerm().getName()) for it in net.getITerms()]
    bts = [bt.getName() for bt in net.getBTerms()]
    if its != [(MACRO, mpin)] or bts != [port]:
        bad[port] = {"iterms": its, "bterms": bts}
report("analog_nets_clean", not bad,
       "each LVDS_* net = its port + exactly one u_lvds pin (RX0_P..RX2_N), nothing else",
       "all six clean" if not bad else bad)

# 4. macro power
pw = {}
for it in inst.getITerms():
    if it.getMTerm().getSigType() in ("POWER", "GROUND"):
        pw[it.getMTerm().getName()] = it.getNet().getName() if it.getNet() else None
straps = {"VDD": [], "VSS": []}
mt = inst.getMaster()
assert inst.getOrient() == "R0", "strap mapping below assumes an unrotated macro"
for mterm in mt.getMTerms():
    if mterm.getName() in straps:
        for mpin in mterm.getMPins():
            for box in mpin.getGeometry():
                if box.getTechLayer() and box.getTechLayer().getName() == "Metal3":
                    # R0 placement: block coordinates = master coordinates + instance origin
                    straps[mterm.getName()].append(
                        odb.Rect(box.xMin() + x, box.yMin() + y, box.xMax() + x, box.yMax() + y))
vias_on = {"VDD": 0, "VSS": 0}
for pin, netname in (("VDD", "DVDD"), ("VSS", "DVSS")):
    net = block.findNet(netname)
    if net is None:
        continue
    for sw in net.getSWires():
        for sb in sw.getWires():
            if not sb.isVia():
                continue
            vx1, vy1, vx2, vy2 = sb.xMin(), sb.yMin(), sb.xMax(), sb.yMax()
            for r in straps[pin]:
                # the via's footprint overlaps the strap (its enclosure may be wider than the 2.5 um strap)
                if vx1 < r.xMax() and r.xMin() < vx2 and vy1 < r.yMax() and r.yMin() < vy2:
                    vias_on[pin] += 1
                    break
report("macro_power",
       pw.get("VDD") == "DVDD" and pw.get("VSS") == "DVSS" and vias_on["VDD"] > 0 and vias_on["VSS"] > 0,
       "VDD->DVDD, VSS->DVSS, PDN vias landing on the macro's Metal3 straps for both nets",
       f"pins {pw}; Metal3 straps VDD {len(straps['VDD'])} / VSS {len(straps['VSS'])}; "
       f"PDN vias on them: VDD {vias_on['VDD']}, VSS {vias_on['VSS']}")

# 5. the cut: no standard cell inside the macro + halo
h = int(HALO_UM * dbu)
keep = odb.Rect(bb.xMin() - h, bb.yMin() - h, bb.xMax() + h, bb.yMax() + h)
inside = []
n_std = 0
for it in block.getInsts():
    m = it.getMaster()
    if m.isBlock() or it.getName() == MACRO:
        continue
    n_std += 1
    if not it.isPlaced():
        continue
    b = it.getBBox()
    if b.xMax() > keep.xMin() and b.xMin() < keep.xMax() and b.yMax() > keep.yMin() and b.yMin() < keep.yMax():
        inside.append(it.getName())
report("cut_respected", not inside,
       f"no standard cell inside the macro + {HALO_UM:.0f} um halo, x {um(keep.xMin()):.2f}-{um(keep.xMax()):.2f}, "
       f"y {um(keep.yMin()):.2f}-{um(keep.yMax()):.2f} um",
       f"{len(inside)} of {n_std} cells inside" + (f" (first: {inside[:5]})" if inside else ""))

# 6. macro outputs: short nets into a nearby buffer (Liberty max_capacitance 30 fF on RXk_O)
#    and EN driven by the link-select logic (only meaningful after repair_design / placement)
outs = {}
for it in inst.getITerms():
    nm = it.getMTerm().getName()
    if nm not in ("RX0_O", "RX1_O", "RX2_O", "EN"):
        continue
    net = it.getNet()
    if net is None:
        outs[nm] = "unconnected"
        continue
    ok, px, py = it.getAvgXY()
    xs, ys, others = [px], [py], []
    for o in net.getITerms():
        if o.getInst().getName() == MACRO:
            continue
        okk, ox, oy = o.getAvgXY()
        if okk:
            xs.append(ox)
            ys.append(oy)
        others.append(o.getInst().getMaster().getName().split("__")[-1])
    outs[nm] = {"net": net.getName(), "other_pins": len(others), "cells": sorted(set(others)),
                "hpwl_um": round(um(max(xs) - min(xs) + max(ys) - min(ys)), 1)}
short = all(isinstance(v, dict) and v["other_pins"] >= 1 and v["hpwl_um"] < 120
            for k, v in outs.items() if k != "EN")
report("macro_outputs_buffered", short and isinstance(outs.get("EN"), dict),
       "each RXk_O net: >= 1 load, half-perimeter < 120 um (about 30 fF with the load); EN connected",
       outs)

# 7./8. routing (only on a routed design: skipped while the LVDS nets carry no wires)
D = odb.dbWireDecoder


def segments(net):
    """(kind, layer, x0, y0, x1, y1) per routed path segment ("seg") and via ("via")."""
    w = net.getWire()
    if w is None:
        return
    dec = odb.dbWireDecoder()
    dec.begin(w)
    layer, prev = None, None
    op = dec.next()
    while op != D.END_DECODE:
        if op in (D.PATH, D.JUNCTION, D.SHORT, D.VWIRE):
            layer, prev = dec.getLayer(), None
        elif op in (D.POINT, D.POINT_EXT):
            p = dec.getPoint() if op == D.POINT else dec.getPoint_ext()[:2]
            if prev is not None and layer is not None and (p[0], p[1]) != (prev[0], prev[1]):
                yield ("seg", layer.getName(), prev[0], prev[1], p[0], p[1])
            prev = p
        elif op in (D.VIA, D.TECH_VIA):
            v = dec.getVia() if op == D.VIA else dec.getTechVia()
            if prev is not None:
                yield ("via", v.getName(), prev[0], prev[1], prev[0], prev[1])
            if layer is not None:
                bl, tl = v.getBottomLayer(), v.getTopLayer()
                layer = tl if layer.getName() == bl.getName() else bl
        op = dec.next()


routed = any(block.findNet(p) is not None and block.findNet(p).getWire() is not None for p in LVDS_PORTS)
if routed:
    # 7. each analog pad net: a short, straight drop from its pad pin row to its macro pin
    rt, bad7 = {}, []
    for port in LVDS_PORTS:
        net = block.findNet(port)
        segs = list(segments(net)) if net is not None else []
        wl = [s for s in segs if s[0] == "seg"]
        length = sum(abs(s[4] - s[2]) + abs(s[5] - s[3]) for s in wl)
        xs = [v for s in wl for v in (s[2], s[4])]
        pin_x = [v for bt in net.getBTerms() for bp in bt.getBPins() for bx in bp.getBoxes()
                 for v in (bx.xMin(), bx.xMax())] if net is not None else []
        within = bool(xs) and bool(pin_x) and min(xs) >= min(pin_x) - 5 * dbu and max(xs) <= max(pin_x) + 5 * dbu
        rt[port] = {"length_um": round(um(length), 1), "layers": sorted({s[1] for s in wl}),
                    "vias": sum(1 for s in segs if s[0] == "via"),
                    "x_um": [round(um(min(xs)), 2), round(um(max(xs)), 2)] if xs else None,
                    "under_own_pad": within}
        if not wl or length > 100 * dbu or not within:
            bad7.append(port)
    report("lvds_routes", not bad7,
           "each LVDS_* net routed as a short drop (< 100 um; the pad row is 39 um above the macro top) "
           "that stays under its own pad (x within the pad's pin span +- 5 um)",
           rt if not bad7 else {"bad": bad7, "routes": rt})

    # 8. foreign wiring over the receiver. The LEF obstructs Metal1-3 over the 600 x 144 um core only;
    #    the 25 um margin around it is a STANDARD-CELL-free margin (handoff sections 12 and 14.2), open to routing.
    #    Graded: (a) no foreign wire inside an obstruction on its layer (a real conflict), and
    #    (b) none on Metal1-3 in the TOP margin, where the six RX input strips run up to the pads
    #    (nothing in the LEF keeps wires off it, so this catches a run that routes beside the inputs).
    #    Reported: every crossing per layer and side; Metal4/5 over the core is allowed by the LEF
    #    (handoff: an optional Metal4/5 ROUTING_OBSTRUCTIONS over the input stage would keep it off).
    #    STATIC nets are exempt from (b) but listed: the link-select path (LINK_SEL -> 2-FF sync ->
    #    lvds_en -> buffer -> EN) only changes when the host flips LINK_SEL, and the bridge ignores the
    #    LVDS lanes for 64 clocks after every switch, so it cannot put switching noise on the inputs.
    LOW = ("Metal1", "Metal2", "Metal3")
    STATIC_NETS = {"LINK_SEL", "lvds_en"}
    obs = {}
    for ob in mt.getObstructions():
        if ob.getTechLayer() is not None:
            obs.setdefault(ob.getTechLayer().getName(), []).append(
                (ob.xMin() + x, ob.yMin() + y, ob.xMax() + x, ob.yMax() + y))
    core_top = max(r[3] for ly in LOW for r in obs.get(ly, []))
    core_bot = min(r[1] for ly in LOW for r in obs.get(ly, []))
    core_l = min(r[0] for ly in LOW for r in obs.get(ly, []))
    core_r = max(r[2] for ly in LOW for r in obs.get(ly, []))

    def side(cx, cy):
        if cy > core_top:
            return "top"
        if cy < core_bot:
            return "bottom"
        if cx < core_l:
            return "left"
        if cx > core_r:
            return "right"
        return "core"

    mine = {it.getNet().getName() for it in inst.getITerms() if it.getNet() is not None}
    over, nets_over, in_obs, in_top, static_top = {}, {}, set(), set(), {}
    for net in block.getNets():
        if net.getName() in mine or net.getSigType() in ("POWER", "GROUND"):
            continue
        for s in segments(net):
            if s[0] != "seg":
                continue
            x0, x1 = sorted((s[2], s[4]))
            y0, y1 = sorted((s[3], s[5]))
            ix0, ix1 = max(x0, bb.xMin()), min(x1, bb.xMax())
            iy0, iy1 = max(y0, bb.yMin()), min(y1, bb.yMax())
            if ix0 > ix1 or iy0 > iy1:
                continue
            ln = max(ix1 - ix0, iy1 - iy0)
            if ln <= 0:
                continue
            key = (s[1], side((ix0 + ix1) / 2, (iy0 + iy1) / 2))
            over[key] = over.get(key, 0) + ln
            nets_over.setdefault(key, set()).add(net.getName())
            w = db.getTech().findLayer(s[1]).getWidth() // 2          # the wire's real extent
            wr = (x0 - w, y0 - w, x1 + w, y1 + w)
            if any(wr[0] < r[2] and r[0] < wr[2] and wr[1] < r[3] and r[1] < wr[3] for r in obs.get(s[1], [])):
                in_obs.add((s[1], net.getName()))
            if s[1] in LOW and key[1] == "top":
                if net.getName() in STATIC_NETS:
                    k = f"{net.getName()} {s[1]}"
                    static_top[k] = static_top.get(k, 0) + ln
                else:
                    in_top.add((s[1], net.getName()))
    info = {f"{ly} {sd}": {"um": round(um(v), 1), "nets": sorted(nets_over[(ly, sd)])[:5]}
            for (ly, sd), v in sorted(over.items())}
    report("over_macro_routing", not in_obs and not in_top,
           "no foreign signal wire inside the receiver's LEF obstructions (Metal1-3 over its core), and no "
           "switching net on Metal1-3 in its top margin beside the six RX input strips (the static link-select "
           "nets LINK_SEL / lvds_en are listed, not graded); other crossings (the bottom and side margins, "
           "Metal4/5) are allowed and only reported",
           {"inside_obstructions": sorted(in_obs), "metal1_3_top_margin": sorted(in_top),
            "static_nets_in_top_margin_um": {k: round(um(v), 1) for k, v in sorted(static_top.items())},
            "crossings_by_layer_and_side": info})
else:
    print("[SKIP] lvds_routes, over_macro_routing: the LVDS nets carry no routing yet")

print(f"INTEGRATION_CHECKS {'PASS' if fails == 0 else 'FAIL'} ({fails} failed)")
if OUT:
    json.dump(res, open(OUT, "w"), indent=1)
