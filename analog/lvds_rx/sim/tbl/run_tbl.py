#!/usr/bin/env python3
"""run_tbl.py -- T11 piece C: run every post-layout bench (pre-layout core and extracted core), then the evaluator.

  tools/cx python3 sim/tbl/run_tbl.py [--jobs 4] [--only tbl_pd,tbl_eye] [--force] [--no-eval]

The single long run (tbl_lanes, extracted) starts first in its own process with one worker; the other specs run one at
a time with jobs - 1 workers, so at most `jobs` ngspice processes run.  The harness caches finished runs by content
hash, so a second call after an interruption only runs what is missing (--force re-runs everything).
Log: results/post_layout/run.log (one line per spec, then the evaluator's line, then EXIT <code>).
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CLI = os.path.join(ROOT, "sim", "harness", "cli.py")
ORDER = ["tbl_op", "tbl_ac", "tbl_trip", "tbl_idle", "tbl_en", "tbl_pd", "tbl_eye", "tbl_pkg", "tbl_lanes"]
LONG = ("tbl_lanes", "pex")
LOG = os.path.join(ROOT, "results", "post_layout", "run.log")


def log(msg):
    with open(LOG, "a") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    print(msg, flush=True)


def cmd(bench, var, jobs, force):
    c = ["python3", CLI, "run", os.path.join(ROOT, "sim", bench, f"{bench}_{var}.json"), "--jobs", str(jobs)]
    return c + (["--force"] if force else [])


def long_elapsed():
    """The long run's own simulation time (sum of its runs' elapsed in results.json).  Its logged wall is taken when it is
    joined, after the other benches: the 19207 s logged on 2026-11-14 was the other benches' time, not TB10's."""
    p = os.path.join(ROOT, "sim", LONG[0], "results", "%s_%s" % LONG, "results.json")
    try:
        import json
        with open(p) as f:
            runs = json.load(f).get("runs", [])
        return "%.0f s" % sum(float(r.get("elapsed") or 0) for r in runs)
    except Exception:  # noqa: BLE001 - a missing or partial file only loses this note
        return "unknown"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--only", default="")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--no-eval", action="store_true")
    a = ap.parse_args()
    only = [x for x in a.only.split(",") if x]
    benches = [b for b in ORDER if not only or b in only]
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    log("START benches %s jobs %d force %s" % (",".join(benches), a.jobs, a.force))
    rc = 0
    long_p = None
    if LONG[0] in benches:
        t0 = time.time()
        long_p = (subprocess.Popen(cmd(*LONG, 1, a.force), cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT), t0)
        log("started %s_%s in parallel (1 worker)" % LONG)
    for b in benches:
        for var in ("pre", "pex"):
            if (b, var) == LONG:
                continue
            t0 = time.time()
            r = subprocess.run(cmd(b, var, max(1, a.jobs - (1 if long_p else 0)), a.force), cwd=ROOT, capture_output=True, text=True)
            tail = (r.stdout.strip().splitlines() or [""])[-1][:200]
            log("%s_%s rc %d wall %.0f s | %s" % (b, var, r.returncode, time.time() - t0, tail))
            rc = rc or (r.returncode not in (0, 1))
    if long_p:
        p, t0 = long_p
        p.wait()
        log("%s_%s rc %d joined after %.0f s, simulation %s" % (LONG[0], LONG[1], p.returncode, time.time() - t0,
                                                                  long_elapsed()))
        rc = rc or (p.returncode not in (0, 1))
    if not a.no_eval:
        r = subprocess.run(["python3", os.path.join(HERE, "evaluate.py")], cwd=ROOT, capture_output=True, text=True)
        log("evaluate rc %d | %s" % (r.returncode, (r.stdout.strip().splitlines() or [r.stderr[-300:]])[-1][:300]))
    log("EXIT %d" % rc)
    return rc


if __name__ == "__main__":
    sys.exit(main())
