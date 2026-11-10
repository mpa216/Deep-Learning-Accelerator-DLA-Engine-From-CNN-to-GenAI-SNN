#!/usr/bin/env python3
"""gates.py -- results + spec/gates.yaml -> results/gates.json.

    python3 flow/gates.py [--tier smoke|full] [--phases env,prelayout] [--out results/gates.json]

A gate PASSES only if (1) its results exist, (2) every run has status `ok`, (3) the run count equals the expected
count computed from gates.yaml `scope` (and the spec file agrees with that scope), (4) every check holds.
Failure reason codes: MISSING, STATUS, COUNT, SCOPE, LIMIT, NODATA, REF.
Gate status: PASS | FAIL | NOT_RUN (nothing to evaluate yet) | NOT_APPLICABLE (condition not met).
Exit code 0 only if every evaluated gate is PASS or NOT_APPLICABLE.
"""
import argparse
import collections
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

PHASE_ORDER = ["env", "prelayout", "layout", "postlayout"]


# ------------------------------------------------------------------------------------------ small helpers
def _num(x):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else x


def _match(rec, where):
    """where: {field: value | [values]}; fields come from the record top level or its params."""
    for k, want in (where or {}).items():
        if k in rec:
            have = rec[k]
        elif k in rec.get("params", {}):
            have = rec["params"][k]
        else:
            return False
        wants = want if isinstance(want, list) else [want]
        ok = False
        for w in wants:
            if isinstance(w, (int, float)) and isinstance(have, (int, float)):
                ok = math.isclose(float(w), float(have), rel_tol=1e-6, abs_tol=1e-12)
            else:
                ok = str(w) == str(have)
            if ok:
                break
        if not ok:
            return False
    return True


def _limits(chk, spec):
    lo = C.resolve(chk.get("min"), spec)
    hi = C.resolve(chk.get("max"), spec)
    return lo, hi


def _margin(val, lo, hi):
    m = []
    if lo is not None:
        m.append(val - lo)
    if hi is not None:
        m.append(hi - val)
    return min(m) if m else float("inf")


def _fmt_limit(lo, hi):
    return "%s .. %s" % ("-inf" if lo is None else "%.6g" % lo, "+inf" if hi is None else "%.6g" % hi)


# ------------------------------------------------------------------------------------------ check kinds
def check_per_run(chk, runs, spec):
    lo, hi = _limits(chk, spec)
    sel = [r for r in runs if _match(r, chk.get("where"))]
    out = {"kind": "per_run", "metric": chk["metric"], "where": chk.get("where"), "limit": _fmt_limit(lo, hi),
           "n": len(sel), "reasons": []}
    if not sel:
        out.update(status="FAIL", detail="no run matches the where filter")
        out["reasons"].append(("NODATA", "%s: no run matches where=%s" % (chk["metric"], chk.get("where"))))
        return out
    worst, worst_run, bad = None, None, []
    for r in sel:
        v = _num(r["metrics"].get(chk["metric"]))
        if v is None:
            bad.append((r["id"], "missing/NaN"))
            continue
        if chk.get("abs"):
            v = abs(v)
        m = _margin(v, lo, hi)
        if worst is None or m < worst[0]:
            worst, worst_run = (m, v), r["id"]
        if m < 0:
            bad.append((r["id"], v))
    out["worst"] = None if worst is None else worst[1]
    out["worst_run"] = worst_run
    out["margin"] = None if worst is None else worst[0]
    if bad:
        out["status"] = "FAIL"
        out["detail"] = "%d of %d runs violate (first: %s = %s)" % (len(bad), len(sel), bad[0][0], bad[0][1])
        out["reasons"].append(("LIMIT", "%s: %d of %d runs outside %s (first %s = %s)" %
                               (chk["metric"], len(bad), len(sel), _fmt_limit(lo, hi), bad[0][0], bad[0][1])))
    else:
        out["status"] = "PASS"
    return out


def check_report(chk, runs, spec):
    sel = [r for r in runs if _match(r, chk.get("where"))]
    vals = [_num(r["metrics"].get(chk["metric"])) for r in sel]
    out = {"kind": "report", "metric": chk["metric"], "where": chk.get("where"), "limit": "reported", "n": len(sel),
           "reasons": []}
    if not sel or any(v is None for v in vals):
        out["status"] = "FAIL"
        out["detail"] = "metric missing/NaN in %d of %d runs" % (sum(v is None for v in vals), len(sel))
        out["reasons"].append(("NODATA", "%s must be reported by every run: %s" % (chk["metric"], out["detail"])))
    else:
        out.update(status="PASS", worst=None, min=min(vals), max=max(vals), mean=sum(vals) / len(vals))
    return out


def check_spread(chk, runs, spec):
    over, mode = chk["over"], chk.get("mode", "ratio")
    lo, hi = _limits(chk, spec)
    sel = [r for r in runs if _match(r, chk.get("where"))]
    groups = collections.defaultdict(list)
    for r in sel:
        key = (r["corner"],) + tuple(sorted((k, str(v)) for k, v in r["params"].items() if k != over))
        groups[key].append(r)
    out = {"kind": "spread", "metric": chk["metric"], "over": over, "mode": mode, "where": chk.get("where"),
           "limit": _fmt_limit(lo, hi), "n": len(groups), "reasons": []}
    worst, bad = None, []
    for key, rs in groups.items():
        vals = [_num(r["metrics"].get(chk["metric"])) for r in rs]
        if len(rs) < 2 or any(v is None for v in vals):
            bad.append((key, "needs >= 2 finite values, got %s" % vals))
            continue
        if mode == "ratio":
            if min(vals) <= 0:
                bad.append((key, "non-positive value, ratio undefined"))
                continue
            s = max(vals) / min(vals)
        else:
            s = max(vals) - min(vals)
        m = _margin(s, lo, hi)
        if worst is None or m < worst[0]:
            worst = (m, s, key)
        if m < 0:
            bad.append((key, s))
    if not groups:
        bad.append(("-", "no run matches the where filter"))
    if worst:
        out.update(worst=worst[1], worst_run=str(worst[2]), margin=worst[0])
    if bad:
        out["status"] = "FAIL"
        out["detail"] = "%d of %d groups violate (first: %s = %s)" % (len(bad), len(groups), bad[0][0], bad[0][1])
        out["reasons"].append(("LIMIT" if worst else "NODATA", "%s spread over %s: %s" % (chk["metric"], over, out["detail"])))
    else:
        out["status"] = "PASS"
    return out


def check_mc_offset_window(chk, runs, spec):
    """Per (corner, grid point) group: |mean| + k*sigma + extras <= window and sigma <= sigma_max.
    sigma = sample standard deviation (Gaussian fit); normality (D'Agostino) is recorded, not gated."""
    k = float(C.resolve(chk["k"], spec))
    window = float(C.resolve(chk["window"], spec))
    sigma_max = C.resolve(chk.get("sigma_max"), spec)
    extra = 0.0
    for e in chk.get("extra", []):
        extra += float(C.lookup(spec, e["ref"])) * float(e.get("mul", 1.0))
    groups = collections.defaultdict(list)
    for r in runs:
        key = (r["corner"],) + tuple(sorted((a, str(v)) for a, v in r["params"].items()))
        groups[key].append(_num(r["metrics"].get(chk["metric"])))
    out = {"kind": "mc_offset_window", "metric": chk["metric"], "limit": "<= %.6g (k=%g, extra=%.6g)" % (window, k, extra),
           "n": len(groups), "reasons": [], "normality_p_min": None}
    worst, bad, pmin = None, [], None
    for key, vals in groups.items():
        if len(vals) < 2 or any(v is None for v in vals):
            bad.append((key, "missing/NaN samples"))
            continue
        n = len(vals)
        mean = sum(vals) / n
        sig = math.sqrt(sum((v - mean) ** 2 for v in vals) / (n - 1))
        total = abs(mean) + k * sig + extra
        try:
            from scipy import stats
            if n >= 20:
                p = float(stats.normaltest(vals).pvalue)
                pmin = p if pmin is None else min(pmin, p)
        except Exception:
            pass
        m = window - total
        if worst is None or m < worst[0]:
            worst = (m, total, key, mean, sig, n)
        if m < 0 or (sigma_max is not None and sig > float(sigma_max)):
            bad.append((key, "total %.4g mV (mean %.3g, sigma %.3g mV, n %d)" % (total * 1e3, mean * 1e3, sig * 1e3, n)))
    out["normality_p_min"] = pmin
    if worst:
        out.update(worst=worst[1], worst_run=str(worst[2]), margin=worst[0], mean=worst[3], sigma=worst[4], samples=worst[5])
    if not groups:
        bad.append(("-", "no data"))
    if bad:
        out["status"] = "FAIL"
        out["detail"] = "%d of %d groups violate (first: %s %s)" % (len(bad), len(groups), bad[0][0], bad[0][1])
        out["reasons"].append(("LIMIT" if worst else "NODATA", "offset window: " + out["detail"]))
    else:
        out["status"] = "PASS"
    return out


def _json_path(obj, path):
    """a.b[*].c -> list of values."""
    cur = [obj]
    for part in path.split("."):
        star = part.endswith("[*]")
        name = part[:-3] if star else part
        nxt = []
        for c in cur:
            v = c[name]
            nxt += list(v) if star else [v]
        cur = nxt
    return cur


def check_json_value(chk, data, spec):
    out = {"kind": "json_value", "metric": chk["path"], "agg": chk.get("agg", "value"), "reasons": []}
    try:
        vals = _json_path(data, chk["path"])
    except (KeyError, TypeError) as e:
        out.update(status="FAIL", n=0, limit="-", detail="path %s not found (%r)" % (chk["path"], e))
        out["reasons"].append(("NODATA", out["detail"]))
        return out
    vals = [(1 if v is True else 0 if v is False else v) for v in vals]
    agg = chk.get("agg", "value")
    if any(not C.is_number(v) for v in vals) or not vals:
        out.update(status="FAIL", n=len(vals), limit="-", detail="non-numeric or empty: %s" % (vals[:3],))
        out["reasons"].append(("NODATA", "%s: %s" % (chk["path"], out["detail"])))
        return out
    v = {"value": lambda: vals[0], "max": lambda: max(vals), "min": lambda: min(vals),
         "abs_max": lambda: max(abs(x) for x in vals), "count": lambda: len(vals)}[agg]()
    v = v * float(chk.get("scale", 1.0))
    lo, hi, eq = C.resolve(chk.get("min"), spec), C.resolve(chk.get("max"), spec), C.resolve(chk.get("eq"), spec)
    ok = ((lo is None or v >= lo) and (hi is None or v <= hi) and
          (eq is None or math.isclose(v, float(eq), rel_tol=1e-9, abs_tol=1e-12)))
    out.update(n=len(vals), worst=v, limit=("== %.6g" % eq) if eq is not None else _fmt_limit(lo, hi),
               status="PASS" if ok else "FAIL")
    if not ok:
        out["detail"] = "%s(%s) = %.6g outside %s" % (agg, chk["path"], v, out["limit"])
        out["reasons"].append(("LIMIT", out["detail"]))
    return out


# ------------------------------------------------------------------------------------------ gate evaluation
def check_refs(gates, spec):
    """Every $spec reference in gates.yaml must resolve (a typo would otherwise silently pass nothing)."""
    bad = []

    def walk(x, where):
        if isinstance(x, str) and x.startswith("$spec."):
            try:
                C.lookup(spec, x[len("$spec."):])
            except (KeyError, TypeError):
                bad.append("%s: unresolved %s" % (where, x))
        elif isinstance(x, list):
            for i in x:
                walk(i, where)
        elif isinstance(x, dict):
            for k, i in x.items():
                walk(i, where)
                if k == "ref":
                    try:
                        C.lookup(spec, i)
                    except (KeyError, TypeError):
                        bad.append("%s: unresolved ref %s" % (where, i))
    for gid, g in gates.items():
        walk(g.get("checks", []), gid)
    return bad


def evaluate_gate(gid, gate, spec, tier, root=None, results_file=None, spec_file=None):
    """Evaluate one gate.  `results_file` / `spec_file` override the locations (used by the mutation tests)."""
    res = {"id": gid, "title": gate.get("title", ""), "phase": gate.get("phase"), "status": "NOT_RUN",
           "reasons": [], "checks": [], "expected_runs": None, "actual_runs": None, "status_counts": {}}
    cond = gate.get("condition")
    if cond and not C.rung_taken(cond["ladder"], cond["min_rung"], root):
        res["status"] = "NOT_APPLICABLE"
        res["reasons"].append(("CONDITION", "needs ladder %s rung >= %s (not taken)" % (cond["ladder"], cond["min_rung"])))
        return res
    if gate.get("deferred"):
        res["reasons"].append(("DEFERRED", gate["deferred"]))
        return res

    # ---- JSON-file gates (ENV, SIZE, TB0, LAYOUT)
    if "json" in gate:
        jp = gate["json"] if os.path.isabs(gate["json"]) else C.path(gate["json"], root=root)
        if not os.path.isfile(jp):
            res["reasons"].append(("MISSING", "%s not written yet" % gate["json"]))
            return res
        res["results_file"], res["results_sha256"] = gate["json"], C.sha256_file(jp)
        data = C.load_json(jp)
        res["checks"] = [check_json_value(c, data, spec) for c in gate["checks"]]
        res["status"] = "PASS" if all(c["status"] == "PASS" for c in res["checks"]) else "FAIL"
        for c in res["checks"]:
            res["reasons"] += c["reasons"]
        return res

    # ---- harness gates
    sp = spec_file or C.path(gate["spec"], root=root)
    if not os.path.isfile(sp):
        res["reasons"].append(("MISSING", "testbench spec %s not written yet" % gate["spec"]))
        return res
    rf = results_file or C.spec_results_file(gate, root)
    if not os.path.isfile(rf):
        res["reasons"].append(("MISSING", "no results at %s (run it first)" % os.path.relpath(rf, root or C.ROOT)))
        return res
    exp = C.expected_runs(gate, tier)
    res["expected_runs"] = exp
    probs = C.spec_file_problems(gate, C.load_json(sp))
    if probs:
        res["status"] = "FAIL"
        res["reasons"] += [("SCOPE", p) for p in probs]
    data = C.load_json(rf)
    runs = data["runs"]
    res["results_file"], res["results_sha256"] = os.path.relpath(rf, root or C.ROOT), C.sha256_file(rf)
    res["actual_runs"] = len(runs)
    res["status_counts"] = dict(collections.Counter(r["status"] for r in runs))
    res["cpu_s"] = round(sum(float(r.get("elapsed") or 0) for r in runs), 1)
    failed = False
    if len(runs) != exp:
        failed = True
        res["reasons"].append(("COUNT", "expected %d runs (tier %s), found %d" % (exp, tier, len(runs))))
    notok = {k: v for k, v in res["status_counts"].items() if k != "ok"}
    if notok:
        failed = True
        res["reasons"].append(("STATUS", "runs not ok: %s" % notok))
    ok_runs = [r for r in runs if r["status"] == "ok"]
    for c in gate["checks"]:
        fn = {"per_run": check_per_run, "report": check_report, "spread": check_spread,
              "mc_offset_window": check_mc_offset_window}[c["kind"]]
        r = fn(c, ok_runs, spec)
        res["checks"].append(r)
        if r["status"] != "PASS":
            failed = True
            res["reasons"] += r["reasons"]
    res["status"] = "FAIL" if (failed or probs) else "PASS"
    return res


def evaluate_all(tier="smoke", phases=("env", "prelayout"), root=None):
    gates_y = C.load_yaml("spec/gates.yaml", root)
    spec = C.load_yaml("spec/spec.yaml", root)
    refs = check_refs(gates_y["gates"], spec)
    if refs:
        raise SystemExit("gates.yaml has unresolved references:\n  " + "\n  ".join(refs))
    results = {}
    for gid, g in gates_y["gates"].items():
        if g.get("phase") in phases:
            results[gid] = evaluate_gate(gid, g, spec, tier, root)
    counts = collections.Counter(r["status"] for r in results.values())
    cpu_min = sum(r.get("cpu_s", 0) for r in results.values()) / 60.0
    flags = []
    tb = gates_y.get("time_budget", {})
    if tier == "full" and cpu_min > tb.get("full_cpu_min", 1e9) * tb.get("flag_over_factor", 2.0):
        flags.append("full-tier CPU time %.0f min is over %.1fx the %g min estimate" %
                     (cpu_min, tb["flag_over_factor"], tb["full_cpu_min"]))
    out = {"generated": time.strftime("%Y-%m-%d %H:%M:%S"), "tier": tier, "phases": list(phases),
           "git": C.git_state(root), "gates_sha256": C.sha256_file(C.path("spec/gates.yaml", root=root)),
           "spec_sha256": C.sha256_file(C.path("spec/spec.yaml", root=root)),
           "summary": dict(counts), "cpu_min": round(cpu_min, 1), "flags": flags,
           "green": all(r["status"] in ("PASS", "NOT_APPLICABLE") for r in results.values()),
           "waivers": C.decisions(root).get("entries") or [], "gates": results}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tier", default="smoke", choices=["smoke", "full"])
    ap.add_argument("--phases", default="env,prelayout")
    ap.add_argument("--out", default="results/gates.json")
    a = ap.parse_args(argv)
    phases = [p for p in a.phases.split(",") if p]
    bad = [p for p in phases if p not in PHASE_ORDER]
    if bad:
        raise SystemExit("unknown phase %s (known: %s)" % (bad, PHASE_ORDER))
    out = evaluate_all(a.tier, phases)
    C.write_json(a.out, out)
    for gid, r in out["gates"].items():
        why = "; ".join("%s: %s" % tuple(x) for x in r["reasons"][:2])
        print("%-9s %-14s runs %s/%s  %s" % (r["status"], gid, r["actual_runs"], r["expected_runs"], why[:160]))
    print("GATES tier=%s phases=%s summary=%s green=%s -> %s" % (a.tier, ",".join(phases), out["summary"], out["green"], a.out))
    return 0 if out["green"] else 1


if __name__ == "__main__":
    sys.exit(main())
