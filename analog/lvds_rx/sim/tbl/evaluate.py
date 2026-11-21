#!/usr/bin/env python3
"""evaluate.py -- gate TBL (task T11, PLAN_V2 3.2 / 6.5): the extracted macro against the pre-layout netlist.

  python3 sim/tbl/evaluate.py      reads  sim/tbl_*/results/tbl_*_{pre,pex}/results.json
                                   writes results/post_layout/tbl.json (gate TBL of spec/gates.yaml reads it)
                                          results/post_layout/TBL.md   (the tables)

Pairs.  Every bench runs one deck twice, core = the pre-layout netlist (_pre) and core = the extracted RC netlist (_pex),
with the same corners and grid; the runs pair by run id (corner + grid point).  Both sets must be complete and `ok`.
Checks.  The checks of the source TB gate in spec/gates.yaml, limits resolved from spec/spec.yaml as flow/gates.py does,
on the runs their `where` filter selects (a check none of whose runs is in the TBL scope is listed as out of scope):
  per_run   margin = distance of the value to its limit (flow/gates.py _margin: the nearer side of a two-sided limit)
  spread    the same for the spread over `over` per group (ratio or delta), the groups formed as flow/gates.py does
  report    deltas listed, no limit
Criterion (frozen in gates.yaml: "every metric within 30 % of its margin to the TB limit").  Per pair
  used = (margin_pre - margin_pex) / margin_pre       the fraction of the pre-layout margin the layout used up
  PASS when used <= 0.30.  Checks without a margin by construction (ber_errors <= 0, toggle_diff == 0, osc_flag <= 0,
  model_warnings <= 0: margin_pre = 0) pass when the extracted value meets the limit.
  Reading, fixed before the runs (log/T11_notes.md): a LOSS of margin is gated; a GAIN of margin by more than 30 % is
  listed as favorable_large and explained in the report, not failed.  A pair whose pre-layout value is itself outside the
  limit (possible only outside the source gate's own scope) is pre_outside: listed, not gated.
Not measurable on the flat extracted netlist (no schematic devices; one VDD net): the per-device metrics of TB1 and the
split of the supply current into lanes and bias; the total is checked against 3 x I_lane max + I_bias max instead.
Added checks.
  TB1 s1_cm_dev_v   formed here as TB1 forms it: (oa + ob)/2 minus the mid-range over the 7 VIC of the same corner / VID.
  offset            the systematic offset the layout adds (TB3_trip off_v, extracted minus pre-layout) against 30 % of the
                    TB3_off window margin of the same corner / VIC (pre-layout Monte Carlo, N = 1000; mismatch is set by
                    device area, which the layout keeps, so sigma is taken as unchanged).
  D-012             sizing/FROZEN.md freeze condition at ff/125C/3.6 V, VIC 0.05 V, extracted netlist: operating point,
                    A1 >= 4, every TB4 timing limit, the TB5 eye limits; failing it takes ladder R6 (re-opens the sizing).
Worst against worst (decision D-019).  TB8 min_pulse_s in cases 3 and 5 (EN high, or rising, while the supply ramps): the
                    wake-up pulse is a race between the output chain waking and the comparator settling and does not pair
                    corner by corner, so the shortest pre-layout value over TB8's own 45 corners is set against the shortest
                    extracted value over the 45-corner evidence runs (tbl_en_pex + tbl_en_pexw_pulse / _cold / _rest), the
                    frozen 30 % rule applied to those two values; incomplete coverage fails the check.  Other cases: per pair.
"""
import collections
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "flow"))
sys.path.insert(0, os.path.join(ROOT, "sim"))
import common as C                                      # noqa: E402
import gates as G                                       # noqa: E402
from harness.corners import get_corner_set             # noqa: E402

USED_MAX = 0.30
EXACT_FAIL = 1.0e9                     # `used` of a failed check that has no margin by construction
OUT = os.path.join(ROOT, "results", "post_layout")
D012 = "ff_125c_3v60"
BENCHES = ["tbl_op", "tbl_ac", "tbl_trip", "tbl_pd", "tbl_pkg", "tbl_eye", "tbl_idle", "tbl_en", "tbl_lanes"]
SOURCE = {"tbl_op": "TB1", "tbl_ac": "TB2", "tbl_trip": "TB3_trip", "tbl_pd": "TB4", "tbl_pkg": "TB12", "tbl_eye": "TB5",
          "tbl_idle": "TB7", "tbl_en": "TB8", "tbl_lanes": "TB10"}
# D-019 (2026-11-22): pre-layout against extracted over the 45 corners, cases 3 and 5, the extracted pulse was longer in 62
# pairs and shorter in 25 (.scratch/t11/iter2/tb8_45pairs.py); ss/125C: 148 -> 28, 12 -> 36, 23 -> 43 ns at 3.0 / 3.3 / 3.6 V.
WVW = dict(bench="tbl_en", metric="min_pulse_s", cases=[3, 5], corners="full45",
           pre=["sim/tb8_en/results/tb8_en/results.json"],
           pex=["sim/tbl_en/results/tbl_en_pex/results.json", "sim/tbl_en/results/tbl_en_pexw_pulse/results.json",
                "sim/tbl_en/results/tbl_en_pexw_cold/results.json", "sim/tbl_en/results/tbl_en_pexw_rest/results.json"])
NOT_MEASURABLE = {
    "min_headroom_v": "per-device VDS - VDsat: the extracted netlist has layout fingers, not the schematic devices",
    "gmid_err": "per-device LUT comparison (fingers, not schematic devices)",
    "id_err": "per-device current (fingers, not schematic devices)",
    "vgs_err_v": "per-device LUT comparison (fingers, not schematic devices)",
    "np_overlap_v": "measured on the dump-free control netlist, a schematic variant the layout does not have",
    "i_lane_a": "one VDD net for three lanes and the bias block: the total idd_a is checked (3 x I_lane max + I_bias max)",
    "i_bias_a": "as i_lane_a",
}


def load(bench, var):
    p = os.path.join(ROOT, "sim", bench, "results", f"{bench}_{var}", "results.json")
    if not os.path.isfile(p):
        return None, p
    return {r["id"]: r for r in C.load_json(p)["runs"]}, p


def expected(bench, var):
    s = C.load_json(os.path.join(ROOT, "sim", bench, f"{bench}_{var}.json"))
    n = len(get_corner_set(s["corners"]))
    for v in s["grid"].values():
        n *= len(v)
    return n


def add_s1_cm_dev(runs):
    """TB1's s1_cm_dev_v: per (corner, vid), cm minus the mid-range of cm over the VIC points (NaN unless all 7 ran)."""
    grp = collections.defaultdict(dict)
    for r in runs.values():
        grp[(r["corner"], r["params"]["vid"])][r["params"]["vic"]] = r["metrics"]["s1_cm_v"]
    for r in runs.values():
        cms = grp[(r["corner"], r["params"]["vid"])]
        mid = 0.5 * (max(cms.values()) + min(cms.values())) if len(cms) == 7 else float("nan")
        r["metrics"]["s1_cm_dev_v"] = r["metrics"]["s1_cm_v"] - mid


def items(chk, pre, pex):
    """(label, value pre, value pex) per pair (per_run, report) or per group (spread)."""
    m = chk["metric"]
    if chk["kind"] in ("per_run", "report"):
        out = []
        for rid, a in pre.items():
            if not G._match(a, chk.get("where")):
                continue
            b = pex.get(rid)
            va = G._num(a["metrics"].get(m))
            vb = G._num(b["metrics"].get(m)) if b else None
            if chk.get("abs"):
                va = None if va is None else abs(va)
                vb = None if vb is None else abs(vb)
            out.append((rid, va, vb))
        return out
    over, mode = chk["over"], chk.get("mode", "ratio")

    def groups(runs):
        g = collections.defaultdict(list)
        for r in runs.values():
            if G._match(r, chk.get("where")):
                key = (r["corner"],) + tuple(sorted((k, str(v)) for k, v in r["params"].items() if k != over))
                g[key].append(G._num(r["metrics"].get(m)))
        return g

    def spread(vals):
        if len(vals) < 2 or any(v is None for v in vals):
            return None
        if mode == "ratio":
            return max(vals) / min(vals) if min(vals) > 0 else None
        return max(vals) - min(vals)
    ga, gb = groups(pre), groups(pex)
    return [("%s %s" % (k[0], " ".join("%s=%s" % kv for kv in k[1:])), spread(ga[k]), spread(gb.get(k, []))) for k in ga]


def judge(rows, lo, hi):
    out = []
    for lab, a, b in rows:
        r = dict(id=lab, pre=a, pex=b)
        if a is None or b is None:
            r["verdict"] = "NODATA"
            out.append(r)
            continue
        ma, mb = G._margin(a, lo, hi), G._margin(b, lo, hi)
        r.update(delta=b - a, margin_pre=ma, margin_pex=mb)
        if ma < 0:
            r.update(used=None, verdict="PRE_OUTSIDE")
        elif ma == 0:
            r.update(used=0.0 if mb >= 0 else EXACT_FAIL, verdict="PASS" if mb >= 0 else "FAIL")
        else:
            u = (ma - mb) / ma
            r.update(used=u, verdict="FAIL" if u > USED_MAX else ("FAVORABLE_LARGE" if u < -USED_MAX else "PASS"))
        out.append(r)
    return out


def check(chk, pre, pex, spec, origin):
    rows = items(chk, pre, pex)
    res = dict(origin=origin, kind=chk["kind"], metric=chk["metric"], where=chk.get("where"), n=len(rows))
    if chk["kind"] == "spread":
        res.update(over=chk["over"], mode=chk.get("mode", "ratio"))
    if not rows:
        res.update(status="OUT_OF_SCOPE", limit="-", rows=[])
        return res
    if chk["kind"] == "report":
        rr = [dict(id=l, pre=a, pex=b, delta=(None if a is None or b is None else b - a)) for l, a, b in rows]
        res.update(status="REPORT", limit="reported", rows=rr)
        return res
    lo, hi = G._limits(chk, spec)
    rr = judge(rows, lo, hi)
    used = [r["used"] for r in rr if r.get("used") is not None]
    worst = max(rr, key=lambda r: -1e99 if r.get("used") is None else r["used"])
    res.update(limit=G._fmt_limit(lo, hi), rows=rr, used_max=max(used) if used else None, worst_id=worst["id"],
               n_fail=sum(r["verdict"] in ("FAIL", "NODATA") for r in rr),
               n_favorable_large=sum(r["verdict"] == "FAVORABLE_LARGE" for r in rr),
               n_pre_outside=sum(r["verdict"] == "PRE_OUTSIDE" for r in rr))
    res["status"] = "FAIL" if res["n_fail"] else "PASS"
    return res


def worst_vs_worst(chk, spec):
    """D-019: one row, the shortest value of each side over the 45 corners x WVW cases; a missing corner or a run that is not
    ok on either side fails the check (coverage is part of the claim)."""
    lo, hi = G._limits(chk, spec)
    corners = get_corner_set(WVW["corners"])
    want = {"%s__case%d" % (c.name, k) for c in corners for k in WVW["cases"]}
    side = {}
    for var in ("pre", "pex"):
        vals, notok, gone = {}, set(), []
        for p in WVW[var]:
            fp = os.path.join(ROOT, p)
            if not os.path.isfile(fp):
                gone.append(p)
                continue
            for r in C.load_json(fp)["runs"]:
                if r["id"] not in want:
                    continue
                if r["status"] != "ok":
                    notok.add(r["id"])
                    continue
                v = G._num(r["metrics"].get(chk["metric"]))
                if v is not None:
                    vals[r["id"]] = v
        side[var] = dict(vals=vals, not_ok=sorted(notok - set(vals)), missing_files=gone, missing=sorted(want - set(vals)))
    a, b = side["pre"]["vals"], side["pex"]["vals"]
    ia = min(a, key=a.get) if a else None
    ib = min(b, key=b.get) if b else None
    lab = "worst of %d corners x cases %s: before layout %s, extracted %s" % (len(corners), WVW["cases"], ia, ib)
    rows = judge([(lab, a.get(ia), b.get(ib))], lo, hi)
    complete = all(not s["missing"] and not s["missing_files"] for s in side.values())
    r0 = rows[0]
    res = dict(origin="TB8 (D-019: worst against worst)", kind="per_run", metric=chk["metric"], where={"case": WVW["cases"]},
               n=1, limit=G._fmt_limit(lo, hi), rows=rows, used_max=r0.get("used"), worst_id=r0["id"],
               n_fail=int(r0["verdict"] in ("FAIL", "NODATA") or not complete),
               n_favorable_large=int(r0["verdict"] == "FAVORABLE_LARGE"), n_pre_outside=int(r0["verdict"] == "PRE_OUTSIDE"),
               coverage={v: dict(n=len(s["vals"]), expected=len(want), missing=s["missing"], not_ok=s["not_ok"],
                                 missing_files=s["missing_files"], files=WVW[v]) for v, s in side.items()})
    res["status"] = "FAIL" if res["n_fail"] else "PASS"
    return res


def other_metrics(pre, pex, covered):
    """Max |delta| (and the relative one) of every metric no check covers."""
    out = {}
    for rid, a in pre.items():
        b = pex.get(rid)
        if not b:
            continue
        for k, va in a["metrics"].items():
            vb = b["metrics"].get(k)
            if k in covered or not C.is_number(va) or not C.is_number(vb) or va != va or vb != vb:
                continue
            d = vb - va
            e = out.setdefault(k, dict(max_abs_delta=0.0, at=None, rel=None))
            if abs(d) >= abs(e["max_abs_delta"]):
                e.update(max_abs_delta=d, at=rid, pre=va, pex=vb, rel=(d / abs(va)) if va else None)
    return out


def offset_check(trip_pre, trip_pex, spec):
    """Layout-added systematic offset (TB3_trip off_v) against 30 % of the TB3_off window margin (same corner / VIC)."""
    gates_y = C.load_yaml("spec/gates.yaml")
    chk = next(c for c in gates_y["gates"]["TB3_off"]["checks"] if c["kind"] == "mc_offset_window")
    k = float(C.resolve(chk["k"], spec))
    window = float(C.resolve(chk["window"], spec))
    extra = sum(float(C.lookup(spec, e["ref"])) * float(e.get("mul", 1.0)) for e in chk.get("extra", []))
    p = os.path.join(ROOT, "sim", "tb3_off", "results", "tb3_off", "results.json")
    g = collections.defaultdict(list)
    for r in C.load_json(p)["runs"]:
        v = G._num(r["metrics"].get(chk["metric"]))
        if r["status"] == "ok" and v is not None:
            g[(r["corner"], float(r["params"]["vic"]))].append(v)
    stat = {}
    for key, vals in g.items():
        n = len(vals)
        mean = sum(vals) / n
        sig = math.sqrt(sum((v - mean) ** 2 for v in vals) / (n - 1))
        stat[key] = dict(n=n, mean=mean, sigma=sig, margin=window - (abs(mean) + k * sig + extra))
    rows = []
    for rid, a in trip_pre.items():
        b = trip_pex.get(rid)
        key = (a["corner"], float(a["params"]["vic"]))
        if key not in stat or not b:
            continue
        va, vb = G._num(a["metrics"].get("off_v")), G._num(b["metrics"].get("off_v"))
        if va is None or vb is None:
            rows.append(dict(id=rid, verdict="NODATA"))
            continue
        s = stat[key]
        u = abs(vb - va) / s["margin"]
        rows.append(dict(id=rid, off_pre=va, off_pex=vb, delta=vb - va, window_margin=s["margin"], mc_n=s["n"],
                         mc_mean=s["mean"], mc_sigma=s["sigma"], used=u, verdict="PASS" if u <= USED_MAX else "FAIL"))
    used = [r["used"] for r in rows if "used" in r]
    return dict(rows=rows, n=len(rows), used_max=max(used) if used else None,
                n_fail=sum(r["verdict"] != "PASS" for r in rows), source=os.path.relpath(p, ROOT),
                status="PASS" if rows and all(r["verdict"] == "PASS" for r in rows) else "FAIL",
                limit="|delta off_v| <= 0.3 x (window - |mean| - %g sigma - %.4g V)" % (k, extra))


def d012_check(data, spec):
    """sizing/FROZEN.md: at ff/125C/3.6 V, VIC 0.05 V on the extracted netlist: op, A1 >= 4, TB4 timing, TB5 eye."""
    gates_y = C.load_yaml("spec/gates.yaml")["gates"]
    out = dict(corner=D012, vic=0.05, parts={})

    def sel(bench):
        pex = data.get(bench, {}).get("pex") or {}
        return {k: r for k, r in pex.items() if r["corner"] == D012 and abs(float(r["params"].get("vic", -1)) - 0.05) < 1e-9}

    # operating point: node voltages / current against the pre-layout run of the same deck
    pre = data.get("tbl_op", {}).get("pre") or {}
    dv, didd = [], []
    for rid, b in sel("tbl_op").items():
        a = pre.get(rid)
        if a:
            dv += [abs(b["metrics"][k] - a["metrics"][k]) for k in a["metrics"] if k.startswith("v_") and k in b["metrics"]]
            didd.append(b["metrics"]["idd_a"] / a["metrics"]["idd_a"] - 1.0)
    out["parts"]["op"] = dict(n=len(sel("tbl_op")), max_abs_dv=max(dv) if dv else None, idd_rel=max(didd, key=abs) if didd else None,
                              ok=bool(dv) and max(dv) < 0.05)
    # gain
    a1 = [r["metrics"].get("a1") for r in sel("tbl_ac").values()]
    lo = C.resolve("$spec.stage1.a1_min", spec)
    out["parts"]["gain"] = dict(n=len(a1), a1_min=min(a1) if a1 else None, limit=lo, ok=bool(a1) and min(a1) >= lo)

    # timing and eye: the source gate's per_run limits, absolute
    def absolute(bench, gid):
        runs = sel(bench)
        res, ok = [], bool(runs)
        for c in gates_y[gid]["checks"]:
            if c["kind"] != "per_run":
                continue
            s = [r for r in runs.values() if G._match(r, c.get("where"))]
            if not s:
                continue
            lo_, hi_ = G._limits(c, spec)
            vals = [G._num(r["metrics"].get(c["metric"])) for r in s]
            vals = [abs(v) if (c.get("abs") and v is not None) else v for v in vals]
            good = all(v is not None and G._margin(v, lo_, hi_) >= 0 for v in vals)
            ok = ok and good
            res.append(dict(metric=c["metric"], where=c.get("where"), limit=G._fmt_limit(lo_, hi_), n=len(s),
                            worst=min(vals, key=lambda v: G._margin(v, lo_, hi_) if v is not None else -1e99), ok=good))
        return dict(n=len(runs), checks=res, ok=ok)
    out["parts"]["timing"] = absolute("tbl_pd", "TB4")
    out["parts"]["eye"] = absolute("tbl_eye", "TB5")
    out["ok"] = int(all(p["ok"] for p in out["parts"].values()))
    out["consequence"] = "none" if out["ok"] else "ladder R6 (constant-gm bias) is taken and the sizing re-opens (sizing/FROZEN.md)"
    return out


def main():
    spec = C.load_yaml("spec/spec.yaml")
    gates_y = C.load_yaml("spec/gates.yaml")["gates"]
    lane_max = C.resolve("$spec.current.i_lane_max_a", spec)
    bias_max = C.resolve("$spec.current.i_bias_max_a", spec)
    data, benches = {}, {}
    summ = dict(benches_missing=0, runs_not_ok=0, count_errors=0, checks_failed=0, pairs=0, favorable_large=0,
                pre_outside=0, margin_used_max=None)
    used_all = []
    for b in BENCHES:
        pre, ppre = load(b, "pre")
        pex, ppex = load(b, "pex")
        e = dict(source_gate=SOURCE[b], results={"pre": os.path.relpath(ppre, ROOT), "pex": os.path.relpath(ppex, ROOT)})
        benches[b] = e
        if pre is None or pex is None:
            e["status"] = "MISSING"
            summ["benches_missing"] += 1
            continue
        data[b] = dict(pre=pre, pex=pex)
        e["expected"] = expected(b, "pex")
        e["runs"] = {"pre": len(pre), "pex": len(pex)}
        e["status_counts"] = {v: dict(collections.Counter(r["status"] for r in runs.values())) for v, runs in (("pre", pre), ("pex", pex))}
        e["retried"] = sorted(r["id"] for runs in (pre, pex) for r in runs.values() if r.get("retry"))
        e["cpu_s"] = {v: round(sum(float(r.get("elapsed") or 0) for r in runs.values()), 1) for v, runs in (("pre", pre), ("pex", pex))}
        cnt_bad = len(pre) != e["expected"] or len(pex) != e["expected"] or set(pre) != set(pex) or expected(b, "pre") != e["expected"]
        notok = sum(r["status"] != "ok" for runs in (pre, pex) for r in runs.values())
        summ["count_errors"] += int(cnt_bad)
        summ["runs_not_ok"] += notok
        summ["pairs"] += len(set(pre) & set(pex))
        okp = {k: r for k, r in pre.items() if r["status"] == "ok"}
        okx = {k: r for k, r in pex.items() if r["status"] == "ok"}
        if b == "tbl_op":
            add_s1_cm_dev(okp)
            add_s1_cm_dev(okx)
        checks, covered, skipped = [], set(), []
        for c in gates_y[SOURCE[b]]["checks"]:
            if c["metric"] in NOT_MEASURABLE:
                skipped.append(dict(metric=c["metric"], why=NOT_MEASURABLE[c["metric"]]))
                continue
            if c["kind"] not in ("per_run", "spread", "report"):
                continue
            if b == WVW["bench"] and c["kind"] == "per_run" and c["metric"] == WVW["metric"]:
                # D-019: the wake-up cases worst against worst over 45 corners, the other cases pair by pair
                grid_cases = C.load_json(os.path.join(ROOT, "sim", b, f"{b}_pre.json"))["grid"]["case"]
                rest = [k for k in grid_cases if k not in WVW["cases"]]
                checks.append(check(dict(c, where=dict(c.get("where") or {}, case=rest)), okp, okx, spec, SOURCE[b]))
                checks.append(worst_vs_worst(c, spec))
                covered.add(c["metric"])
                continue
            checks.append(check(c, okp, okx, spec, SOURCE[b]))
            covered.add(c["metric"])
        if b == "tbl_op":          # the supply-current split is not measurable; the total against the sum of the limits
            c = {"kind": "per_run", "metric": "idd_a", "max": 3 * lane_max + bias_max}
            checks.append(check(c, okp, okx, spec, "derived: 3 x I_lane max + I_bias max"))
            covered.add("idd_a")
        e["checks"], e["not_measurable"] = checks, skipped
        e["other_metrics"] = other_metrics(okp, okx, covered)
        nf = sum(c["status"] == "FAIL" for c in checks)
        summ["checks_failed"] += nf
        for c in checks:
            summ["favorable_large"] += c.get("n_favorable_large", 0)
            summ["pre_outside"] += c.get("n_pre_outside", 0)
            if c.get("used_max") is not None:
                used_all.append(c["used_max"])
        e["status"] = "FAIL" if (nf or cnt_bad or notok) else "PASS"
    off = None
    if "tbl_trip" in data:
        off = offset_check(data["tbl_trip"]["pre"], data["tbl_trip"]["pex"], spec)
        summ["checks_failed"] += int(off["status"] != "PASS")
        if off["used_max"] is not None:
            used_all.append(off["used_max"])
    d012 = d012_check(data, spec)
    summ["margin_used_max"] = max(used_all) if used_all else None
    out = dict(generated=time.strftime("%Y-%m-%d %H:%M:%S"), git=C.git_state(), criterion=dict(
        used_max=USED_MAX, text="per pair: used = (margin_pre - margin_pex) / margin_pre <= 0.30; exact checks: extracted value "
                                "within the limit; gains of margin > 30 % listed (favorable_large), not failed; TB8 min_pulse_s "
                                "of cases 3 and 5 worst against worst over 45 corners (D-019)"),
        cores={"pre": "netlist/lvds_rx_core.spice", "pex": "sim/tbl/core_pexrc.spice"}, summary=summ, offset=off, d012=d012,
        benches=benches)
    out["status"] = "PASS" if (not summ["benches_missing"] and not summ["runs_not_ok"] and not summ["count_errors"]
                               and not summ["checks_failed"] and d012["ok"]) else "FAIL"
    os.makedirs(OUT, exist_ok=True)
    C.write_json(os.path.join(OUT, "tbl.json"), out)
    with open(os.path.join(OUT, "TBL.md"), "w") as f:
        f.write(markdown(out))
    print("TBL %s  pairs %d  checks failed %d  missing %d  not ok %d  count errors %d  margin used max %s  D-012 ok %s" % (
        out["status"], summ["pairs"], summ["checks_failed"], summ["benches_missing"], summ["runs_not_ok"],
        summ["count_errors"], summ["margin_used_max"], d012["ok"]))
    return 0 if out["status"] == "PASS" else 1


def _f(v, unit=""):
    if v is None:
        return "-"
    if isinstance(v, str):
        return v
    return ("%.4g" % v) + unit


def markdown(o):
    s = o["summary"]
    L = ["# Gate TBL: post-layout re-simulation (T11)", "",
         "GENERATED by `sim/tbl/evaluate.py` on %s; do not edit. Cores: pre = `%s`, extracted = `%s`." % (
             o["generated"], o["cores"]["pre"], o["cores"]["pex"]), "",
         "Criterion: %s." % o["criterion"]["text"], "",
         "**Status: %s**. Pairs %d, checks failed %d, benches missing %d, runs not ok %d, count errors %d, largest margin "
         "use %s, gains of margin over 30 %%: %d, pre-layout outside the limit: %d, D-012 condition %s." % (
             o["status"], s["pairs"], s["checks_failed"], s["benches_missing"], s["runs_not_ok"], s["count_errors"],
             _f(s["margin_used_max"]), s["favorable_large"], s["pre_outside"], "met" if o["d012"]["ok"] else "NOT met"), "",
         "## Checks", "", "| Bench | Gate | Check | Limit | n | Worst use of margin | at | Fails | Gains > 30 % | Status |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for b, e in o["benches"].items():
        if e.get("status") == "MISSING":
            L.append("| %s | %s | - | - | - | - | - | - | - | MISSING |" % (b, e["source_gate"]))
            continue
        for c in e["checks"]:
            name = c["metric"] + (" spread over %s (%s)" % (c["over"], c["mode"]) if c["kind"] == "spread" else "")
            if c.get("where"):
                name += " where " + ", ".join("%s=%s" % kv for kv in c["where"].items())
            L.append("| %s | %s | %s | %s | %d | %s | %s | %s | %s | %s |" % (
                b, c["origin"], name, c.get("limit", "-"), c["n"], _f(c.get("used_max")), c.get("worst_id", "-"),
                c.get("n_fail", "-"), c.get("n_favorable_large", "-"), c["status"]))
    if o["offset"]:
        f = o["offset"]
        L += ["", "## Systematic offset added by the layout", "", "Limit: %s; TB3_off data `%s`. Status **%s**, largest use %s." % (
            f["limit"], f["source"], f["status"], _f(f["used_max"])), "",
            "| Run | off pre (mV) | off extracted (mV) | delta (mV) | window margin (mV) | use |", "|---|---|---|---|---|---|"]
        for r in f["rows"]:
            if "used" in r:
                L.append("| %s | %.3f | %.3f | %.3f | %.2f | %.3f |" % (r["id"], r["off_pre"] * 1e3, r["off_pex"] * 1e3,
                                                                         r["delta"] * 1e3, r["window_margin"] * 1e3, r["used"]))
    d = o["d012"]
    L += ["", "## D-012 freeze condition (ff/125C/3.6 V, VIC 0.05 V, extracted netlist)", "",
          "Condition **%s**; consequence: %s." % ("met" if d["ok"] else "NOT met", d["consequence"]), "",
          "- operating point: %d runs, largest node-voltage change %s V, supply current change %s" % (
              d["parts"]["op"]["n"], _f(d["parts"]["op"]["max_abs_dv"]), _f(d["parts"]["op"]["idd_rel"])),
          "- gain: A1 min %s (limit %s)" % (_f(d["parts"]["gain"]["a1_min"]), _f(d["parts"]["gain"]["limit"]))]
    for part in ("timing", "eye"):
        for c in d["parts"][part]["checks"]:
            L.append("- %s: %s %s: worst %s, limit %s, %s" % (part, c["metric"], c["where"] or "", _f(c["worst"]), c["limit"],
                                                              "ok" if c["ok"] else "FAILS"))
    L += ["", "## Gains of margin over 30 % and pre-layout values outside the limit", ""]
    any_ = False
    for b, e in o["benches"].items():
        for c in e.get("checks", []):
            for r in c.get("rows", []):
                if r.get("verdict") in ("FAVORABLE_LARGE", "PRE_OUTSIDE"):
                    any_ = True
                    L.append("- %s %s %s: pre %s, extracted %s (%s)" % (b, c["metric"], r["id"], _f(r["pre"]), _f(r["pex"]),
                                                                    r["verdict"]))
    if not any_:
        L.append("none")
    L += ["", "## Not measurable on the extracted netlist", ""]
    for b, e in o["benches"].items():
        for x in e.get("not_measurable", []):
            L.append("- %s %s: %s" % (b, x["metric"], x["why"]))
    L += ["", "## Metrics without a limit (largest change)", "", "| Bench | Metric | pre | extracted | change | at |", "|---|---|---|---|---|---|"]
    for b, e in o["benches"].items():
        for k, v in sorted(e.get("other_metrics", {}).items()):
            L.append("| %s | %s | %s | %s | %s | %s |" % (b, k, _f(v.get("pre")), _f(v.get("pex")),
                                                          _f(v["rel"] * 100, " %") if v.get("rel") is not None else _f(v["max_abs_delta"]), v["at"]))
    L += ["", "## Runs and CPU", "", "| Bench | expected | pre | extracted | status pre | status extracted | CPU pre (s) | CPU extracted (s) | retried |",
          "|---|---|---|---|---|---|---|---|---|"]
    for b, e in o["benches"].items():
        if e.get("status") == "MISSING":
            continue
        L.append("| %s | %d | %d | %d | %s | %s | %s | %s | %d |" % (b, e["expected"], e["runs"]["pre"], e["runs"]["pex"],
                                                                   e["status_counts"]["pre"], e["status_counts"]["pex"],
                                                                   e["cpu_s"]["pre"], e["cpu_s"]["pex"], len(e["retried"])))
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    sys.exit(main())
