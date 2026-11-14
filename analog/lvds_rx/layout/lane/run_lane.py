#!/usr/bin/env python3
"""run_lane.py [--stage place|rails|route] [--nok]   build the lane and check it.  Run INSIDE the container:

  docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx python3 layout/lane/run_lane.py [--stage S] [--nok]

  --stage place | rails   partial build (cell lane_<stage>): Magic build, Magic DRC (.mag and GDS read-back), KLayout foundry deck
                          main + antenna, picture.  No LVS (the nets are still open).  A fast filter while the lane is being built.
  --stage route (default) the finished lane, cell lvds_lane: everything check.run_cell does (self-check, DRC, strict LVS, finger
                          read-back, negative controls) plus the lane-only checks added in piece F.
  --nok                   skip the KLayout deck (fast loop; never a sign-off)
Work files: .scratch/t9/work/<cell>/.  Results: layout/lane/results/.
"""
import hashlib
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LAYOUT = os.path.dirname(HERE)
ROOT = os.path.dirname(LAYOUT)
sys.path.insert(0, LAYOUT)
sys.path.insert(0, HERE)

from lib import check                                 # noqa: E402
import lane                                           # noqa: E402

RESULTS = os.path.join(HERE, "results")
OUT = os.path.join(ROOT, ".scratch", "t9", "work")
CO6 = ("(CO.6)",)       # Magic CO.6 is stricter than the foundry deck on the trimmed L = 0.28 contact bars (see leaves.mos_row)
REF = "netlist/lvds_rx_lvs_ref.spice"
FROZEN = "sizing/FROZEN.md"


def frozen_sha(rel):
    """The sha256 that sizing/FROZEN.md records for `rel` (None if the file is not in its table)."""
    for line in open(os.path.join(ROOT, FROZEN)):
        m = re.match(r"\|\s*`([^`]+)`\s*\|\s*([0-9a-f]{64})\s*\|", line)
        if m and m.group(1) == rel:
            return m.group(2)
    return None


def reference_lvs(L, wd):
    """PLAN_V2 6.4 step 5 against the frozen file: the flat schematic WITHOUT the layout's dummies, compared by Netgen (same
    strict criteria) with subckt lvds_lane of netlist/lvds_rx_lvs_ref.spice; Netgen flattens the reference's sub-blocks
    (lvds_esd2, lvds_pre, lvds_hyst, lvds_out).  With the layout run (layout == flat + dummies) this gives
    layout == reference + the layout's dummies.  The reference file's sha256 must equal the one in sizing/FROZEN.md."""
    flat = os.path.join(wd, "flat_nodummy.spice")
    with open(flat, "w") as f:
        f.write(lane.schematic(L, dummies=False))
    path = os.path.join(ROOT, REF)
    sha = hashlib.sha256(open(path, "rb").read()).hexdigest()
    want = frozen_sha(REF)
    lv = check.netgen_lvs(lane.CELL, flat, open(path).read(), wd, "reference")
    flattened = re.findall(r"Flattening unmatched subcell (\S+)", open(lv["out"]).read()) if os.path.exists(lv["out"]) else []
    return dict(ok=bool(lv["clean"] and sha == want), reference=REF, sha256=sha, frozen_sha256=want, frozen_sha256_ok=(sha == want),
                flattened_subcells=sorted(set(flattened)), **lv)


def verdict(r):
    st = r["steps"]
    r["all_ok"] = bool(st) and all(s.get("ok", False) for s in st.values())
    r["verdict"] = "PASS" if r["all_ok"] else "FAIL: " + ", ".join(k for k, s in st.items() if not s.get("ok", False))


def partial(stage, nok):
    name = f"lane_{stage}"
    t0 = time.time()
    L = lane.build(stage, name=name)
    blk = L.blk
    wd = os.path.join(OUT, name)
    os.makedirs(RESULTS, exist_ok=True)
    res = dict(cell=name, stage=stage, steps={}, started=time.strftime("%Y-%m-%d %H:%M:%S"),
               box_um=[2 * lane.HALF, L.height], python_build_s=round(time.time() - t0, 1))
    b = check.build(blk, wd)
    res["steps"]["build"] = dict(ok=not b["errors"] and not b["genbbox_mismatch"], errors=b["errors"], genbbox_mismatch=b["genbbox_mismatch"])
    gds = b["gds"]
    if os.path.exists(gds):
        res["steps"]["metal_cap"] = check.metal_cap(blk, gds)
        d1 = check.magic_drc(name, wd, wd, "mag", CO6)
        d2 = check.magic_drc(name, gds, wd, "gds", CO6)
        res["steps"]["magic_drc"] = dict(ok=(d1["effective"] == 0 and d2["effective"] == 0), mag=d1, gds_readback=d2, allow=list(CO6))
        if not nok:
            k = check.klayout_drc(gds, name, os.path.join(wd, "klayout"))
            k["ok"] = bool(k["dbu_ok"] and k["main"] == 0 and k.get("antenna") == 0 and k["main_lyrdb_files"] > 0)
            res["steps"]["klayout"] = k
        png = os.path.join(RESULTS, name + ".png")
        check.sh(["python3", os.path.join(LAYOUT, "lib", "render.py"), gds, name, png])
        res["steps"]["render"] = dict(ok=os.path.exists(png))
    res["power"] = L.pp.report(macro_len=2 * 200.0 + 2 * lane.HALF)
    res["all_ok"] = all(s.get("ok", False) for s in res["steps"].values())
    res["wall_s"] = round(time.time() - t0, 1)
    with open(os.path.join(RESULTS, name + ".json"), "w") as f:
        json.dump(res, f, indent=1, default=str)
    print(name, "OK" if res["all_ok"] else "NOT OK", f"{res['wall_s']} s")
    for k, s in res["steps"].items():
        print("   %-10s %s %s" % (k, "ok" if s.get("ok") else "NOT OK", "" if s.get("ok") else str(s)[:1500]))
    return res["all_ok"]


def full(nok):
    """The finished lane: every step of check.run_cell (PLAN_V2 6.4 steps 1, 2, 3, 5)."""
    t0 = time.time()
    L = lane.build("route")
    sch = lane.schematic(L)
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, lane.CELL + ".spice"), "w") as f:
        f.write("* LVS schematic of the lane layout: subckt lvds_lane of netlist/lvds_rx_lvs_ref.spice flattened + the layout's dummy devices.\n"
                "* GENERATED by layout/lane/lane.py (schematic) -- do not edit by hand.\n" + sch)
    r = check.run_cell(L.blk, sch, OUT, RESULTS, klayout=not nok, cut_net="oa", cut_kind="route", magic_allow=CO6)
    r["python_build_s"] = round(time.time() - t0 - r["wall_s"], 1)
    # ---- lane-only checks (T9 piece F)
    wd = os.path.join(OUT, lane.CELL)
    gds = os.path.join(wd, lane.CELL + ".gds")
    r["steps"]["lvs_reference"] = reference_lvs(L, wd)
    r["steps"]["via_arrays"] = check.via_arrays(gds, lane.CELL, wd)
    verdict(r)
    r["wall_s"] = round(time.time() - t0, 1)
    r["box_um"] = [2 * lane.HALF, L.height]
    r["schematic"] = L.schem_counts
    r["routes"] = L.R.summary()
    r["power"] = L.pp.report(macro_len=2 * 200.0 + 2 * lane.HALF)
    r["klayout_skipped"] = bool(nok)
    with open(os.path.join(RESULTS, lane.CELL + ".json"), "w") as f:
        json.dump(r, f, indent=1, default=str)
    print(lane.CELL, r["verdict"], f"{r['wall_s']} s", "(KLayout deck skipped: not a sign-off)" if nok else "")
    for k, s in r["steps"].items():
        print("   %-16s %s %s" % (k, "ok" if s.get("ok") else "NOT OK", "" if s.get("ok") else str(s)[:1800]))
    return bool(r["all_ok"])


def main(args):
    nok = "--nok" in args
    stage = args[args.index("--stage") + 1] if "--stage" in args else "route"
    if stage != "route":
        return 0 if partial(stage, nok) else 1
    return 0 if full(nok) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
