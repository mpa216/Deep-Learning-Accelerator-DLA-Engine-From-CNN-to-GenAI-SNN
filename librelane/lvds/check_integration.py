#!/usr/bin/env python3
"""Integration checks on a LibreLane ODB of the LVDS-integrated ACV chip.

    openroad-librelane -no_init -exit -python librelane/lvds/check_integration.py <design.odb> [out.json]

Checks (each prints expected vs actual):
  1. u_lvds is placed at the configured origin, orientation R0, and FIRM/LOCKED/PLACED.
  2. every pin of the template exists; the 9 LVDS-integration pins carry the template's boxes.
  3. each LVDS_* net connects exactly its port and one u_lvds pin (no buffer, diode or other cell).
  4. u_lvds VDD/VSS are on DVDD/DVSS, and PDN vias land on the macro's Metal3 power straps.
  5. no standard cell overlaps the macro or its 10 um halo ("the cut" is respected).
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
       f"all {len(tpins)} template pins present; the 9 new ones with the template's boxes (8 per analog pin)",
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

print(f"INTEGRATION_CHECKS {'PASS' if fails == 0 else 'FAIL'} ({fails} failed)")
if OUT:
    json.dump(res, open(OUT, "w"), indent=1)
