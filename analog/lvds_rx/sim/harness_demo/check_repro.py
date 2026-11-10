#!/usr/bin/env python3
"""Monte Carlo reproducibility / cache / independence checks on the pelgrom_pair testbench.

 (c1) re-run 100 seeds with --force: results must be bit-identical to the first run;
 (c2) run again without force: every run must come from the cache;
 (c3) editing the deck changes the hash: runs are re-executed (not served stale);
 (d)  different base seed -> statistically independent sample of the same population: the sigma
      ratio to the formula stays within the sampling error, with N=1000.
Exit code 0 only if all of them hold.   Run:  python3 sim/harness_demo/check_repro.py
"""
import json
import os
import shutil
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from harness import runner, mc  # noqa: E402

SPEC = os.path.join(HERE, "pelgrom_pair.json")
OUT = os.path.join(HERE, "results", "pelgrom_pair")


def vals(recs):
    return {r["id"]: r["metrics"].get("vos") for r in recs}


def main():
    ok = True
    base = {r["id"]: r["metrics"]["vos"] for r in json.load(open(os.path.join(OUT, "results.json")))["runs"]}
    # c1: forced re-run of the first 100 seeds, same spec (the seed list is a prefix-stable sequence)
    recs, _ = runner.run_spec(SPEC, force=True, n_mc=100, verbose=False)
    v = vals(recs)
    same = [i for i in v if i in base]
    maxd = max(abs(v[i] - base[i]) for i in same)
    print("c1 forced re-run: %d runs compared with the first campaign, max |diff| = %.3g V -> %s"
          % (len(same), maxd, "IDENTICAL" if maxd == 0 else "DIFFERENT"))
    ok &= len(same) == 1200 and maxd == 0
    # c2: cache
    recs, _ = runner.run_spec(SPEC, n_mc=100, verbose=False)
    ncached = sum(r["cached"] for r in recs)
    print("c2 second run without --force: %d/%d runs served from cache" % (ncached, len(recs)))
    ok &= ncached == len(recs)
    # c3: hash invalidation when the deck changes
    deck = os.path.join(HERE, "pelgrom_pair.spice")
    orig = open(deck).read()
    try:
        open(deck, "w").write(orig.replace("it tail 0 20u", "it tail 0 21u"))
        recs, _ = runner.run_spec(SPEC, n_mc=20, verbose=False)
        nc = sum(r["cached"] for r in recs)
        print("c3 deck edited (tail current 20u -> 21u): %d/%d runs cached (must be 0)" % (nc, len(recs)))
        ok &= nc == 0
    finally:
        open(deck, "w").write(orig)
    # restore the full 200-seed campaign results (cached except for the edited-deck runs, which re-run)
    runner.run_spec(SPEC, verbose=False)
    # d: independent seed base, N=1000, one area
    spec2 = json.load(open(SPEC))
    spec2.update(name="pelgrom_n1000", grid={"w": ["1u"], "l": ["0.5u"]}, mc={"n": 1000, "mode": "mismatch", "seed": 777, "k": 3})
    p2 = os.path.join(HERE, "pelgrom_n1000.json")
    json.dump(spec2, open(p2, "w"), indent=1)
    recs, _ = runner.run_spec(p2, verbose=False)
    x = np.array([r["metrics"]["vos"] for r in recs if r["status"] == "ok"])
    s = mc.stats(x)
    pred = mc.pelgrom_pair_sigma(1e-6, 0.5e-6)
    gm = np.mean([abs(r["metrics"]["gain"]) for r in recs if r["status"] == "ok"]) / 20e3
    pred_tot = np.hypot(pred, (10e-6 / gm) * 0.007008e-6 / np.sqrt(0.35e-6 * 1.1e-6))
    z = (s["sigma"] - pred_tot) / s["sigma_err"]
    print("d  independent base seed 777, N=%d (failed %d): mean %.3f mV (+-%.3f), sigma %.3f mV vs pred %.3f mV "
          "(VT only %.3f): ratio %.3f, %.2f std errors" % (s["n"], s["n_bad"] + len(recs) - s["n"], 1e3 * s["mean"],
                                                           1e3 * s["sigma"] / np.sqrt(s["n"]), 1e3 * s["sigma"], 1e3 * pred_tot,
                                                           1e3 * pred, s["sigma"] / pred_tot, z))
    ok &= abs(z) < 3 and abs(s["mean"]) < 3 * s["sigma"] / np.sqrt(s["n"])
    print("OVERALL", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
