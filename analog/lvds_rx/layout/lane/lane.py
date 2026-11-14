"""lane.py -- generator of ONE receiver lane, cell `lvds_lane` (task T9).

Circuit: subckt lvds_lane of netlist/lvds_rx_lvs_ref.spice (two secondary-ESD cells, stage 1, hysteresis stage, output stage).
Sizes: layout/device_table.json only (lib.device_table).  Net names in the layout are the reference's own names, so the flat
schematic used for LVS is the reference flattened, plus the dummy devices the layout adds.

Floorplan (x = 0 is the lane axis; the INP side of every matched pair is WEST, the INN side EAST; signal flow top -> bottom, so
the digital output is the row farthest from the inputs):

    S7 VDD ---------------------------------------------------------------   pins INP / INN (Metal3, top), VBP trunk
    R6   [ ESD_P ]            [ mpt tail ]            [ ESD_N mirrored ]
    S6 VSS ---------------------------------------------------------------
    R5              [ PMOS input quad: mp1 x2 + dump twins ]                   VREF, VB2 trunks below
    R4          [ m5a ]      [ m3 fold sinks, ABBA ]      [ m5b ]
    S4 VSS ---------------------------------------------------------------   VBN trunk
    R3       [ mnt ]     [ NMOS input quad: mn1 x2 + twins ]     [ mt2 ]
    S3 VDD ---------------------------------------------------------------
    R2             [ ms1 ] [ RL pair, ABBA, terminals up ] [ ms2 ] [ RS ]
    S2 VSS ---------------------------------------------------------------
    R1   [ mn3 ] [ mp3 ]  [ mpu2a ] [ loads2 ] [ mpu2b ]
    S1 VDD ---------------------------------------------------------------   EN trunk
    R0       [ NAND n|p ] [ INV1 n|p ] [ INV2 n|p ] [ INV3 n|p ]
    S0 VSS ---------------------------------------------------------------   pin OUT (Metal2, bottom)

Straps, spines and ring ties come from lib.power, every other wire from lib.route (grid 0.7 um, column i = 0 on the axis, so
the grid is its own mirror image).  build(stage=...) stops early for partial checks: "place" (leaves, straps, spines, ties,
trunks), "rails" (+ source bars to the straps), "route" (everything).
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LAYOUT = os.path.dirname(HERE)
ROOT = os.path.dirname(LAYOUT)
sys.path.insert(0, LAYOUT)
sys.path.insert(0, os.path.join(ROOT, "netlist"))

from lib import leaves, passives                      # noqa: E402
from lib.block import Block, snap                     # noqa: E402
from lib.device_table import DeviceTable              # noqa: E402
from lib.power import PowerPlan                       # noqa: E402
from lib.route import Router, L2, L3, PITCH           # noqa: E402
from lib.xform import MirrorX                         # noqa: E402

DT = DeviceTable()
CELL = "lvds_lane"
HALF = 71.4            # lane half width: 102 grid columns
GAP = 5.6              # gap between leaves of the analog rows: 8 grid columns
GAP_D = 4.2            # gap between leaves of the digital row
SPINE_X = 70.2
ESD_X = 67.2           # outer edge of the ESD cells

# bottom -> top.  ("tracks", n): n free grid rows; ("strap", net, name): four grid rows; ("row", name): a band of leaves
STACK = [("tracks", 1),
         ("strap", "VSS", "S0"), ("tracks", 3), ("row", "R0"), ("tracks", 4),
         ("strap", "VDD", "S1"), ("tracks", 3), ("row", "R1"), ("tracks", 3),
         ("strap", "VSS", "S2"), ("tracks", 3), ("row", "R2"), ("tracks", 3),
         ("strap", "VDD", "S3"), ("tracks", 3), ("row", "R3"), ("tracks", 4),
         ("strap", "VSS", "S4"), ("tracks", 3), ("row", "R4"), ("tracks", 7), ("row", "R5"), ("tracks", 3),
         ("strap", "VSS", "S6"), ("tracks", 3), ("row", "R6"), ("tracks", 2),
         ("strap", "VDD", "S7"), ("tracks", 3)]


# ----------------------------------------------------------------------------------------------------------- leaf builders
def res_spec(stem, a, b, **kw):
    r = DT.res[stem]
    return dict(R=r["R_tt_ohm"], w=r["r_width_um"], a=a, b=b, l_table=r["r_length_um"], **kw)


def _mld_outs():
    d, c = DT["mld"], DT["mlc"]
    assert (d.Wf, d.L) == (c.Wf, c.L)
    return d, [dict(sym="a", nf=d.nf, gate="d2a", drn="d2a"), dict(sym="b", nf=d.nf, gate="d2b", drn="d2b"),
               dict(sym="c", nf=c.nf, gate="d2b", drn="d2a"), dict(sym="d", nf=c.nf, gate="d2a", drn="d2b")]


def _esd(b, ll):
    r, dh = DT.res["resd"], DT.dio["desd_h"]
    return passives.esd_cell(b, "esdp" if isinstance(b, Block) else "esdn", ll, r["r_width_um"], r["r_length_um"], dh["w_um"], dh["l_um"],
                             nets=("INP", "gp", "VDD", "VSS") if isinstance(b, Block) else ("INN", "gn", "VDD", "VSS"))


def _rl(b, ll):
    # ABBA of two series pieces per resistor; rla reversed so that its OA end is the WEST column; terminals turned to the top
    cols = passives.plan_series({"rla": res_spec("rl", "VDD", "oa", reverse=True), "rlb": res_spec("rl", "VDD", "ob")},
                                ["rla", "rlb", "rlb", "rla"])
    cols = [dict(c, bot=c["top"], top=c["bot"]) for c in cols]
    return passives.res_array(b, "rl", cols, ll, "VSS")


def _rs(b, ll):
    cols = passives.plan_series({"rs1": res_spec("rs", "sa", "ts"), "rs2": res_spec("rs", "sb", "ts")}, ["rs1", "rs2"])
    return passives.res_array(b, "rs", cols, ll, "VSS")


def _nand_p(b, ll):
    d = DT["nand_p"]
    return leaves.grouped_row(b, "nandp", "p", d.Wf, d.L,
                              [dict(sym="P1", n=1, gate="d3", src="VDD", drn="nd", side="top", exit="W"),
                               dict(sym="P2", n=1, gate="EN", src="VDD", drn="nd", side="bot", exit="E")], ll, rail="VDD")


def _mn3(b, ll):
    d = DT["mn3"]
    outs = [dict(sym="D", nf=d.nf, gate="n3a", drn="n3a"), dict(sym="C", nf=d.nf, gate="n3a", drn="d3")]
    return leaves.mirror_interdig(b, "mn3", "n", outs, S="VSS", rail="VSS", ll=ll, Wf=d.Wf, L=d.L)


def _loads(b, ll):
    d, outs = _mld_outs()
    return leaves.mirror_interdig(b, "ld", "p", outs, S="VDD", rail="VDD", ll=ll, Wf=d.Wf, L=d.L)


BUILD = {
    "mpt": lambda b, ll: leaves.single(b, "mpt", DT["mpt"], ll, gate="VBP", drn="tp", src="VDD", rail="VDD"),
    # pair_dump puts gate A on the top strap leaving EAST and gate B on the bottom strap leaving WEST: the INN side is passed as A
    "pquad": lambda b, ll: leaves.pair_dump(b, "pq", DT["mp1"], DT["mpd"], ll, dict(gate="gn", drn="fb"), dict(gate="gp", drn="fa"), "tp", "tp", "VREF"),
    "nquad": lambda b, ll: leaves.pair_dump(b, "nq", DT["mn1"], DT["mnd"], ll, dict(gate="gn", drn="ob"), dict(gate="gp", drn="oa"), "tn", "VSS", "VREF"),
    "m3": lambda b, ll: leaves.pair_abba(b, "m3", DT["m3"], ll, A=dict(gate="VBN", drn="fa"), B=dict(gate="VBN", drn="fb"), S="VSS", rail="VSS"),
    "m5a": lambda b, ll: leaves.single(b, "m5a", DT["m5"], ll, gate="VB2", drn="oa", src="fa", rail="VSS"),
    "m5b": lambda b, ll: leaves.single(b, "m5b", DT["m5"], ll, gate="VB2", drn="ob", src="fb", rail="VSS"),
    "mnt": lambda b, ll: leaves.single(b, "mnt", DT["mnt"], ll, gate="VBN", drn="tn", src="VSS", rail="VSS"),
    "mt2": lambda b, ll: leaves.single(b, "mt2", DT["mt2"], ll, gate="VBN", drn="ts", src="VSS", rail="VSS"),
    "ms1": lambda b, ll: leaves.single(b, "ms1", DT["ms"], ll, gate="oa", drn="d2a", src="sa", rail="VSS"),
    "ms2": lambda b, ll: leaves.single(b, "ms2", DT["ms"], ll, gate="ob", drn="d2b", src="sb", rail="VSS"),
    "rl": _rl, "rs": _rs, "loads": _loads, "mn3": _mn3, "esd": _esd, "nandp": _nand_p,
    "mpu2a": lambda b, ll: leaves.single(b, "mpu2a", DT["mpu2"], ll, gate="EN", drn="d2a", src="VDD", rail="VDD"),
    "mpu2b": lambda b, ll: leaves.single(b, "mpu2b", DT["mpu2"], ll, gate="EN", drn="d2b", src="VDD", rail="VDD"),
    "mp3": lambda b, ll: leaves.pair_abba(b, "mp3", DT["mp3"], ll, A=dict(gate="d2a", drn="n3a"), B=dict(gate="d2b", drn="d3"), S="VDD", rail="VDD"),
    "nandn": lambda b, ll: leaves.stacked(b, "nandn", DT["nand_n"], DT["nand_n"], ll, dict(g_lo="EN", g_up="d3", src="VSS", mid="nm", drn="nd"), rail="VSS"),
}
for _stem, _g, _o in (("inv1", "nd", "i1"), ("inv2", "i1", "i2"), ("inv3", "i2", "OUT")):
    BUILD[_stem + "n"] = (lambda b, ll, s=_stem, g=_g, o=_o: leaves.single(b, s + "n", DT[s + "_n"], ll, gate=g, drn=o, src="VSS", rail="VSS"))
    BUILD[_stem + "p"] = (lambda b, ll, s=_stem, g=_g, o=_o: leaves.single(b, s + "p", DT[s + "_p"], ll, gate=g, drn=o, src="VDD", rail="VDD"))

_SIZE = {}


def size(name):
    """(width, height) of a leaf, measured by building it once on a scratch block (generators put the outer box at ll)."""
    if name not in _SIZE:
        lf = BUILD[name](Block("scratch"), (0.0, 0.0))
        _SIZE[name] = (snap(lf.bbox[2] - lf.bbox[0]), snap(lf.bbox[3] - lf.bbox[1]))
    return _SIZE[name]


# rows: (leaf, x rule, vertical alignment).  x rules are resolved in order: ("c", x) centre at x; ("r", ref, gap) right edge = left edge
# of leaf `ref` minus gap; ("l", ref, gap) left edge = right edge of `ref` plus gap; ("x", x) left edge at x
ROWS = {
    "R6": [("esd", ("x", -ESD_X), "bottom"), ("mpt", ("c", 0.0), "top")],          # the mirrored ESD cell is added by build()
    "R5": [("pquad", ("c", 0.0), "bottom")],
    "R4": [("m3", ("c", 0.0), "bottom"), ("m5a", ("r", "m3", GAP), "bottom"), ("m5b", ("l", "m3", GAP), "bottom")],
    "R3": [("nquad", ("c", 0.0), "top"), ("mnt", ("r", "nquad", GAP), "top"), ("mt2", ("l", "nquad", GAP), "top")],
    "R2": [("rl", ("c", 0.0), "bottom"), ("ms1", ("r", "rl", GAP), "bottom"), ("ms2", ("l", "rl", GAP), "bottom"), ("rs", ("l", "ms2", GAP), "bottom")],
    "R1": [("loads", ("c", 0.0), "bottom"), ("mpu2a", ("r", "loads", 4.9), "bottom"), ("mpu2b", ("l", "loads", 4.9), "bottom"),
           ("mp3", ("r", "mpu2a", 4.9), "bottom"), ("mn3", ("r", "mp3", 4.9), "top")],
    "R0": [],                                                                       # filled below (centred chain)
}
_chain = ["nandn", "nandp", "inv1n", "inv1p", "inv2n", "inv2p", "inv3n", "inv3p"]


def _chain_row():
    w = sum(size(n)[0] for n in _chain) + GAP_D * (len(_chain) - 1)
    out, prev = [], None
    for n in _chain:
        out.append((n, ("x", snap(-w / 2)) if prev is None else ("l", prev, GAP_D), "bottom" if n.endswith("n") else "top"))
        prev = n
    return out


def stack():
    """Resolve STACK into grid rows and y positions.  Returns (items, top_row): items carry j1 (first grid row), y, h."""
    ROWS["R0"] = _chain_row()
    j, out = 0, []
    for it in STACK:
        if it[0] == "tracks":
            out.append(dict(kind="tracks", j1=j, n=it[1]))
            j += it[1]
        elif it[0] == "strap":
            out.append(dict(kind="strap", net=it[1], name=it[2], j1=j, y=snap((j + 1.5) * PITCH)))
            j += 4
        else:
            h = max(size(n)[1] for n, _x, _a in ROWS[it[1]])
            y = snap((j - 1) * PITCH + 0.4)
            out.append(dict(kind="row", name=it[1], y=y, h=h))
            j = int(math.ceil((y + h + 0.4) / PITCH - 1e-6))     # first grid row at least 0.4 um above the band
    return out, j


# ----------------------------------------------------------------------------------------------------------- build
class Lane:
    pass


def build(stage="route", name=CELL):
    blk = Block(name)
    L = Lane()
    L.blk, L.leaf, L.row_of = blk, {}, {}
    items, jtop = stack()
    L.items, L.jtop = items, jtop
    L.y1, L.y2 = -PITCH / 2, snap(jtop * PITCH - PITCH / 2)      # lane box in y: half a pitch beyond the first / last grid row
    L.height = snap(L.y2 - L.y1)
    # ---- leaves
    for it in items:
        if it["kind"] != "row":
            continue
        x_of = {}
        for nm, rule, align in ROWS[it["name"]]:
            w, h = size(nm)
            if rule[0] == "c":
                x = rule[1] - w / 2
            elif rule[0] == "x":
                x = rule[1]
            elif rule[0] == "r":
                x = x_of[rule[1]][0] - rule[2] - w
            else:
                x = x_of[rule[1]][1] + rule[2]
            x = snap(x)
            y = it["y"] if align == "bottom" else snap(it["y"] + it["h"] - h)
            x_of[nm] = (x, x + w)
            key = "esdp" if nm == "esd" else nm
            L.leaf[key] = BUILD[nm](blk, (x, y))
            L.row_of[key] = it["name"]
            if nm == "esd":                                   # INN side: the same call, mirrored about the lane axis
                m = MirrorX(blk, 0.0)
                L.leaf["esdn"] = m.leaf(BUILD[nm](m, (x, y)))
                L.row_of["esdn"] = it["name"]
    lv = L.leaf
    # ---- power: straps edge to edge, spines, ring ties, trunk ties
    pp = L.pp = PowerPlan(blk, -HALF, HALF)
    S = L.strap = {it["name"]: pp.strap(it["net"], it["y"], name=it["name"]) for it in items if it["kind"] == "strap"}
    pp.spine("VSS", -SPINE_X)
    pp.spine("VDD", SPINE_X)
    ties = {"S0": ["nandn", "inv1n", "inv2n", "inv3n"], "S1": ["nandp", "inv1p", "inv2p", "inv3p", "loads", "mpu2a", "mpu2b", "mp3"],
            "S2": ["mn3", "ms1", "ms2", "rl", "rs"], "S4": ["mnt", "nquad", "mt2", "m3", "m5a", "m5b"], "S7": ["mpt"]}
    for sname, names in ties.items():
        for nm in names:
            pp.ring_tie(lv[nm], S[sname])
    for key in ("esdp", "esdn"):                              # ESD trunks: three Metal2 ties each to the strap below / above
        e = lv[key]
        for net, sname in (("VSS", "S6"), ("VDD", "S7")):
            p = [q for q in e.ports if q.net == net][0]
            for f in (0.25, 0.5, 0.75):
                pp.tie_m3(S[sname], p.rect[0] + f * (p.rect[2] - p.rect[0]), (p.rect[1] + p.rect[3]) / 2)
    # RL: each VDD end pad (a via stack) straight up to S3
    rl = lv["rl"]
    for i, c in enumerate(rl.info["cols"]):
        if not c["dummy"] and c["top"] == "VDD":
            cx = rl.info["ox"] + rl.info["xs"][i] + c["w"] / 2
            pp.tie_pad(S["S3"], cx, rl.info["oy"] + c["l"] + passives.GH_EXTRA["ppolyf_u_1k"] - 0.18)
    # DC currents (typical corner, device table) booked on the strap that carries them, for the planner's report.  The digital
    # chain draws only switching current and is not booked.
    cur = {d["stem"]: (d.get("ID_tt_uA") or 0.0) for d in DT.raw["devices"]}
    pp.load(S["S4"], cur["mnt"] + 2 * cur["m3"] + cur["mt2"], "mnt + 2 x m3 + mt2 (sources)")
    pp.load(S["S3"], 2 * cur["m3"] - cur["mpt"] + cur["mnt"], "RL pair = 2 x m3 - mpt + mnt")
    pp.load(S["S7"], cur["mpt"], "mpt (source)")
    # stage 3 has no current in the table: each mp3 copies at most the whole stage-2 tail current (upper bound)
    pp.load(S["S1"], 3 * cur["mt2"], "stage-2 loads (= mt2) + mp3 pair (bound: 2 x mt2)")
    pp.load(S["S2"], 2 * cur["mt2"], "mn3 pair (bound: 2 x mt2)")
    # ---- router: grid, closed boxes, trunks
    R = L.R = Router(blk, (-HALF, L.y1, HALF, L.y2))
    for lf in lv.values():
        R.close(lf.bbox)
    for s in S.values():
        R.adopt(s["net"], L3, s["x1"], s["y"] - s["w"] / 2, s["x2"], s["y"] + s["w"] / 2)
    L.trunk_row = {}
    for net, row in trunk_rows(items).items():
        R.trunk(net, row, -HALF, HALF)
        L.trunk_row[net] = row
    if stage == "place":
        return L
    raise NotImplementedError("stages beyond 'place' are added in the next piece")


def trunk_rows(items):
    """Grid row of every edge-to-edge trunk: counted from the first track row above (+k) or the last track row below (-k) a strap."""
    def tracks_after(name):       # first track row above strap / row `name`
        k = [i for i, it in enumerate(items) if it.get("name") == name][0]
        return items[k + 1]["j1"]

    def tracks_before(name):      # last track row below it
        k = [i for i, it in enumerate(items) if it.get("name") == name][0]
        return items[k - 1]["j1"] + items[k - 1]["n"] - 1
    return {"EN": tracks_before("S1"),            # top track under S1: between the digital row and the VDD strap
            "VBN": tracks_after("S4"),            # first track above S4: next to the VSS strap, under the fold sinks
            "VB2": tracks_before("R5") - 4,       # the channel between the sinks row and the PMOS quad: 7 tracks, VB2 on the 3rd,
            "VREF": tracks_before("R5") - 2,      # VREF on the 5th
            "VBP": tracks_before("S7")}           # under the top VDD strap
