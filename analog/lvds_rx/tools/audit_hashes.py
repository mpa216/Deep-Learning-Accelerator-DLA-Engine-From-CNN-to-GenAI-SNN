"""Audit check: is every stored result tied to the CURRENT inputs?

For each pre-layout gate at the given tier, rebuild the run list exactly as the harness would (deck text, includes such
as sizing/sizes.spice and the netlists, generated stimulus files) WITHOUT simulating, and compare each planned run's
content hash with the hash stored in the bench's results.json. Helper specs of flow/run_all.py HELPERS are checked too.

Known harness flaw (found by this audit, harness 1.3): for a bench whose prep hook generates include files, the run hash
takes the include-file hash from the copy left on disk by the PREVIOUS execution, so the stored hash of a run can differ
from the planned one although every input is identical. A hash mismatch is therefore re-checked by ingredients: the deck
on disk equals the planned deck, every prep file on disk equals the planned content, the run's result.json carries the
stored hash, and (with --since) result.json is not older than the given epoch, i.e. it was simulated after the sizing
and netlist reached their current content. Only a run that fails both checks is reported as stale.

usage (in the container): tools/cx python3 tools/audit_hashes.py [--tier full] [--only TB1,TB2] [--since EPOCH]
Writes results/audit_hashes.json; exit code 0 only if every gate is current.
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "flow"))
import common as C  # noqa: E402
import run_all  # noqa: E402
from harness import runner  # noqa: E402

SINCE = 0.0


def planned(spec_path, corners, n_mc):
    spec_path = os.path.abspath(spec_path)
    sd = os.path.dirname(spec_path)
    spec = runner.load_spec(spec_path)
    name = spec.get("name") or os.path.splitext(os.path.basename(spec_path))[0]
    deck_path = os.path.join(sd, spec["deck"])
    with open(deck_path) as f:
        template = f.read()
    out_dir = os.path.join(sd, spec.get("out", "results/" + name))
    mc = dict(spec["mc"]) if spec.get("mc") else None
    if mc and n_mc:
        mc["n"] = n_mc
        mc.pop("seeds", None)
    work = os.path.join(out_dir, "work")
    # abspath as in runner.run_testbench: a deck that lives in another bench's folder ("../tb4_pd/x.spice") must give the same path text
    runs = runner.build_runs(template, os.path.abspath(os.path.dirname(deck_path)), os.path.abspath(work), corners or spec.get("corners", "tt"),
                             spec.get("grid"), mc, spec.get("vars"), runner._load_hook(sd, spec.get("prep")),
                             runner.ngspice_version(runner.NGSPICE))
    return {r["id"]: r for r in runs}, os.path.join(out_dir, "results.json")


def stored(path):
    d = json.load(open(path))
    recs = d["runs"] if isinstance(d, dict) else d
    return {r["id"]: (r.get("hash"), r.get("status"), bool(r.get("retry"))) for r in recs}


def ingredients(run, stored_hash):
    """'ok' or the first ingredient that differs: nodir, deck, file, hash, old."""
    rd = run["run_dir"]
    if not os.path.isdir(rd):
        return "nodir"
    try:
        if open(os.path.join(rd, "deck.spice")).read() != run["deck"]:
            return "deck"
        for k, v in run["files"].items():
            if open(os.path.join(rd, k)).read() != v:
                return "file"
        rj = os.path.join(rd, "result.json")
        if json.load(open(rj)).get("hash") != stored_hash:
            return "hash"
        return "ok" if os.path.getmtime(rj) >= SINCE else "old"
    except (OSError, ValueError):
        return "file"


def check(label, spec_path, corners, n_mc):
    plan, res = planned(spec_path, corners, n_mc)
    o = {"bench": label, "planned": len(plan), "stored": 0, "match": 0, "ingredients": 0, "stale": 0, "missing": 0,
         "extra": 0, "not_ok": 0}
    if not os.path.isfile(res):
        o["missing"] = len(plan)
        return o
    st = stored(res)
    o["stored"] = len(st)
    o["extra"] = sum(1 for k in st if k not in plan)
    o["not_ok"] = sum(1 for v in st.values() if v[1] != "ok")
    for k, run in plan.items():
        if k not in st:
            o["missing"] += 1
        elif st[k][0] == run["hash"]:
            o["match"] += 1
        else:
            why = ingredients(run, st[k][0])
            if why == "deck" and st[k][2] and os.path.getmtime(os.path.join(run["run_dir"], "result.json")) >= SINCE:
                why = "ok"      # a retried run keeps the deck of the solver-option variant that converged (harness 1.3 retry)
                o["retried"] = o.get("retried", 0) + 1
            if why == "ok":
                o["ingredients"] += 1
            else:
                o["stale"] += 1
                o.setdefault("why", {})
                o["why"][why] = o["why"].get(why, 0) + 1
    return o


def main():
    global SINCE
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="full")
    ap.add_argument("--only", default="")
    ap.add_argument("--since", type=float, default=0.0, help="epoch seconds: runs accepted by ingredients must be newer")
    a = ap.parse_args()
    SINCE = a.since
    only = [x for x in a.only.split(",") if x]
    rows, _, _ = run_all.plan(a.tier, ["prelayout"], only)
    out = []
    for r in rows:
        if not r["spec"] or not r["exists"] or not r["applicable"]:
            continue
        for h in run_all.HELPERS.get(r["gate"], []):
            own = isinstance(h, tuple)
            h = h[0] if own else h
            out.append(check(r["gate"] + ":helper:" + os.path.basename(h), C.path(h), None if own else r["corners"], None))
        out.append(check(r["gate"], C.path(r["spec"]), r["corners"], r.get("n_mc")))
    bad = 0
    for o in out:
        ok = o["planned"] > 0 and o["match"] + o["ingredients"] == o["planned"] and o["not_ok"] == 0 and o["extra"] == 0
        bad += 0 if ok else 1
        print("%-30s planned %6d stored %6d hash-match %6d by-ingredients %5d stale %5d missing %5d extra %3d not_ok %3d  %s" % (
            o["bench"], o["planned"], o["stored"], o["match"], o["ingredients"], o["stale"], o["missing"], o["extra"],
            o["not_ok"], "OK" if ok else "STALE/INCOMPLETE %s" % o.get("why", "")))
    with open(os.path.join(ROOT, "results", "audit_hashes.json"), "w") as f:
        json.dump({"tier": a.tier, "since": a.since, "benches": out, "all_current": bad == 0}, f, indent=1)
    print("AUDIT_HASHES tier=%s benches=%d not_current=%d" % (a.tier, len(out), bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
