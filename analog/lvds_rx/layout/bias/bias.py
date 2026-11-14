"""bias.py -- generator of the shared bias block, cell `lvds_bias` (task T10).

Circuit: subckt lvds_bias of netlist/lvds_rx_lvs_ref.spice (EN inverter, the resistor reference RRB into the NMOS mirror
MBN:MBS, the PMOS mirror MBP:MB2P, the VB2 diode MB2 with RRF, the Vref divider RRDT / RRDB with its switch MVS and the
Vref capacitor, three pull-downs / pull-ups for EN low).  Sizes: layout/device_table.json only.  Net names are the
reference's own (enb nrb vf nmid inside), so the flat LVS schematic is the reference flattened plus the layout's dummies.

Place in the macro: the column east of lane 2 (macro x 571.4 to 624.6), inside the 600 um core (spec/spec.yaml layout:
macro_max_um [600, 150] plus a 25 um margin; the pin x positions of spec/pins.yaml are unchanged).  Coordinates: x = 0 is
the west edge, which abuts lane 2's east edge; y is the lane's own y (grid row j at y = 0.7 j), so the straps S2, S4, S6
(VSS), S7 and the short west strap S1v (VDD) sit at the lane's strap rows and join lane 2's straps by abutment, and the
outputs leave at the lane's trunk rows on the west edge (EN in, VBN, VB2, VREF, VBP out).  B0 (VSS) lies below the lane.

    S7 VDD ------------------------------------------------   pin VBP (row 171, west)
         (free)                 [ MBP : MB2P mirror ]
    S6 VSS ------------------------------------------------
      [ mpd_n ]                 [ Vref capacitor   ]          pins VB2, VREF, VBN (rows 126, 128, 107, west)
    S4 VSS ------------------------------------------------
      [ mpd_2 ]
      [ mvs   ]         [ RRDT / RRDB array, terminals up ]
    S2 VSS ------------------------------------------------
      [ men_p ] [ mpu_p ]
    S1v VDD ---------            [ RRB / RRF array,     ]     pin EN (row 25, west)
      [ msw        ]             [ terminals down       ]
      [ men_n ] [ mb2 ]          [ MBN : MBS mirror     ]
    B0 VSS ------------------------------------------------
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LAYOUT = os.path.dirname(HERE)
ROOT = os.path.dirname(LAYOUT)
sys.path.insert(0, LAYOUT)
sys.path.insert(0, os.path.join(LAYOUT, "lane"))

from lib import leaves, passives                      # noqa: E402
from lib.block import Block, snap                     # noqa: E402
from lib.power import PowerPlan                       # noqa: E402
from lib.route import Router, L2, L3, PITCH           # noqa: E402
import lane                                            # noqa: E402

DT = lane.DT
CELL = "lvds_bias"
W_B = 53.2                 # 76 grid columns: macro x 571.4 .. 624.6
X_R = 52.8                 # east edge of the leaves (0.4 um inside the cell)
X_L = 2.1                  # west edge of the leaves: the corridor west of it holds the VSS spine and the pins
SPINE_X = 1.0              # VSS spine (Metal2, 1.2 um): B0, S2, S4, S6
J_B0 = -23                 # first row of strap B0
X_S1V = 22.4               # east end of the short VDD strap S1v (it stops 2.7 um short of the RRB / RRF array)


# ----------------------------------------------------------------------------------------------------------- leaf builders
def _arr(stems, pattern, up, b, inst, ll):
    nets = {"rb": ("nrb", "VBN"), "rf": ("vf", "VSS"), "rdt": ("VDD", "VREF"), "rdb": ("VREF", "nmid")}
    specs = {k: lane.res_spec(k, *nets[k], **({"reverse": True} if k == "rdb" else {})) for k in stems}
    cols = passives.plan_series(specs, pattern)
    if up:
        cols = [dict(c, bot=c["top"], top=c["bot"]) for c in cols]
    return passives.res_array(b, inst, cols, ll, "VSS")


def _mir_n(b, ll):
    m, s = DT["mbn"], DT["mbs"]
    return leaves.mirror_interdig(b, "mbn", "n", [dict(sym="R", nf=m.nf, gate="VBN", drn="VBN"), dict(sym="S", nf=s.nf, gate="VBN", drn="VBP")],
                                  S="VSS", rail="VSS", ll=ll, Wf=m.Wf, L=m.L, gate_exit="E")


def _mir_p(b, ll):
    m, u = DT["mbp"], DT["mb2p"]
    return leaves.mirror_interdig(b, "mbp", "p", [dict(sym="R", nf=m.nf, gate="VBP", drn="VBP"), dict(sym="U", nf=u.nf, gate="VBP", drn="VB2")],
                                  S="VDD", rail="VDD", ll=ll, Wf=m.Wf, L=m.L, gate_exit="E")


def _cap(b, ll):
    c = DT.raw["cap_vref"]
    return passives.nfet_cap(b, "cvref", c["c_width_um"], c["c_length_um"], ll, "VREF", "VSS")


# the west leaves stand against the corridor (VSS spine): their gates leave to the EAST, into the free channels
BUILD = {
    "ra1": lambda b, ll: _arr(("rb", "rf"), ["rb"] * 4 + ["rf"] * 2, False, b, "ra1", ll),
    "ra2": lambda b, ll: _arr(("rdt", "rdb"), ["rdt", "rdb", "rdb", "rdt", "rdt", "rdb", "rdb", "rdt"], True, b, "ra2", ll),
    "mir_n": _mir_n, "mir_p": _mir_p, "cvref": _cap,
    "msw": lambda b, ll: leaves.single(b, "msw", DT["msw"], ll, gate="enb", drn="nrb", src="VDD", rail="VDD", gate_exit="E"),
    "mpu_p": lambda b, ll: leaves.single(b, "mpu_p", DT["mpu_p"], ll, gate="EN", drn="VBP", src="VDD", rail="VDD", gate_exit="E"),
    "men_p": lambda b, ll: leaves.single(b, "men_p", DT["men_p"], ll, gate="EN", drn="enb", src="VDD", rail="VDD", gate_exit="E"),
    "men_n": lambda b, ll: leaves.single(b, "men_n", DT["men_n"], ll, gate="EN", drn="enb", src="VSS", rail="VSS", m1_ring_regions=True,
                                         gate_exit="E", dummies=0),
    "mb2": lambda b, ll: leaves.single(b, "mb2", DT["mb2"], ll, gate="VB2", drn="VB2", src="vf", rail="VSS", gate_exit="E"),
    "mvs": lambda b, ll: leaves.single(b, "mvs", DT["mvs"], ll, gate="EN", drn="nmid", src="VSS", rail="VSS", gate_exit="E"),
    "mpd_n": lambda b, ll: leaves.single(b, "mpd_n", DT["mpd_n"], ll, gate="enb", drn="VBN", src="VSS", rail="VSS", gate_exit="E"),
    "mpd_2": lambda b, ll: leaves.single(b, "mpd_2", DT["mpd_2"], ll, gate="enb", drn="VB2", src="VSS", rail="VSS", gate_exit="E"),
}
_SIZE = {}


def size(name):
    if name not in _SIZE:
        lf = BUILD[name](Block("scratch"), (0.0, 0.0))
        _SIZE[name] = (snap(lf.bbox[2] - lf.bbox[0]), snap(lf.bbox[3] - lf.bbox[1]))
    return _SIZE[name]


# ----------------------------------------------------------------------------------------------------------- floorplan
def rows():
    """Strap rows: the lane's own (lane.stack) where the bias block has the same strap, B0 below the lane."""
    items, jtop = lane.stack()
    st = {it["name"]: it for it in items if it["kind"] == "strap"}
    j = {"B0": J_B0, "S1v": st["S1"]["j1"], "S2": st["S2"]["j1"], "S4": st["S4"]["j1"], "S6": st["S6"]["j1"], "S7": st["S7"]["j1"]}
    return j, lane.trunk_rows(items), jtop


def strap_y(j1):
    return snap((j1 + 1.5) * PITCH)


def placement():
    """Lower-left corner of every leaf.  Bands: a leaf sits 2.3 um from the strap it ties to (the lane's 3 track rows), the
    Vref capacitor 1.4 um above S4 (its band is 27.3 um for a 24.12 um leaf)."""
    j, _, _ = rows()
    top = {k: strap_y(v) + 1.25 for k, v in j.items()}       # strap top edge
    bot = {k: strap_y(v) - 1.25 for k, v in j.items()}       # strap bottom edge
    w = {k: size(k)[0] for k in BUILD}
    h = {k: size(k)[1] for k in BUILD}
    P = {}
    # band B0 .. S2: MBN : MBS on B0 (east), RRB / RRF under S2 (east); the west part is split by S1v
    P["mir_n"] = (X_R - w["mir_n"], top["B0"] + 2.3)
    P["ra1"] = (X_R - w["ra1"], bot["S2"] - 2.3 - h["ra1"])
    P["men_n"] = (X_L, top["B0"] + 2.3)
    P["mb2"] = (X_L + w["men_n"] + 3.0, top["B0"] + 2.3)
    P["msw"] = (X_L, bot["S1v"] - 2.3 - h["msw"])
    P["men_p"] = (X_L, top["S1v"] + 2.3)
    P["mpu_p"] = (X_L + w["men_p"] + 3.0, top["S1v"] + 2.3)
    # band S2 .. S4: RRDT / RRDB under S4 (terminals up), mvs on S2 and mpd_2 under S4 at the west
    P["ra2"] = (X_R - w["ra2"], bot["S4"] - 2.3 - h["ra2"])
    P["mvs"] = (X_L, top["S2"] + 2.3)
    P["mpd_2"] = (X_L, bot["S4"] - 2.3 - h["mpd_2"])
    # band S4 .. S6: the Vref capacitor (east), mpd_n on S4 (west)
    P["cvref"] = (X_R - w["cvref"], top["S4"] + 1.4)
    P["mpd_n"] = (X_L, top["S4"] + 2.3)
    # band S6 .. S7: MBP : MB2P under S7 (east)
    P["mir_p"] = (X_R - w["mir_p"], bot["S7"] - 2.3 - h["mir_p"])
    return {k: (snap(x), snap(y)) for k, (x, y) in P.items()}


TIES = {"B0": ["mir_n", "men_n", "mb2"], "S1v": ["msw", "men_p", "mpu_p"], "S2": ["ra1", "mvs", "ra2"],
        "S4": ["mpd_2", "mpd_n", "cvref"], "S7": ["mir_p"]}


class Bias:
    pass


def build(stage="route", name=CELL):
    blk = Block(name)
    B = Bias()
    B.blk, B.leaf = blk, {}
    j, trows, jtop = rows()
    B.j, B.trunk_rows = j, trows
    B.y1, B.y2 = snap((J_B0 - 1) * PITCH - PITCH / 2), snap(jtop * PITCH - PITCH / 2)
    B.height = snap(B.y2 - B.y1)
    for k, ll in placement().items():
        B.leaf[k] = BUILD[k](blk, ll)
    lv = B.leaf
    # ---- power
    pp = B.pp = PowerPlan(blk, 0.0, W_B)
    S = B.strap = {k: pp.strap(("VDD" if k == "S7" else "VSS"), strap_y(v), name=k) for k, v in j.items() if k != "S1v"}
    pw = B.pp_west = PowerPlan(blk, 0.0, X_S1V)
    S["S1v"] = pw.strap("VDD", strap_y(j["S1v"]), name="S1v")
    pp.spine("VSS", SPINE_X)
    for sname, names in TIES.items():
        plan = pw if sname == "S1v" else pp
        for nm in names:
            plan.ring_tie(lv[nm], S[sname])
    # ---- router: grid on the lane's, west corridor closed to signals except the pins
    R = B.R = Router(blk, (1.0, B.y1, W_B, B.y2))
    for lf in lv.values():
        R.close(lf.bbox)
    for k, s in S.items():
        if k != "S1v":                    # S1v is joined to the VDD tree by a route (see below), so it is not adopted yet
            R.adopt(s["net"], L3, s["x1"], s["y"] - s["w"] / 2, s["x2"], s["y"] + s["w"] / 2)
    B.pins = {}
    for net, row in trows.items():        # outputs (and EN) on the west edge at the lane's trunk rows
        R.trunk(net, row, 0.0, 1.6)
        B.pins[net] = row
    if stage == "place":
        return B

    def hp(key, net, kind, sides=None):
        ps = lv[key].port(net, "m3", kind)
        if len(ps) != 1:
            raise ValueError(f"{key}: {len(ps)} ports of {net} / {kind}")
        return R.hport(ps[0], lv[key].bbox, sides)

    def vp(key, net, kind="term", **kw):
        ps = lv[key].port(net, "m3", kind)
        if len(ps) != 1:
            raise ValueError(f"{key}: {len(ps)} ports of {net} / {kind}")
        return R.vport(ps[0], lv[key].bbox, **kw)

    # ---- rails.  S1v first joins the VDD tree (S7) by a route, so the cell's VDD is one net on its own too; then it is adopted
    s1v = S["S1v"]
    R.connect("VDD", [R.pin(R.col_ge(X_L + 0.7), R.row_ge(s1v["y"]), L3)])
    R.adopt("VDD", L3, s1v["x1"], s1v["y"] - s1v["w"] / 2, s1v["x2"], s1v["y"] + s1v["w"] / 2)
    for key in ("mir_n", "cvref"):
        R.connect("VSS", [hp(key, "VSS", "bar")])
    for key in ("mvs", "mpd_n", "mpd_2"):
        R.connect("VSS", [hp(key, "VSS", "bar")])
    for key in ("msw", "men_p", "mpu_p", "mir_p"):
        R.connect("VDD", [hp(key, "VDD", "bar")])
    if stage == "rails":
        return B
    # ---- signals: short local nets first, then the outputs, then the enable nets.  Diode-connected devices (MBN, MBP, MB2)
    #      join gate and drain inside the leaf, so only their drain bar is a terminal.
    R.connect("nrb", [vp("ra1", "nrb"), hp("msw", "nrb", "bar")])
    R.connect("vf", [vp("ra1", "vf"), hp("mb2", "vf", "bar")])
    ra2_vref = lv["ra2"].port("VREF", "m3", "bar")[0]
    R.connect("nmid", [vp("ra2", "nmid"), hp("mvs", "nmid", "bar")])
    R.connect("VREF", [R.vport(ra2_vref, lv["ra2"].bbox, need_via=True, x=(ra2_vref.rect[0] + ra2_vref.rect[2]) / 2),
                       hp("cvref", "VREF", "gate")])
    R.connect("VDD", [vp("ra2", "VDD")])
    R.connect("VBN", [vp("ra1", "VBN"), hp("mir_n", "VBN", "bar"), hp("mpd_n", "VBN", "bar")])
    R.connect("VBP", [hp("mir_n", "VBP", "bar"), hp("mir_p", "VBP", "bar"), hp("mpu_p", "VBP", "bar")])
    R.connect("VB2", [hp("mir_p", "VB2", "bar"), hp("mb2", "VB2", "bar"), hp("mpd_2", "VB2", "bar")])
    R.connect("enb", [hp("men_n", "enb", "bar"), hp("men_p", "enb", "bar"), hp("msw", "enb", "gate"), hp("mpd_2", "enb", "gate"),
                      hp("mpd_n", "enb", "gate")])
    R.connect("EN", [hp("men_n", "EN", "gate"), hp("men_p", "EN", "gate"), hp("mpu_p", "EN", "gate"), hp("mvs", "EN", "gate")])
    # ---- pins: the five lane nets on the west edge, VDD on S7, VSS on S2 (both straps reach the west edge)
    for net, row in B.pins.items():
        blk.add_pin(net, "m3", 0.3, R.Y(row))
    blk.add_pin("VDD", "m3", W_B / 2, S["S7"]["y"])
    blk.add_pin("VSS", "m3", W_B / 2, S["S2"]["y"])
    return B


def schematic(B, name=CELL, dummies=True):
    """Flat LVS schematic: subckt lvds_bias of the reference flattened by name, plus the layout's dummies (MOS and the dummy
    columns of both resistor arrays)."""
    return lane.flat_schematic(B, "lvds_bias", ("ra1", "ra2"), name, dummies)


if __name__ == "__main__":                 # host dry run: python3 layout/bias/bias.py [place|rails|route]
    st = sys.argv[1] if len(sys.argv) > 1 else "place"
    B = build(st)
    print("bias box", W_B, "x", B.height, "y", B.y1, B.y2, "shapes", len(B.blk.shapes))
    if st == "place":
        for k, lf in B.leaf.items():
            print("  %-6s x %6.2f..%6.2f  y %7.2f..%7.2f" % (k, lf.bbox[0], lf.bbox[2], lf.bbox[1], lf.bbox[3]))
    else:
        for n, s in B.R.summary().items():
            print("   %-5s" % n, s)
        if st == "route":
            sch = schematic(B)
            print("schematic lines", len(sch.splitlines()), B.schem_counts)
