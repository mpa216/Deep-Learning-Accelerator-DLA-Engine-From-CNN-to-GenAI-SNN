#!/usr/bin/env python3
"""run_macro.py [--stage drc] [--nok]   build the macro lvds_rx_x3 (three lanes + bias block as subcells) and check it.
Run INSIDE the container:

  docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx python3 layout/macro/run_macro.py [--stage drc] [--nok]

Steps (PLAN_V2 6.4 on the macro): build (lane, bias block, macro in ONE work directory, so Magic finds the subcells there);
Magic DRC on the .mag and on the GDS read back; KLayout foundry deck main + antenna (flat run over the hierarchy);
check_via_arrays.py; then (not with --stage drc) hierarchical extraction and strict Netgen LVS against the hierarchical
schematic (lvds_lane and lvds_bias with their dummies + lvds_rx_x3 of the reference file), the top level also against the
frozen reference file, negative controls (wrong W, a cut fill between lanes, a top-level bridge, a DRC sliver), antenna
without the ESD diodes, picture.  --nok skips the KLayout deck (never a sign-off).
Work files: .scratch/t10/work/lvds_rx_x3/.  Results: layout/macro/results/.
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LAYOUT = os.path.dirname(HERE)
ROOT = os.path.dirname(LAYOUT)
sys.path.insert(0, LAYOUT)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(LAYOUT, "lane"))
sys.path.insert(0, os.path.join(LAYOUT, "bias"))

from lib import check                                 # noqa: E402
from lib.selfcheck import parse_ext_devices           # noqa: E402
import lane                                            # noqa: E402
import bias                                            # noqa: E402
import macro                                           # noqa: E402
import run_lane                                        # noqa: E402

RESULTS = os.path.join(HERE, "results")
OUT = os.path.join(ROOT, ".scratch", "t10", "work")
CO6 = run_lane.CO6


def run(stage, nok):
    t0 = time.time()
    L, B = lane.build("route"), bias.build("route")
    M = macro.build(L, B)
    name = macro.CELL
    wd = os.path.join(OUT, name)
    os.makedirs(RESULTS, exist_ok=True)
    r = dict(cell=name, steps={}, started=time.strftime("%Y-%m-%d %H:%M:%S"), fixed_bbox_um=list(M.fixed_bbox), core_um=list(M.core),
             y0=M.y0, instances=M.blk.instances, python_build_s=round(time.time() - t0, 1))
    # ---- 1 build: subcells first (the first build cleans the directory), then the macro
    bl = check.build(L.blk, wd)
    bb = check.build(B.blk, wd, clean=False)
    bm = check.build(M.blk, wd, clean=False)
    errs = bl["errors"] + bb["errors"] + bm["errors"]
    r["steps"]["build"] = dict(ok=not errs and not (bl["genbbox_mismatch"] or bb["genbbox_mismatch"]), errors=errs[:5])
    gds = bm["gds"]
    if not os.path.exists(gds):
        r["verdict"] = "FAIL (no GDS)"
        return _write(r, t0)
    r["steps"]["metal_cap"] = check.metal_cap(M.blk, gds)
    # ---- 2 Magic DRC (the .mag of all three cells sit in wd)
    d1 = check.magic_drc(name, wd, wd, "mag", CO6, flat=True)
    d2 = check.magic_drc(name, gds, wd, "gds", CO6, flat=True)
    r["steps"]["magic_drc"] = dict(ok=(d1["effective"] == 0 and d2["effective"] == 0), mag=d1, gds_readback=d2, allow=list(CO6))
    # ---- 3 KLayout foundry deck, 4 via arrays
    if not nok:
        k = check.klayout_drc(gds, name, os.path.join(wd, "klayout"))
        k["ok"] = bool(k["dbu_ok"] and k["main"] == 0 and k.get("antenna") == 0 and k["main_lyrdb_files"] > 0 and k.get("antenna_lyrdb_files", 0) > 0)
        r["steps"]["klayout"] = k
    r["steps"]["via_arrays"] = check.via_arrays(gds, name, wd)
    png = os.path.join(RESULTS, name + ".png")
    check.sh(["python3", os.path.join(LAYOUT, "lib", "render.py"), gds, name, png])
    r["steps"]["render"] = dict(ok=os.path.exists(png))
    if stage == "drc":
        return _write(r, t0)
    # ---- 5 LVS (hierarchical), negative controls, antenna without ESD: piece C
    return _write(r, t0)


def _write(r, t0):
    run_lane.verdict(r)
    r["wall_s"] = round(time.time() - t0, 1)
    with open(os.path.join(RESULTS, r["cell"] + ".json"), "w") as f:
        json.dump(r, f, indent=1, default=str)
    import shutil
    g = os.path.join(OUT, r["cell"], r["cell"] + ".gds")
    if os.path.exists(g):
        shutil.copy(g, os.path.join(RESULTS, r["cell"] + ".gds"))
    print(r["cell"], r["verdict"], f"{r['wall_s']} s")
    for k, s in r["steps"].items():
        print("   %-16s %s %s" % (k, "ok" if s.get("ok") else "NOT OK", "" if s.get("ok") else str(s)[:1800]))
    return bool(r["all_ok"])


def main(args):
    nok = "--nok" in args
    stage = args[args.index("--stage") + 1] if "--stage" in args else "full"
    return 0 if run(stage, nok) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
