#!/usr/bin/env python3
"""run_all.py [cell ...] [--nok]   rebuild and fully re-check EVERY leaf of the device table in one command; writes
layout/leaf_tests/results/summary.md.  Run inside the container:

  docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx python3 layout/leaf_tests/run_all.py [names] [--nok]

Cells = the T8 part 1 cells (run_leaf_tests.CELLS / FAULTS) + the part 2 cells (cells2.CELLS2) + the antenna with / without ESD
comparison (ant_tests).  Sizes come from layout/device_table.json (re-run after a sizing freeze).  `--nok` skips the KLayout deck
(5 s loop); a summary written with --nok says so and is not a sign-off.  Work files: .scratch/t8/work/<cell>/.
Per cell: self-check (extraction == request), Magic DRC, KLayout foundry deck main + antenna at 0.001 um DBU, strict Netgen LVS,
finger read-back, negative controls, PNG; faulty cells must FAIL LVS and be located.
"""
import glob
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import run_leaf_tests as part1                      # noqa: E402
import cells2                                        # noqa: E402
import cells3                                        # noqa: E402
import ant_tests                                     # noqa: E402
from lib import check                                # noqa: E402

ALL2 = {**cells2.CELLS2, **cells3.CELLS3}
RESULTS = part1.RESULTS
OUT = part1.OUT


def gds_info(path):
    import klayout.db as db
    ly = db.Layout()
    ly.read(path)
    bb = ly.top_cell().dbbox()
    return round(bb.width(), 2), round(bb.height(), 2)


def run_one(name, nok):
    """Returns the result dict (and prints one line)."""
    if name in part1.FAULTS:
        fault, exp = part1.FAULTS[name]
        blk, sch = part1.build_block(name, fault)
        f = blk.faults[0]
        r = check.run_fault_cell(blk, sch, OUT, RESULTS, dict(exp, at=f["at"], tol=2.5))
        print(name, r["verdict"], f"{r['wall_s']} s")
        return r
    if name in part1.CELLS:
        blk, schem, cut = part1.CELLS[name]()
        opts = {}
    else:
        blk, schem, cut, opts = ALL2[name]()
    leaf = opts.pop("leaf", None)
    if leaf is not None and leaf.info.get("kind") == "res_array":
        opts["res_cols"] = leaf.info["cols"]
    r = check.run_cell(blk, schem, OUT, RESULTS, klayout=not nok, cut_net=cut, **opts)
    g = os.path.join(RESULTS, name + ".gds")
    if os.path.exists(g):
        r["bbox_um"] = gds_info(g)
        with open(os.path.join(RESULTS, name + ".json"), "w") as f:
            json.dump(r, f, indent=1, default=str)
    print(name, r["verdict"], f"{r['wall_s']} s", r.get("bbox_um"))
    for k, s in r["steps"].items():
        if not s.get("ok"):
            print("    NOT OK:", k, str(s)[:300])
    return r


def main(args):
    nok = "--nok" in args
    names = [a for a in args if not a.startswith("--")]
    everything = list(part1.CELLS) + list(part1.FAULTS) + list(ALL2) + ["ant_esd"]
    full = not names
    names = names or everything
    ok = part1.alloc_selftest() if full else True
    results = {}
    for n in names:
        if n not in everything:
            print("unknown cell", n)
            ok = False
            continue
        if n == "ant_esd":
            r = ant_tests.run_ant(OUT, RESULTS, klayout=not nok)
            r["all_ok"] = r["ok"]
            print("ant_esd", "PASS" if r["ok"] else "FAIL", {k: (v.get("main"), v.get("antenna"), v.get("antenna_rules")) for k, v in r.items() if isinstance(v, dict)})
            results[n] = r
            ok &= r["ok"]
            continue
        r = run_one(n, nok)
        results[n] = r
        ok &= bool(r.get("all_ok"))
    print("ALL GREEN" if ok else "NOT GREEN")
    if full:
        import summarize2
        summarize2.write(nok=nok, ok=ok)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
