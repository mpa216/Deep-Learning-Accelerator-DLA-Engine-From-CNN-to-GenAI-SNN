"""macro.py -- generator of the macro, cell `lvds_rx_x3` (task T10): three instances of `lvds_lane`, one of `lvds_bias`,
and the top-level metal only.

Circuit: subckt lvds_rx_x3 of netlist/lvds_rx_lvs_ref.spice (XBIAS + XL0..XL2).  Hierarchy: the lane and the bias block
stay subcells (PLAN_V2 6.3: one lane instantiated three times); the schematic is hierarchical too.

Frame (spec/spec.yaml layout, spec/pins.yaml; decision in log/T10_notes.md): FIXED_BBOX = (0, 0) .. (650, H) with a 25 um
margin, core x 25..625.  Lane k has its axis at x = 100 + 200 k; the bias block abuts lane 2 (x 571.4 .. 624.6).  Every cell
shares one y origin Y0 (lane-local y = 0), chosen so that the bias block's bottom sits on the core's lower edge (y 25); the
lane tops are the core's upper edge.

Top-level metal:
  * gap fills: the lanes' seven Metal3 straps and five trunks (EN VBN VB2 VREF VBP) continue across the two 57.2 um gaps
  * RXk_P / RXk_N: Metal3 stub from the lane's INP / INN pad straight up to the top edge (pins.yaml x 50 + 200k / 150 + 200k:
    the pads sit on the lane's grid at +-49.7 from the axis, 0.3 um from the nominal x)
  * RXk_O: Metal2 down from the lane's OUT pad to channel row -2 under the lanes, Metal3 to x = 200 + 100 k, Metal2 down to
    the bottom edge;  EN: Metal2 up from the bottom edge at x = 100 to channel row -3, Metal3 east into gap 0-1, Metal2 up
    to the EN trunk fill.  Drawn by hand (the three lane grids are mutually offset: 200 um is not a multiple of 0.7)
  * every top-level shape is checked against the subcells' own shapes (Block.ghost) before it is painted
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LAYOUT = os.path.dirname(HERE)
ROOT = os.path.dirname(LAYOUT)
sys.path.insert(0, LAYOUT)
sys.path.insert(0, os.path.join(LAYOUT, "lane"))
sys.path.insert(0, os.path.join(LAYOUT, "bias"))

from lib.block import Block, snap                     # noqa: E402
from lib.route import PITCH, WIRE                     # noqa: E402
import lane                                            # noqa: E402
import bias                                            # noqa: E402

CELL = "lvds_rx_x3"
MARGIN = 25.0
CORE_W = 600.0
LANE_X = (100.0, 300.0, 500.0)                      # spec/pins.yaml lane_centres_um
BIAS_X = LANE_X[2] + lane.HALF                      # 571.4
OUT_X = (200.0, 300.0, 400.0)                       # spec/pins.yaml RX0_O .. RX2_O
EN_X = 100.0                                        # spec/pins.yaml EN
EN_RISER_X = LANE_X[0] + lane.HALF + 2.6            # 174.0: the EN riser in gap 0-1
ROW_OUT, ROW_EN = -2, -3                            # channel rows under the lanes (lane-local)
PIN_W3 = 0.5                                        # RX pin stubs (Metal3)


def rename_lane(k):
    ext = {"INP": f"RX{k}_P", "INN": f"RX{k}_N", "OUT": f"RX{k}_O", "EN": "EN", "VBN": "vbn", "VBP": "vbp", "VB2": "vb2",
           "VREF": "vref", "VDD": "VDD", "VSS": "VSS"}
    return lambda n: ext.get(n, f"L{k}:{n}")


def rename_bias(n):
    ext = {"EN": "EN", "VBN": "vbn", "VBP": "vbp", "VB2": "vb2", "VREF": "vref", "VDD": "VDD", "VSS": "VSS"}
    return ext.get(n, f"B:{n}")


TRUNK_NET = {"EN": "EN", "VBN": "vbn", "VBP": "vbp", "VB2": "vb2", "VREF": "vref"}


class Macro:
    pass


def build(L=None, B=None, name=CELL):
    """L, B: the built lane and bias block (lane.build("route"), bias.build("route")); built here when not given."""
    L = L or lane.build("route")
    B = B or bias.build("route")
    M = Macro()
    blk = M.blk = Block(name)
    M.L, M.B = L, B
    M.y0 = Y0 = snap(MARGIN - B.y1)                  # lane-local y = 0
    M.core = (MARGIN, MARGIN, MARGIN + CORE_W, snap(Y0 + L.y2))
    M.fixed_bbox = (0.0, 0.0, MARGIN * 2 + CORE_W, snap(M.core[3] + MARGIN))
    top = M.fixed_bbox[3]
    # ---- instances and their shapes (conflict checks only)
    for k, x in enumerate(LANE_X):
        blk.instance(lane.CELL, x, Y0)
        blk.ghost(L.blk.shapes, x, Y0, rename_lane(k))
    blk.instance(bias.CELL, BIAS_X, Y0)
    blk.ghost(B.blk.shapes, BIAS_X, Y0, rename_bias)
    items, _ = lane.stack()
    straps = [it for it in items if it["kind"] == "strap"]
    trows = lane.trunk_rows(items)
    # ---- gap fills
    M.fills = []
    for k in range(2):
        xa, xb = LANE_X[k] + lane.HALF, LANE_X[k + 1] - lane.HALF
        for s in straps:
            r = blk.rect("m3", xa, Y0 + s["y"] - 1.25, xb, Y0 + s["y"] + 1.25, s["net"], "fill")
            M.fills.append((s["name"], s["net"], r))
        for net, row in trows.items():
            y = Y0 + row * PITCH
            r = blk.rect("m3", xa, y - WIRE / 2, xb, y + WIRE / 2, TRUNK_NET[net], "fill")
            M.fills.append((net, TRUNK_NET[net], r))
    # ---- outputs: lane OUT pad -> channel row -2 -> x = 200 + 100 k -> bottom edge
    i_out = L.pins["OUT"][0]
    yo = snap(Y0 + ROW_OUT * PITCH)
    M.routes = {}
    for k, x in enumerate(LANE_X):
        net, xo, xp = f"RX{k}_O", snap(x + i_out * PITCH), OUT_X[k]
        blk.vwire("m2", xo, Y0, yo, WIRE, net, "route")
        blk.via2(xo, yo, net)
        blk.hwire("m3", yo, xo, xp, WIRE, net, "route")
        blk.via2(xp, yo, net)
        blk.vwire("m2", xp, yo, 0.0, WIRE, net, "route")
        blk.add_pin(net, "m2", xp, 0.3)
        M.routes[net] = dict(m2=round(abs(Y0 - yo) + yo, 2), m3=round(abs(xp - xo), 2))
    # ---- EN: bottom edge at x = 100 -> channel row -3 -> gap 0-1 -> up to the EN trunk fill
    ye, yt = snap(Y0 + ROW_EN * PITCH), snap(Y0 + trows["EN"] * PITCH)
    blk.vwire("m2", EN_X, 0.0, ye, WIRE, "EN", "route")
    blk.via2(EN_X, ye, "EN")
    blk.hwire("m3", ye, EN_X, EN_RISER_X, WIRE, "EN", "route")
    blk.via2(EN_RISER_X, ye, "EN")
    blk.vwire("m2", EN_RISER_X, ye, yt, WIRE, "EN", "route")
    blk.via2(EN_RISER_X, yt, "EN")
    blk.add_pin("EN", "m2", EN_X, 0.3)
    M.routes["EN"] = dict(m2=round(ye + (yt - ye), 2), m3=round(EN_RISER_X - EN_X, 2))
    # ---- RX pins: Metal3 stub from the lane's INP / INN pad to the top edge
    M.pins = {}
    for k, x in enumerate(LANE_X):
        for p, suf in (("INP", "P"), ("INN", "N")):
            i, j, _ = L.pins[p]
            xp, yp = snap(x + i * PITCH), snap(Y0 + j * PITCH)
            net = f"RX{k}_{suf}"
            blk.rect("m3", xp - PIN_W3 / 2, yp - 0.2, xp + PIN_W3 / 2, top, net, "pin_stub")
            blk.add_pin(net, "m3", xp, top - 0.3)
            M.pins[net] = (xp, top)
    # ---- power pins on the fills of gap 0-1 (S7 VDD, S0 VSS)
    s7 = [s for s in straps if s["name"] == "S7"][0]
    s0 = [s for s in straps if s["name"] == "S0"][0]
    xm = (LANE_X[0] + LANE_X[1]) / 2
    blk.add_pin("VDD", "m3", xm, Y0 + s7["y"])
    blk.add_pin("VSS", "m3", xm, Y0 + s0["y"])
    # ---- FIXED_BBOX (Magic property, lambda = 0.05 um; PLAN_V2 L7) for the LEF of T12
    fb = " ".join(str(int(round(v / 0.05))) for v in M.fixed_bbox)
    blk.ops.append(("t", f"property FIXED_BBOX \"{fb}\""))
    return M


def schematic(M, name=CELL):
    """Hierarchical LVS schematic: subckts lvds_lane and lvds_bias (each = the reference flattened + the layout's dummies, as
    checked in T9 / T10 A2), then lvds_rx_x3 exactly as in the reference file (its four instance lines)."""
    import re
    ref = open(os.path.join(ROOT, "netlist", "lvds_rx_lvs_ref.spice")).read()
    m = re.search(r"^\.subckt lvds_rx_x3 .*?^\.ends lvds_rx_x3\s*$", ref, re.M | re.S)
    top = m.group(0) if name == CELL else m.group(0).replace("lvds_rx_x3", name)
    return lane.schematic(M.L) + bias.schematic(M.B) + top + "\n"


if __name__ == "__main__":                 # host dry run: python3 layout/macro/macro.py
    import time
    t0 = time.time()
    M = build()
    print("built in %.1f s | Y0 %.2f | core %s | FIXED_BBOX %s | shapes %d (ghosts incl.) | instances %s" % (
        time.time() - t0, M.y0, M.core, M.fixed_bbox, len(M.blk.shapes), M.blk.instances))
    print("routes", M.routes)
    print("pins", M.pins)
    sch = schematic(M)
    print("schematic lines", len(sch.splitlines()))
