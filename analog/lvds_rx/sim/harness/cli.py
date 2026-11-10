#!/usr/bin/env python3
"""Command line for the harness.

  python3 sim/harness/cli.py run   <spec.json> [--jobs N] [--force] [--corners SET] [--n-mc N] [--dry-run]
  python3 sim/harness/cli.py header <corner-or-set> [--mc none|mismatch|global|both]
  python3 sim/harness/cli.py corners

`--corners` takes a named set (tt, worst5, speed4, tt_temps, full45), a corner string
'proc:temp:vdd[:key=val]' or a comma-separated list of those.
Exit code of `run`: 0 = every run ok and every limit met, 1 = a limit failed or a run failed, 2 = bad usage.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import corners as C  # noqa: E402
from harness import runner  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run a testbench spec")
    r.add_argument("spec")
    r.add_argument("--jobs", type=int, default=None, help="parallel ngspice processes (default: spec or 3)")
    r.add_argument("--force", action="store_true", help="ignore the cache and re-run everything")
    r.add_argument("--corners", default=None, help="override the spec's corner set")
    r.add_argument("--n-mc", type=int, default=None, help="override the number of Monte Carlo samples")
    r.add_argument("--dry-run", action="store_true", help="only render the decks")
    h = sub.add_parser("header", help="print a corner header")
    h.add_argument("corner")
    h.add_argument("--mc", default="none", choices=C.MC_MODES)
    sub.add_parser("corners", help="list named corner sets")
    a = ap.parse_args(argv)
    if a.cmd == "corners":
        for k, v in C.CORNER_SETS.items():
            print("%-9s %2d: %s" % (k, len(v), ", ".join(c.name for c in v[:5]) + (" ..." if len(v) > 5 else "")))
        return 0
    if a.cmd == "header":
        for c in C.get_corner_set(a.corner.split(",") if "," in a.corner else a.corner):
            print(c.header(mc=a.mc))
        return 0
    corners = a.corners.split(",") if a.corners and "," in a.corners else a.corners
    recs, summ = runner.run_spec(a.spec, jobs=a.jobs, force=a.force, dry_run=a.dry_run, only_corners=corners, n_mc=a.n_mc)
    if a.dry_run:
        return 0
    print("summary:", summ)
    txt = open(summ).read()
    print([ln for ln in txt.splitlines() if ln.startswith("**Overall")][0])
    return 0 if ("Overall: PASS" in txt or "no limits" in txt) and all(r["status"] == "ok" for r in recs) else 1


if __name__ == "__main__":
    sys.exit(main())
