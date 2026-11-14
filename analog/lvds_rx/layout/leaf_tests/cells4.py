"""cells4.py -- T9 leaf test cells for the library pieces the lane needs on top of T8: mirrored generation (lib.xform),
power straps (lib.power) and the grid router (lib.route).  Same contract as cells2 / cells3: builders return
(block, schematic_text, cut_net, run_opts); run_opts may carry `post`, a function(result_dict, work_dir) -> step dict that
run_all.py stores as the step "post".

  t_esd_mirror   the secondary-ESD cell generated through xform.MirrorX; must pass the same checks as t_esd AND its GDS,
                 mirrored back, must equal the GDS of t_esd on every layer (XOR empty)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from lib import leaves, passives                      # noqa: E402
from lib.block import Block                           # noqa: E402
from lib.xform import MirrorX                         # noqa: E402
from cells2 import DT, subckt, esd_args, esd_lines    # noqa: E402

RESULTS = os.path.join(HERE, "results")


def mirror_xor(gds_a, gds_b, axis_a=0.0):
    """XOR of layout A mirrored about x = axis_a against layout B, per layer.  Returns dict(ok, layers, differing)."""
    import klayout.db as db
    la, lb = db.Layout(), db.Layout()
    la.read(gds_a)
    lb.read(gds_b)
    ta, tb = la.top_cell(), lb.top_cell()
    keys = sorted({(la.get_info(i).layer, la.get_info(i).datatype) for i in la.layer_indexes()} |
                  {(lb.get_info(i).layer, lb.get_info(i).datatype) for i in lb.layer_indexes()})
    shift = int(round(2 * axis_a / la.dbu))
    bad = {}
    n = 0
    for (l, d) in keys:
        ia, ib = la.find_layer(l, d), lb.find_layer(l, d)
        ra = db.Region(ta.begin_shapes_rec(ia)) if ia is not None else db.Region()
        rb = db.Region(tb.begin_shapes_rec(ib)) if ib is not None else db.Region()
        if ra.is_empty() and rb.is_empty():
            continue
        n += 1
        x = ra.merged().transformed(db.Trans(db.Trans.M90, shift, 0)) ^ rb.merged()
        if not x.is_empty():
            bad[f"{l}/{d}"] = round(x.area() * la.dbu * la.dbu, 4)
    return dict(ok=(not bad and n > 0), layers=n, differing=bad)


def t_esd_mirror():
    r, dh, dl = esd_args()
    blk = Block("t_esd_mirror")
    m = MirrorX(blk, 0.0)
    leaf = m.leaf(passives.esd_cell(m, "esd", (0, 0), r["r_width_um"], r["r_length_um"], dh["w_um"], dh["l_um"]))
    leaves.pin_ports(blk, leaf)
    cx = -(leaf.info["rwell"][2] + leaf.info["xd1"]) / 2          # between the resistor and the first diode plate (mirrored)

    def post(res, wd):
        ref = os.path.join(RESULTS, "t_esd.gds")
        if not os.path.exists(ref):
            return dict(ok=False, error="results/t_esd.gds missing: run t_esd first")
        out = mirror_xor(os.path.join(wd, "t_esd_mirror.gds"), ref, 0.0)
        out["what"] = "GDS mirrored about x = 0 XOR results/t_esd.gds, all layers"
        out["ports"] = {p.net: (p.dirs, [round(v, 3) for v in p.rect]) for p in leaf.ports}
        return out

    return blk, subckt("t_esd_mirror", blk, esd_lines(r, dh, dl)), "B", dict(leaf=leaf, cut_x=cx, post=post)


def t_power():
    """One NMOS row (mnt) between two VSS straps: ring tied to both, the two straps tied by a Metal2 spine.  Checks the strap,
    spine, via-array and ring-tie geometry of lib.power against the foundry deck and LVS, and the planner's report."""
    from lib import alloc
    from lib.power import PowerPlan
    dev = DT["mnt"]
    blk = Block("t_power")
    lf = leaves.single(blk, "mnt", dev, (0, 5.0), gate="VBN", drn="TN", src="VSS", rail="VSS")
    pp = PowerPlan(blk, -3.0, lf.bbox[2] + 3.0)
    lo = pp.strap("VSS", lf.bbox[1] - 2.5)
    hi = pp.strap("VSS", lf.bbox[3] + 2.5)
    pp.ring_tie(lf, lo)
    pp.ring_tie(lf, hi)
    pp.spine("VSS", -1.8)
    pp.load(lo, 105.0, "mnt")
    blk.add_pin("VSS", "m3", pp.x1 + 1.0, lo["y"])
    al = alloc.Alloc(blk)
    al.pin_port("VBN", lf.port("VBN", "m3", "gate")[0])
    al.pin_port("TN", lf.port("TN", "m3", "bar")[0])
    lines = [DT.spice("MNT", dev, "TN", "VBN", "VSS", "VSS")]

    def post(res, wd):
        rep = pp.report(macro_len=542.0)
        return dict(ok=rep["ok"], report=rep)

    return blk, subckt(blk.name, blk, lines), "TN", dict(post=post)


def t_route():
    """The output chain (NAND2 + three inverters, as t_out_chain) in ONE row, N and P leaves side by side, between a VSS strap
    below and a VDD strap above, wired completely by lib.route (signals, rail hook-ups of the source bars, an edge-to-edge EN
    trunk, on-grid pins) with ring ties from lib.power.  The same devices as t_out_chain, so the schematic is the same."""
    from lib.power import PowerPlan
    from lib.route import Router, L2, L3
    blk = Block("t_route")
    nn, np_ = DT["nand_n"], DT["nand_p"]
    Y_N, Y_PTOP, GAP = 5.3, 14.3, 4.2
    N, P = {}, {}
    x = 0.0

    def place_p(builder, height):
        return builder(Y_PTOP - height)

    # heights of the P leaves are needed before placing them top-aligned: build each once on a scratch block
    def p_height(fn):
        lf = fn(Block("scratch"), 0.0, 0.0)
        return lf.bbox[3] - lf.bbox[1]

    def nand_p(b, xx, yy):
        return leaves.grouped_row(b, "nandp", "p", np_.Wf, np_.L,
                                  [dict(sym="P1", n=1, gate="d3", src="VDD", drn="nd", side="top", exit="W"),
                                   dict(sym="P2", n=1, gate="EN", src="VDD", drn="nd", side="bot", exit="E")], (xx, yy), rail="VDD")

    N["nand"] = leaves.stacked(blk, "nandn", nn, nn, (x, Y_N), dict(g_lo="EN", g_up="d3", src="VSS", mid="nm", drn="nd"), rail="VSS")
    x = N["nand"].bbox[2] + GAP
    P["nand"] = nand_p(blk, x, Y_PTOP - p_height(nand_p))
    x = P["nand"].bbox[2] + GAP
    prev = "nd"
    names = [("inv1", "i1"), ("inv2", "i2"), ("inv3", "OUT")]
    for stem, out in names:
        dn, dp = DT[stem + "_n"], DT[stem + "_p"]
        N[stem] = leaves.single(blk, stem + "n", dn, (x, Y_N), gate=prev, drn=out, src="VSS", rail="VSS")
        x = N[stem].bbox[2] + GAP

        def inv_p(b, xx, yy, dp=dp, stem=stem, prev=prev, out=out):
            return leaves.single(b, stem + "p", dp, (xx, yy), gate=prev, drn=out, src="VDD", rail="VDD")
        P[stem] = inv_p(blk, x, Y_PTOP - p_height(inv_p))
        x = P[stem].bbox[2] + GAP
        prev = out
    X1, X2 = -3.0, x - GAP + 3.0
    pp = PowerPlan(blk, X1, X2)
    vss = pp.strap("VSS", 1.75)
    vdd = pp.strap("VDD", 17.85)
    for lf in N.values():
        pp.ring_tie(lf, vss)
    for lf in P.values():
        pp.ring_tie(lf, vdd)
    pp.load(vss, 100.0, "chain (average, assumed)")
    pp.load(vdd, 100.0, "chain (average, assumed)")
    R = Router(blk, (X1, -0.5, X2, 19.4))
    for lf in list(N.values()) + list(P.values()):
        R.close(lf.bbox)
    R.adopt("VSS", L3, vss["x1"], vss["y"] - vss["w"] / 2, vss["x2"], vss["y"] + vss["w"] / 2)
    R.adopt("VDD", L3, vdd["x1"], vdd["y"] - vdd["w"] / 2, vdd["x2"], vdd["y"] + vdd["w"] / 2)

    def hp(lf, net, kind):
        return R.hport(lf.port(net, "m3", kind)[0], lf.bbox)

    for lf in N.values():
        R.connect("VSS", [hp(lf, "VSS", "bar")])
    for lf in P.values():
        R.connect("VDD", [hp(lf, "VDD", "bar")])
    R.trunk("EN", 22, X1, X2)
    R.connect("EN", [hp(N["nand"], "EN", "gate"), hp(P["nand"], "EN", "gate")])
    pd3 = (R.col_ge(X1 + 0.5), 6, L3)
    R.connect("d3", [R.pin(*pd3), hp(N["nand"], "d3", "gate"), hp(P["nand"], "d3", "gate")])
    R.connect("nd", [hp(N["nand"], "nd", "bar"), hp(P["nand"], "nd", "bar"), hp(N["inv1"], "nd", "gate"), hp(P["inv1"], "nd", "gate")])
    R.connect("i1", [hp(N["inv1"], "i1", "bar"), hp(P["inv1"], "i1", "bar"), hp(N["inv2"], "i1", "gate"), hp(P["inv2"], "i1", "gate")])
    R.connect("i2", [hp(N["inv2"], "i2", "bar"), hp(P["inv2"], "i2", "bar"), hp(N["inv3"], "i2", "gate"), hp(P["inv3"], "i2", "gate")])
    pout = (R.col_le(X2 - 0.5), 0, L2)
    R.connect("OUT", [hp(N["inv3"], "OUT", "bar"), hp(P["inv3"], "OUT", "bar"), R.pin(*pout)])
    blk.add_pin("d3", "m3", R.X(pd3[0]), R.Y(pd3[1]))
    blk.add_pin("OUT", "m2", R.X(pout[0]), R.Y(pout[1]))
    blk.add_pin("EN", "m3", X1 + 0.6, R.Y(22))
    blk.add_pin("VSS", "m3", X1 + 1.0, vss["y"])
    blk.add_pin("VDD", "m3", X1 + 1.0, vdd["y"])
    lines = [DT.spice("MNANDN1", nn, "nd", "d3", "nm", "VSS"), DT.spice("MNANDN2", nn, "nm", "EN", "VSS", "VSS"),
             DT.spice("MNANDP1", np_, "nd", "d3", "VDD", "VDD"), DT.spice("MNANDP2", np_, "nd", "EN", "VDD", "VDD")]
    prev = "nd"
    for stem, out in names:
        dn, dp = DT[stem + "_n"], DT[stem + "_p"]
        lines += [DT.spice("M" + stem.upper() + "N", dn, out, prev, "VSS", "VSS"), DT.spice("M" + stem.upper() + "P", dp, out, prev, "VDD", "VDD")]
        prev = out

    def post(res, wd):
        rep = pp.report(macro_len=542.0)
        return dict(ok=rep["ok"], routes=R.summary(), power=rep["straps"])

    return blk, subckt(blk.name, blk, lines), "nd", dict(magic_allow=("(CO.6)",), post=post, cut_kind="route")


CELLS4 = {"t_esd_mirror": t_esd_mirror, "t_power": t_power, "t_route": t_route}
