"""ant_tests.py -- KLayout antenna check on a small gate WITH and WITHOUT the secondary-ESD cell attached (PLAN_V2 L10).

Both cells hold a small gate (W 2.0 x L 0.5 = 1.0 um2) driven through a long Metal3 wire (the
"input run" from the pad side), wire length LEN um in 28 um pieces (merged by Magic):
  t_ant_bare   gate net G = wire only, no diffusion on the net            -> antenna violations expected (check is live)
  t_ant_esd    gate net B = same wire + esd_cell (nd2ps cathode and pd2nw anode on B)  -> must be 0
Main DRC must be 0 in both.  Results: results/ant_esd_comparison.json (counts, rule names) and results/t_ant_*.png.
UNQUALIFIED: this shows the antenna deck sees the diodes, nothing about ESD robustness.
"""
import json
import os
import shutil

from lib import check, leaves, passives
from lib.block import Block
from lib.device_table import DeviceTable, Dev

DT = DeviceTable()
LEN = 700.0


def build_ant(name, with_esd):
    gdev = Dev("gate", "nfet_03v3", 2.0, 0.5, 1, 2.0)       # W 2.0 x L 0.5 = 1.0 um2 (the L 0.28 digital sizes need the digital generator)
    blk = Block(name)
    x0 = 0.0
    net = "B" if with_esd else "G"
    if with_esd:
        r, dh = DT.res["resd"], DT.dio["desd_h"]
        e = passives.esd_cell(blk, "esd", (0, 0), r["r_width_um"], r["r_length_um"], dh["w_um"], dh["l_um"])
        bport = [p for p in e.ports if p.net == "B"][0]
        x0 = e.bbox[2] + 6.0
        leaves.pin_ports(blk, e)
        ybus = (bport.rect[1] + bport.rect[3]) / 2
        xs = bport.rect[2]
    lg = leaves.single(blk, "mn", gdev, (x0 + LEN, 0), gate=net, drn="D", src="VSS", rail="VSS")
    gp = [p for p in lg.ports if p.net == net and p.owner.startswith("gate")][0]
    gx, gy = (gp.rect[0] + gp.rect[2]) / 2, (gp.rect[1] + gp.rect[3]) / 2
    if with_esd:
        # run: B port -> east along its own height -> up/down to the gate strap height -> gate port (exits west of the row)
        xv = gx - 4.0
        blk.hwire("m3", ybus, xs - 0.5, xv + 0.14, 0.28, net, "run")
        blk.vwire("m3", xv, ybus, gy, 0.28, net, "run")
        blk.hwire("m3", gy, xv - 0.14, gx, 0.28, net, "run")
        blk.add_pin(net, "m3", xs - 0.3, ybus)
    else:
        xa = gx - LEN
        blk.hwire("m3", gy, xa, gx, 0.28, net, "run")
        blk.add_pin(net, "m3", xa + 0.2, gy)
    for n in ("D", "VSS"):
        pr = [p for p in lg.ports if p.net == n]
        if pr:
            x1, y1, x2, y2 = pr[0].rect
            blk.add_pin(n, pr[0].layer, (x1 + x2) / 2 if pr[0].owner != "bar" else x1 + 0.2, (y1 + y2) / 2)
    return blk


def run_ant(outdir, results_dir, klayout=True):
    out = {}
    for name, esd in (("t_ant_bare", False), ("t_ant_esd", True)):
        blk = build_ant(name, esd)
        wd = os.path.join(outdir, name)
        b = check.build(blk, wd)
        gds = b["gds"]
        res = dict(build_errors=b["errors"], wire_um=LEN)
        if klayout and os.path.exists(gds):
            k = check.klayout_drc(gds, name, os.path.join(wd, "klayout"))
            res.update(main=k["main"], antenna=k["antenna"], antenna_rules=k["antenna_rules"], main_rules=k["main_rules"],
                       dbu_ok=k["dbu_ok"], lyrdb=(k["main_lyrdb_files"], k["antenna_lyrdb_files"]))
        if os.path.exists(gds):
            shutil.copy(gds, os.path.join(results_dir, name + ".gds"))
            check.sh(["python3", os.path.join(check.LIB, "render.py"), gds, name, os.path.join(results_dir, name + ".png")])
        out[name] = res
    if klayout:
        bare, esd = out["t_ant_bare"], out["t_ant_esd"]
        out["ok"] = bool(bare["main"] == 0 and esd["main"] == 0 and bare["antenna"] > 0 and esd["antenna"] == 0
                         and bare["dbu_ok"] and esd["dbu_ok"] and min(bare["lyrdb"] + esd["lyrdb"]) > 0)
    else:
        out["ok"] = False
        out["note"] = "--nok: KLayout skipped"
    with open(os.path.join(results_dir, "ant_esd_comparison.json"), "w") as f:
        json.dump(out, f, indent=1)
    return out
