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


CELLS4 = {"t_esd_mirror": t_esd_mirror, "t_power": t_power}
