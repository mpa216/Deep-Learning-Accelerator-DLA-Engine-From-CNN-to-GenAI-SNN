#!/usr/bin/env python3
"""report.py -- results/gates.json (+ env.json, mutants.json, manifest.json) -> results/REPORT.md.

Every number in the report is generated here from JSON; waivers and ladder rungs (spec/decisions.yaml) are printed first.
    python3 flow/report.py [--gates results/gates.json] [--out results/REPORT.md]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402


def g(x, nd=4):
    if x is None:
        return "-"
    if isinstance(x, float):
        return "%.*g" % (nd, x)
    return str(x)


def render(gates, env=None, mutants=None, manifest=None):
    L = []
    gi = gates.get("git", {})
    L.append("# LVDS RX macro: verification report (generated)")
    L.append("")
    L.append("Generated %s by flow/report.py from results/gates.json. Tier **%s**, phases %s, commit `%s`%s. "
             "Criteria: spec/gates.yaml sha256 `%s...`." %
             (gates["generated"], gates["tier"], ", ".join(gates["phases"]), gi.get("commit"),
              {True: " (dirty)", False: "", None: " (dirty flag unavailable: no working git in the container)"}[gi.get("dirty")], gates["gates_sha256"][:12]))
    L.append("")
    L.append("## Waivers and fallback-ladder rungs")
    L.append("")
    w = gates.get("waivers") or []
    if not w:
        L.append("None. Every gate runs at its frozen (rung 0) limit.")
    else:
        L.append("| id | date | kind | ladder / rung | trigger | measured | gate relaxed |")
        L.append("|---|---|---|---|---|---|---|")
        for e in w:
            L.append("| %s | %s | %s | %s %s | %s | %s | %s |" % (
                e.get("id"), e.get("date"), e.get("kind"), e.get("ladder", ""), e.get("rung", ""),
                e.get("trigger", ""), e.get("measured", ""), e.get("gate_relaxed", "")))
    L.append("")
    s = gates["summary"]
    L.append("## Summary")
    L.append("")
    L.append("**%s**: %s" % ("GREEN" if gates["green"] else "NOT GREEN",
                             ", ".join("%d %s" % (v, k) for k, v in sorted(s.items()))))
    for f in gates.get("flags") or []:
        L.append("")
        L.append("FLAG: " + f)
    L.append("")
    L.append("| gate | phase | status | runs (found/expected) | worst margin | note |")
    L.append("|---|---|---|---|---|---|")
    for gid, r in gates["gates"].items():
        margins = [c["margin"] for c in r["checks"] if c.get("margin") is not None]
        note = "; ".join("%s: %s" % tuple(x) for x in r["reasons"][:1])[:110]
        L.append("| %s | %s | %s | %s/%s | %s | %s |" % (gid, r["phase"], r["status"], g(r["actual_runs"]),
                                                       g(r["expected_runs"]), g(min(margins)) if margins else "-", note))
    L.append("")
    L.append("## Gates")
    for gid, r in gates["gates"].items():
        L.append("")
        L.append("### %s: %s" % (gid, r["title"]))
        L.append("")
        L.append("Status **%s**. %s" % (r["status"], ("Runs %s of %s expected; run status counts %s; results `%s` (sha256 `%s...`)." % (
            g(r["actual_runs"]), g(r["expected_runs"]), r["status_counts"], r.get("results_file"),
            r.get("results_sha256", "")[:12])) if r["actual_runs"] is not None else ""))
        for code, msg in r["reasons"]:
            L.append("")
            L.append("- %s: %s" % (code, msg))
        if r["checks"]:
            L.append("")
            L.append("| metric | kind | where | limit | n | worst | status |")
            L.append("|---|---|---|---|---|---|---|")
            for c in r["checks"]:
                where = ", ".join("%s=%s" % kv for kv in (c.get("where") or {}).items()) or "all"
                L.append("| %s | %s | %s | %s | %s | %s | %s |" % (c["metric"], c["kind"], where, c.get("limit", ""),
                                                                   g(c.get("n")), g(c.get("worst")), c["status"]))
    if env:
        L.append("")
        L.append("## Environment (results/env.json)")
        L.append("")
        L.append("| item | value |")
        L.append("|---|---|")
        L.append("| LUT selftest | %s/%s passed |" % (env["lut_selftest"]["passed"], env["lut_selftest"]["total"]))
        L.append("| LUT load test | %s |" % ", ".join("%s=%s" % (k, g(v)) for k, v in env["lut_load"].items()))
        L.append("| harness tests | %s run, %s failures |" % (env["harness_tests"]["run"], env["harness_tests"]["failures"]))
        L.append("| OMP exports | ok=%s %s |" % (env["omp"]["ok"], env["omp"]["environment"]))
        L.append("| lint | %s findings %s |" % (env["lint"]["failed"], env["lint"]["rules"]))
        L.append("| toy layout regression | ok=%s |" % env["layout_toy"].get("ok"))
        for name, t in env["tools"].items():
            if isinstance(t, dict) and "present" in t:
                L.append("| tool %s | %s |" % (name, t.get("version") or ("present" if t["present"] else "MISSING")))
    if mutants:
        L.append("")
        L.append("## Gate mutation tests (results/mutants.json)")
        L.append("")
        L.append("| mutant | target | control | mutant result | detected |")
        L.append("|---|---|---|---|---|")
        for m in mutants["mutants"]:
            L.append("| %s | %s | %s | %s | %s |" % (m["id"], m["target"], m["control"], m["detail"], "YES" if m["detected"] else "NO (SURVIVED)"))
    if manifest:
        L.append("")
        L.append("## Manifest")
        L.append("")
        L.append("Wall time %s s; sizes.spice sha256 `%s`; LUT hash `%s...`." % (
            g(manifest.get("wall_s")), manifest.get("sizes_spice_sha256"), str(manifest["hashes"].get("luts"))[:12]))
    L.append("")
    return "\n".join(L)


def _opt(rel):
    p = C.path(rel)
    return C.load_json(p) if os.path.isfile(p) else None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gates", default="results/gates.json")
    ap.add_argument("--out", default="results/REPORT.md")
    a = ap.parse_args(argv)
    gates = C.load_json(a.gates)
    txt = render(gates, _opt("results/env.json"), _opt("results/mutants.json"), _opt("results/manifest.json"))
    out = C.path(a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        f.write(txt)
    print("REPORT %s (%d lines)" % (a.out, txt.count("\n")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
