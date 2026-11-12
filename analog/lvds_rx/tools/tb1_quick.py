#!/usr/bin/env python3
"""tb1_quick.py -- iteration helper for sizing changes (T5): run TB1 on a handful of corners and print, per corner, the smallest
saturation margin (mV) of the stage-1 devices that matter plus the worst gm/ID and VGS comparison errors.

    tools/cx python3 tools/tb1_quick.py [corner ...]     (corner = proc:temp:vdd[:res=res_ff]; default: the 8 corners that failed the first full run)

It writes into sim/tb1_op/results/tb1_op (the gate bench's own folder); `make full` overwrites it.
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "sim"))
from harness import runner  # noqa: E402

DEFAULT = ["ff:125:3.3", "ff:125:3.6", "ff:125:3.0", "tt:125:3.6", "ff:27:3.0", "ff:27:3.6", "fs:125:3.0", "sf:125:3.6",
           "ss:125:3.0", "ss:125:3.0:res=res_ff", "ff:-40:3.6", "tt:27:3.3"]
GROUPS = ("mp1", "mn1", "m3", "mnt", "mpt", "mt2", "ms")


def main():
    corners = sys.argv[1:] or DEFAULT
    spec = os.path.join(ROOT, "sim", "tb1_op", "tb1_op.json")
    runner.run_spec(spec, jobs=6, only_corners=corners, verbose=False)
    out = os.path.join(ROOT, "sim", "tb1_op", "results", "tb1_op")
    res = json.load(open(os.path.join(out, "results.json")))
    by = {}
    for r in res["runs"]:
        c = r["corner"]
        d = by.setdefault(c, {"mg": {}, "gmid": 0.0, "vgs": 0.0, "head": 9.0, "n": 0})
        d["n"] += 1
        m = r["metrics"]
        d["gmid"] = max(d["gmid"], abs(m.get("gmid_err", 0)))
        d["vgs"] = max(d["vgs"], abs(m.get("vgs_err_v", 0)))
        d["head"] = min(d["head"], m.get("min_headroom_v", 9))
        lc = json.load(open(os.path.join(out, r["run_dir"], "lutcmp.json")))
        for row in lc["devices"].values():
            if "mg" not in row or row.get("id", 0) < 1e-6:
                continue
            s = row["stem"]
            if s in GROUPS:
                d["mg"][s] = min(d["mg"].get(s, 9), row["mg"])
    print("%-26s %6s %s  | gmid_err vgs_err(mV) head(mV)" % ("corner", "n", " ".join("%6s" % g for g in GROUPS)))
    for c, d in by.items():
        print("%-26s %6d %s  | %.3f %.1f %.1f" % (c, d["n"], " ".join("%6.0f" % (1e3 * d["mg"].get(g, float("nan"))) for g in GROUPS),
                                                   d["gmid"], 1e3 * d["vgs"], 1e3 * d["head"]))


if __name__ == "__main__":
    main()
