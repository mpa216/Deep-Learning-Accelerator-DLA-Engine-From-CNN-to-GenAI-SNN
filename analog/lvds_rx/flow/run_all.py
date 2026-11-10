#!/usr/bin/env python3
"""run_all.py -- the stage driver: harness runs -> gates -> report -> manifest (thin layer over sim/harness).

    python3 flow/run_all.py --tier smoke|full [--phases env,prelayout] [--only TB1,TB2] [--jobs 6]
                            [--stage sim|gates|report|all] [--dry-run]

For every gate of the selected phases that names a testbench spec the harness is run with the tier's corner set and
Monte Carlo N from spec/gates.yaml (`scope`); gates whose spec file does not exist yet are listed as pending and
evaluate to NOT_RUN.  Expected run counts are computed from gates.yaml, printed in --dry-run and checked by gates.py.
Exit code = gates.py exit code (0 only if every evaluated gate is PASS or NOT_APPLICABLE).
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402
import gates as G  # noqa: E402
import report as R  # noqa: E402
from harness import runner  # noqa: E402


def plan(tier, phases, only=None):
    gates_y = C.load_yaml("spec/gates.yaml")
    spec = C.load_yaml("spec/spec.yaml")
    rows = []
    for gid, g in gates_y["gates"].items():
        if g.get("phase") not in phases or (only and gid not in only):
            continue
        row = {"gate": gid, "spec": g.get("spec"), "exists": False, "expected": None, "applicable": True}
        cond = g.get("condition")
        if cond and not C.rung_taken(cond["ladder"], cond["min_rung"]):
            row["applicable"] = False
        if g.get("spec") and not g.get("deferred"):
            row["exists"] = os.path.isfile(C.path(g["spec"]))
            row["expected"] = C.expected_runs(g, tier)
            row["corners"] = g["scope"]["corners"][tier]
            row["n_mc"] = (g["scope"].get("mc") or {}).get(tier)
        rows.append(row)
    return rows, gates_y, spec


def run_sims(rows, tier, jobs):
    walls = {}
    for r in rows:
        if not r["spec"] or not r["exists"] or not r["applicable"]:
            continue
        t0 = time.time()
        recs, summ = runner.run_spec(C.path(r["spec"]), jobs=jobs, only_corners=r["corners"], n_mc=r.get("n_mc"),
                                     verbose=False)
        walls[r["gate"]] = round(time.time() - t0, 1)
        bad = sum(1 for x in recs if x["status"] != "ok")
        print("SIM %-9s %4d runs (expected %s), %d not ok, %.1f s" % (r["gate"], len(recs), r["expected"], bad, walls[r["gate"]]))
    return walls


def write_manifest(tier, phases, rows, walls, wall_total):
    hashes = C.input_hashes()
    sizes = C.path("sizing", "sizes.spice")
    hashes["spec_files"] = {f: C.sha256_file(C.path(f)) for f in ("spec/spec.yaml", "spec/gates.yaml", "spec/pins.yaml",
                                                                  "spec/paths.yaml", "spec/decisions.yaml")}
    nets = {}
    ndir = C.path("netlist")
    for fn in sorted(os.listdir(ndir)) if os.path.isdir(ndir) else []:
        if fn.endswith(".spice"):
            nets[fn] = C.sha256_file(os.path.join(ndir, fn))
    env = C.path("results", "env.json")
    man = {"generated": time.strftime("%Y-%m-%d %H:%M:%S"), "tier": tier, "phases": phases, "git": C.git_state(),
           "harness_version": runner.HARNESS_VERSION, "hashes": hashes, "netlists": nets,
           "sizes_spice_sha256": C.sha256_file(sizes) if os.path.isfile(sizes) else None,
           "tools": C.load_json(env)["tools"] if os.path.isfile(env) else None,
           "runs": [{"gate": r["gate"], "expected": r["expected"], "spec_exists": r["exists"],
                     "wall_s": walls.get(r["gate"])} for r in rows],
           "wall_s": round(wall_total, 1)}
    C.write_json("results/manifest.json", man)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tier", default="smoke", choices=["smoke", "full"])
    ap.add_argument("--phases", default="env,prelayout")
    ap.add_argument("--only", default="")
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--stage", default="all", choices=["sim", "gates", "report", "all"])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    phases = [p for p in a.phases.split(",") if p]
    only = [x for x in a.only.split(",") if x]
    rows, gates_y, spec = plan(a.tier, phases, only)
    refs = G.check_refs(gates_y["gates"], spec)
    if refs:
        print("gates.yaml has unresolved references:\n  " + "\n  ".join(refs), file=sys.stderr)
        return 2
    print("%-9s %-34s %-8s %-9s %s" % ("gate", "spec", "exists", "expected", "corners / MC"))
    for r in rows:
        print("%-9s %-34s %-8s %-9s %s" % (r["gate"], r["spec"] or "(json gate)", r["exists"] if r["spec"] else "-",
                                           r["expected"] if r["expected"] is not None else "-",
                                           ("%s%s" % (r.get("corners", ""), (" mc=%s" % r["n_mc"]) if r.get("n_mc") else ""))
                                           + ("" if r["applicable"] else "  (not applicable)")))
    if a.dry_run:
        return 0
    t0 = time.time()
    walls = {}
    if a.stage in ("sim", "all"):
        walls = run_sims(rows, a.tier, a.jobs)
    rc = 0
    if a.stage in ("gates", "all"):
        rc = G.main(["--tier", a.tier, "--phases", ",".join(phases)])
    if a.stage in ("report", "all"):
        R.main([])
    if a.stage in ("gates", "all"):
        write_manifest(a.tier, phases, rows, walls, time.time() - t0)
    return rc


if __name__ == "__main__":
    sys.exit(main())
