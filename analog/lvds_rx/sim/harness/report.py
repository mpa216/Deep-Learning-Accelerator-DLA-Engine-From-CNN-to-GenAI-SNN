"""report.py -- limits evaluation and the markdown summary (summary.md).

Spec "limits" format (JSON or YAML):
    "limits": {
        "vos":   {"min": -0.02, "max": 0.02, "scale": 1000, "unit": "mV", "label": "input offset"},
        "tpd":   {"max": 5e-9,  "scale": 1e9, "unit": "ns"},
        "idd":   {"max": 2e-3}
    }
`scale` multiplies the value for DISPLAY only (limits are always in the metric's own SI unit).
A limited metric that is missing or NaN in a run is a FAIL (never skipped).

Non-Monte-Carlo runs: every run passes or fails against the limits; the worst case per metric
(smallest margin) is highlighted.  Monte Carlo runs: the runs of one (corner, grid point) form a
group; the group passes if mean +- k*sigma lies inside the limits (k = mc.k, default 3; 6 sigma is
also printed) AND no sample failed.
"""
import math
import os

import numpy as np

from . import mc as _mc


def _sc(lim):
    return lim.get("scale", 1.0)


def margin(value, lim):
    """Smallest distance (SI units) to a limit; positive = inside; nan if value missing."""
    if value is None or not np.isfinite(value):
        return float("nan")
    m = []
    if lim.get("min") is not None:
        m.append(value - lim["min"])
    if lim.get("max") is not None:
        m.append(lim["max"] - value)
    return min(m) if m else float("inf")


def evaluate_runs(records, limits):
    """Per-run verdicts: list of dict(run, ok, failures[list of str], margins{metric: m})."""
    out = []
    for r in records:
        fails, margins = [], {}
        if r["status"] != "ok":
            fails.append("status=%s" % r["status"])
        for k, lim in limits.items():
            v = r["metrics"].get(k)
            m = margin(v, lim)
            margins[k] = m
            if v is None or not np.isfinite(v):
                fails.append("%s missing" % k)
            elif m < 0:
                fails.append("%s=%.4g outside [%s, %s]" % (k, v, "-inf" if lim.get("min") is None else "%.4g" % lim["min"],
                                                           "inf" if lim.get("max") is None else "%.4g" % lim["max"]))
        out.append({"run": r, "ok": not fails, "failures": fails, "margins": margins})
    return out


def group_key(r):
    return (r["corner"], tuple(sorted(r["params"].items())))


def group_name(key):
    c, p = key
    return c + ("" if not p else " " + " ".join("%s=%s" % kv for kv in p))


def evaluate_mc(records, limits, k):
    """Group MC records; returns list of dict(key, name, n_total, n_failed, stats{metric: check}, ok)."""
    groups = {}
    for r in records:
        groups.setdefault(group_key(r), []).append(r)
    res = []
    for key, rs in groups.items():
        failed = [r for r in rs if r["status"] != "ok"]
        st, ok = {}, not failed
        names = sorted({m for r in rs for m in r["metrics"]})
        for mname in names:
            vals = [r["metrics"].get(mname, float("nan")) if r["status"] == "ok" else float("nan") for r in rs]
            lim = limits.get(mname, {})
            c = _mc.check_limits(vals, lim.get("min"), lim.get("max"), k)
            # in a limited metric any bad sample already forces failure through n_bad
            st[mname] = c
            if mname in limits:
                ok = ok and c["ok"]
        for mname in limits:
            if mname not in names:
                ok = False
        res.append({"key": key, "name": group_name(key), "n_total": len(rs), "n_failed": len(failed),
                    "failed": failed, "stats": st, "ok": ok, "records": rs})
    return res


def _f(v, scale=1.0):
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return "n/a"
    return "%.4g" % (v * scale)


def _hdr(name, lim):
    u = lim.get("unit", "")
    return "%s%s" % (name, " (%s)" % u if u else "")


def write_summary(records, spec, out_dir, name, mc=None):
    limits = spec.get("limits", {}) or {}
    L = ["# %s" % name, ""]
    if spec.get("description"):
        L += [spec["description"], ""]
    # ---- counts
    stat = {}
    for r in records:
        stat[r["status"]] = stat.get(r["status"], 0) + 1
    ncached = sum(1 for r in records if r["cached"])
    L.append("Runs: **%d** (%s); %d reused from cache." % (len(records), ", ".join("%s %d" % kv for kv in sorted(stat.items())), ncached))
    L.append("")
    overall_ok = True
    bad = [r for r in records if r["status"] != "ok"]
    if mc:
        k = float(mc.get("k", 3))
        L += _mc_section(records, limits, out_dir, k, L)
        groups = evaluate_mc(records, limits, k)
        overall_ok = all(g["ok"] for g in groups)
    else:
        ver = evaluate_runs(records, limits)
        overall_ok = all(v["ok"] for v in ver)
        L += _corner_section(records, ver, limits)
    if bad:
        L += ["", "## Failed runs (explicit, not dropped)", "", "| run | status | first error |", "|---|---|---|"]
        for r in bad[:100]:
            L.append("| `%s` | %s | %s |" % (r["id"], r["status"], (r["errors"][0] if r["errors"] else "").replace("|", "/")))
        if len(bad) > 100:
            L.append("| ... | %d more | see results.json |" % (len(bad) - 100))
    L.insert(2, "**Overall: %s**" % ("PASS" if overall_ok else "FAIL") if limits else "**Overall: no limits given (information only)**")
    L.insert(3, "")
    path = os.path.join(out_dir, "summary.md")
    with open(path, "w") as f:
        f.write("\n".join(L) + "\n")
    return path


def _corner_section(records, ver, limits):
    L = []
    pk = sorted({k for r in records for k in r["params"]})
    mk = list(limits) + sorted({m for r in records for m in r["metrics"]} - set(limits))
    # worst case per limited metric
    worst = {}
    for k, lim in limits.items():
        cand = [(v["margins"][k], v["run"]["id"]) for v in ver if np.isfinite(v["margins"].get(k, float("nan")))]
        worst[k] = min(cand)[1] if cand else None
        miss = [v["run"]["id"] for v in ver if not np.isfinite(v["margins"].get(k, float("nan")))]
        if miss and not cand:
            worst[k] = miss[0]
    if limits:
        L += ["## Worst case per metric", "", "| metric | limit | worst run | value | margin | verdict |", "|---|---|---|---|---|---|"]
        for k, lim in limits.items():
            rid = worst[k]
            r = next((v["run"] for v in ver if v["run"]["id"] == rid), None)
            val = r["metrics"].get(k) if r else None
            m = margin(val, lim) if r else float("nan")
            lims = "%s .. %s" % (_f(lim.get("min"), _sc(lim)) if lim.get("min") is not None else "-", _f(lim.get("max"), _sc(lim)) if lim.get("max") is not None else "-")
            L.append("| %s | %s | `%s` | **%s** | %s | %s |" % (_hdr(k, lim), lims, rid, _f(val, _sc(lim)), _f(m, _sc(lim)),
                                                                   "PASS" if np.isfinite(m) and m >= 0 else "FAIL"))
        L.append("")
    L += ["## All runs", ""]
    cols = ["run", "corner"] + pk + ["status"] + [_hdr(k, limits.get(k, {})) for k in mk] + ["verdict"]
    L.append("| " + " | ".join(cols) + " |")
    L.append("|" + "---|" * len(cols))
    for v in ver[:400]:
        r = v["run"]
        cells = ["`%s`" % r["id"], r["corner"]] + [str(r["params"].get(k, "")) for k in pk] + [r["status"]]
        for k in mk:
            lim = limits.get(k, {})
            s = _f(r["metrics"].get(k), _sc(lim))
            if k in limits:
                if worst.get(k) == r["id"]:
                    s = "**%s** (worst)" % s
                if k in limits and (not np.isfinite(v["margins"].get(k, float("nan"))) or v["margins"][k] < 0):
                    s += " FAIL"
            cells.append(s)
        cells.append("PASS" if v["ok"] else "FAIL: " + "; ".join(v["failures"])[:120].replace("|", "/"))
        L.append("| " + " | ".join(cells) + " |")
    if len(ver) > 400:
        L.append("\n(%d more rows: see results.csv)" % (len(ver) - 400))
    return L


def _mc_section(records, limits, out_dir, k, parent_lines):
    L = []
    groups = evaluate_mc(records, limits, k)
    plots = os.path.join(out_dir, "plots")
    os.makedirs(plots, exist_ok=True)
    L += ["## Monte Carlo statistics (limits applied to mean +- %g sigma; N valid / failed shown)" % k, ""]
    mnames = list(limits) + sorted({m for g in groups for m in g["stats"]} - set(limits))
    for mname in mnames:
        lim = limits.get(mname, {})
        sc = _sc(lim)
        L += ["### %s" % _hdr(mname, lim), "",
              "| group | N ok | N failed | mean | sigma | min | max | mean-%gs | mean+%gs | mean+-6s | verdict |" % (k, k),
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        worst_g = None
        if mname in limits:
            cand = [(min([x for x in (g["stats"][mname]["margin_lo"], g["stats"][mname]["margin_hi"]) if x is not None] or [float("inf")]), g["name"])
                    for g in groups if mname in g["stats"] and np.isfinite(g["stats"][mname]["mean"])]
            worst_g = min(cand)[1] if cand else None
        for g in groups:
            s = g["stats"].get(mname)
            if s is None:
                if mname in limits:
                    L.append("| %s | 0 | %d | n/a | n/a | n/a | n/a | n/a | n/a | n/a | FAIL (no valid samples) |"
                             % (g["name"], g["n_total"]))
                continue
            nm = g["name"] if g["name"] != worst_g else "**%s** (worst)" % g["name"]
            s6 = _mc.stats([r["metrics"].get(mname, float("nan")) for r in g["records"] if r["status"] == "ok"], ks=(6,))
            ok = (s["ok"] and g["n_failed"] == 0) if mname in limits else None
            L.append("| %s | %d | %d | %s | %s | %s | %s | %s | %s | %s .. %s | %s |" % (
                nm, s["n"], g["n_failed"] + s["n_bad"], _f(s["mean"], sc), _f(s["sigma"], sc), _f(s["min"], sc), _f(s["max"], sc),
                _f(s["lo%g" % k], sc),
                _f(s["hi%g" % k], sc),
                _f(s6.get("lo6"), sc), _f(s6.get("hi6"), sc),
                "-" if ok is None else ("PASS" if ok else "FAIL")))
            # histogram (limited metrics only, or all when no limits are given)
            if limits and mname not in limits:
                continue
            vals = [r["metrics"].get(mname, float("nan")) for r in g["records"] if r["status"] == "ok"]
            png = "hist_%s__%s.png" % (mname, "".join(c if c.isalnum() or c in "._-" else "_" for c in g["name"]))
            _mc.histogram(vals, os.path.join(plots, png), title="%s  [%s]" % (mname, g["name"]),
                          xlabel=_hdr(mname, lim) if sc != 1 else mname, unit_scale=sc,
                          lo=lim.get("min"), hi=lim.get("max"), k=k)
        L.append("")
        # link the plots in one line per metric
        if not limits or mname in limits:
            L.append("Histograms: " + ", ".join("[%s](plots/hist_%s__%s.png)" % (g["name"], mname, "".join(c if c.isalnum() or c in "._-" else "_" for c in g["name"])) for g in groups if mname in g["stats"]))
        L.append("")
    return L
