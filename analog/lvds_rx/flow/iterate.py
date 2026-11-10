#!/usr/bin/env python3
"""iterate.py -- thin, enforcing logger of sizing/simulate iterations (PLAN_V2 rule 7); NOT an optimiser.

    python3 flow/iterate.py log --phase P1 --block stage1 --symptom "A1_min 3.2 at ss" --knob "L_pair 0.5->0.4" \
                               [--result results/gates.json] [--note text]
    python3 flow/iterate.py status

Appends one JSON line to results/iterations.jsonl.  `log` refuses (exit 3) when the block already has
iteration_caps.per_block iterations or the phase has iteration_caps.per_phase: the next step is the next
fallback-ladder rung in spec/decisions.yaml, never another hand tweak.
"""
import argparse
import collections
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

LOG = "results/iterations.jsonl"


def read():
    p = C.path(LOG)
    if not os.path.isfile(p):
        return []
    return [json.loads(ln) for ln in open(p) if ln.strip()]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    lg = sub.add_parser("log")
    lg.add_argument("--phase", required=True)
    lg.add_argument("--block", required=True)
    lg.add_argument("--symptom", required=True)
    lg.add_argument("--knob", required=True)
    lg.add_argument("--result", default="")
    lg.add_argument("--note", default="")
    sub.add_parser("status")
    a = ap.parse_args(argv)
    caps = C.decisions().get("iteration_caps", {"per_block": 5, "per_phase": 8})
    rows = read()
    nb = collections.Counter(r["block"] for r in rows)
    npz = collections.Counter(r["phase"] for r in rows)
    if a.cmd == "status":
        for b, n in sorted(nb.items()):
            print("block %-14s %d/%d" % (b, n, caps["per_block"]))
        for p, n in sorted(npz.items()):
            print("phase %-14s %d/%d" % (p, n, caps["per_phase"]))
        print("total iterations %d" % len(rows))
        return 0
    if nb[a.block] >= caps["per_block"] or npz[a.phase] >= caps["per_phase"]:
        print("ITERATION CAP reached (block %s %d/%d, phase %s %d/%d): take the next rung of the fallback ladder "
              "(spec/decisions.yaml) instead of another tweak" % (a.block, nb[a.block], caps["per_block"], a.phase,
                                                                   npz[a.phase], caps["per_phase"]), file=sys.stderr)
        return 3
    row = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "phase": a.phase, "block": a.block, "iteration": nb[a.block] + 1,
           "symptom": a.symptom, "knob": a.knob, "result": a.result, "note": a.note,
           "sizes_sha256": C.sha256_file(C.path("sizing", "sizes.spice")) if os.path.isfile(C.path("sizing", "sizes.spice")) else None,
           "git": C.git_state()["commit"]}
    p = C.path(LOG)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "a") as f:
        f.write(json.dumps(row) + "\n")
    print("logged iteration %d of block %s (phase total %d/%d)" % (row["iteration"], a.block, npz[a.phase] + 1, caps["per_phase"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
