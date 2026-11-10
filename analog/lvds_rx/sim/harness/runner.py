"""runner.py -- render decks, run ngspice in parallel, parse .meas, cache, report.

Core entry points
    run_testbench(...)   -> list of run records (and writes results.json / results.csv)
    run_spec(path)       -> run_testbench driven by a JSON/YAML spec file, then summary.md

A deck TEMPLATE is plain SPICE.  `{name}` is replaced when `name` is a known variable:
    {header}      the corner header (with .temp), see corners.py
    {vdd} {temp}  numbers;  {corner} the corner name;  {process}
    {seed_line}   '.option seed=N' for Monte Carlo runs, '' otherwise;  {seed}
    {deck_dir}    absolute directory of the template (use it in .include paths)
    {run_dir}     absolute directory of this run (ngspice runs with it as working directory,
                  so `wrdata eye.txt ...` lands there)
    {anything}    every key of the parameter grid / spec "vars"
  A `{word}` that is not a known variable is left untouched (SPICE `{expr}` syntax is legal);
  the names are listed in the run log so a typo is visible.

Every run ends in exactly one status: ok | meas_failed | nonconverged | sim_error | timeout |
post_error.  Nothing is dropped silently.
"""
import concurrent.futures as cf
import csv
import hashlib
import itertools
import json
import os
import re
import signal
import subprocess
import sys
import time

import numpy as np

from . import corners as _corners
from . import mc as _mc

NGSPICE = os.environ.get("NGSPICE", "ngspice")
HARNESS_VERSION = "1.1"   # 1.1: .option wnflag=1 in the header, cross corners, record carries `res`

ERR_NONCONV = [r"no convergence", r"singular matrix", r"timestep too small", r"iteration limit reached",
               r"gmin stepping failed", r"source stepping failed", r"convergence problem"]
ERR_GENERIC = [r"^\s*error", r"fatal", r"unable to find definition", r"undefined parameter",
               r"could not find", r"simulation\(s\) aborted", r"no such vector", r"can't find",
               r"unknown subckt", r"unknown model", r"unrecognized parameter", r"doanalyses:"]


# --------------------------------------------------------------------------- helpers
def _sha(*chunks):
    h = hashlib.sha256()
    for c in chunks:
        h.update(c if isinstance(c, bytes) else str(c).encode())
        h.update(b"\x00")
    return h.hexdigest()


def ngspice_version(ngspice=NGSPICE):
    try:
        r = subprocess.run([ngspice, "--version"], capture_output=True, text=True, timeout=20)
        m = re.search(r"ngspice-?\s*([0-9.]+)", r.stdout + r.stderr)
        return m.group(1) if m else (r.stdout + r.stderr).strip()[:40]
    except Exception as e:  # pragma: no cover
        return "unknown(%s)" % e


def _fmt(v):
    if isinstance(v, float):
        return repr(v)
    return str(v)


def render(template, variables):
    """Substitute {name} for known names.  Returns (text, unresolved_names)."""
    unresolved = []

    def repl(m):
        n = m.group(1)
        if n in variables:
            return _fmt(variables[n])
        unresolved.append(n)
        return m.group(0)

    # comment lines (first non-blank character '*') are copied verbatim: a {header} mentioned
    # in a comment must not expand into a multi-line header
    lines = [ln if ln.lstrip().startswith("*") else re.sub(r"\{(\w+)\}", repl, ln)
             for ln in template.split("\n")]
    return "\n".join(lines), sorted(set(unresolved))


_INC = re.compile(r"^\s*\.(?:include|inc|lib)\s+['\"]?([^\s'\"]+)", re.I | re.M)


def _dep_hashes(deck_text, search_dirs):
    out = []
    for p in _INC.findall(deck_text):
        cands = [p] if os.path.isabs(p) else [os.path.join(d, p) for d in search_dirs]
        for c in cands:
            if os.path.isfile(c) and not c.startswith("/foss/pdks"):
                with open(c, "rb") as f:
                    out.append((c, hashlib.sha256(f.read()).hexdigest()))
                break
    return out


def expected_measures(deck_text):
    """Names of every .meas / control-block `meas` in the deck (what must show up in the log)."""
    names = []
    for ln in deck_text.splitlines():
        s = ln.strip()
        if not s or s.startswith("*") or s.startswith("$"):
            continue
        m = re.match(r"\.?meas(?:ure)?\s+(?:ac|dc|tran|op|sp|noise|disto)\s+(\w+)", s, re.I)
        if m:
            names.append(m.group(1).lower())
    return list(dict.fromkeys(names))


def lint_deck(text):
    """Raise ValueError for the one pattern that silently loses results in ngspice 46 batch mode:
    two or more analysis directives (.dc/.tran/.ac/...) at deck level together with `.meas`.
    Measured: `.dc` then `.tran` -> the tran .meas fail with 'no such vector'; `.tran` then `.dc`
    -> the dc .meas vanish.  Put several analyses inside a `.control ... .endc` block
    (`dc ...`, `meas dc ...`, `tran ...`, `meas tran ...`), which works."""
    in_ctl, n, has_meas = False, 0, False
    for ln in text.splitlines():
        s = ln.strip().lower()
        if s.startswith(".control"):
            in_ctl = True
        elif s.startswith(".endc"):
            in_ctl = False
        elif not in_ctl and not s.startswith(("*", "$")):
            if re.match(r"\.(dc|tran|ac|noise|tf|disto|pz|sens)\b", s):
                n += 1
            if s.startswith(".meas"):
                has_meas = True
    if n > 1 and has_meas:
        raise ValueError("deck has %d analysis directives plus .meas: ngspice 46 batch mode loses the "
                         "measurements of all but one analysis.  Use one analysis per deck, or a "
                         ".control block with `meas` commands (see README)." % n)


_NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"


def parse_log(text, expected):
    """Parse the ngspice log: (measures dict, extra RESULT dict, failed_meas list, errors list, nonconv bool)."""
    meas, failed = {}, []
    extra = {}
    for ln in text.splitlines():
        m = re.match(r"^\s*(\w+)\s*=\s*(%s|failed)\b" % _NUM, ln, re.I)
        if m and m.group(1).lower() in expected:
            n = m.group(1).lower()
            if m.group(2).lower() == "failed":
                failed.append(n)
                meas[n] = float("nan")
            elif n not in meas or np.isnan(meas[n]):
                meas[n] = float(m.group(2))     # first printed value wins
            continue
        m = re.match(r"^\s*\.?meas\w*\s+\w+\s+(\w+)\b.*\bfailed", ln, re.I)   # '.meas tran x ... failed!'
        if m and m.group(1).lower() in expected and m.group(1).lower() not in failed:
            failed.append(m.group(1).lower())
            meas.setdefault(m.group(1).lower(), float("nan"))
            continue
        m = re.match(r"^\s*RESULT\s+(\w+)\s+(%s)\s*$" % _NUM, ln)
        if m:
            extra[m.group(1).lower()] = float(m.group(2))
    errors, nonconv = [], False
    for ln in text.splitlines():
        low = ln.lower()
        if any(re.search(p, low) for p in ERR_NONCONV):
            nonconv = True
            errors.append(ln.strip()[:200])
        elif any(re.search(p, low) for p in ERR_GENERIC):
            errors.append(ln.strip()[:200])
    return meas, extra, failed, list(dict.fromkeys(errors)), nonconv


# ----------------------------------------------------------------------------- one run
def _execute(run, ngspice, timeout, force):
    run_dir = run["run_dir"]
    os.makedirs(run_dir, exist_ok=True)
    res_path = os.path.join(run_dir, "result.json")
    if not force and os.path.isfile(res_path):
        try:
            with open(res_path) as f:
                old = json.load(f)
            if old.get("hash") == run["hash"] and old.get("status") != "timeout":
                old["cached"] = True
                return old
        except Exception:
            pass
    with open(os.path.join(run_dir, "deck.spice"), "w") as f:
        f.write(run["deck"])
    for fn, content in run["files"].items():
        with open(os.path.join(run_dir, fn), "w") as f:
            f.write(content)
    for stale in ("result.json", "ngspice.log"):
        p = os.path.join(run_dir, stale)
        if os.path.exists(p):
            os.remove(p)
    t0 = time.time()
    status, rc, errors, nonconv = "ok", None, [], False
    log_path = os.path.join(run_dir, "ngspice.log")
    # ngspice is OpenMP-built.  With 2+ processes at once the default spin-waiting threads made a
    # 0.1 s run take 3-10 s (load average 23), and OMP_NUM_THREADS=1 alone did NOT cure it
    # (measured, log/sim_harness.md).  OMP_THREAD_LIMIT=1 / OMP_WAIT_POLICY=PASSIVE do.
    env = dict(os.environ, OMP_NUM_THREADS="1", OMP_THREAD_LIMIT="1", OMP_WAIT_POLICY="PASSIVE")
    p = subprocess.Popen([ngspice, "-b", "-o", "ngspice.log", "deck.spice"], cwd=run_dir, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
    try:
        so, _ = p.communicate(timeout=timeout)
        rc = p.returncode
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        so, _ = p.communicate()
        status = "timeout"
        errors.append("killed after %.0f s timeout" % timeout)
    elapsed = time.time() - t0
    text = so or ""
    if os.path.isfile(log_path):
        with open(log_path, errors="replace") as f:
            text += "\n" + f.read()
    with open(os.path.join(run_dir, "ngspice.log"), "w") as f:
        f.write(text)
    meas, extra, failed, errs, nonconv = parse_log(text, run["expected"])
    errors += errs
    # "Error: measure ..." lines are measurement failures (reported as meas_failed below), not netlist/simulator errors
    fatal = [e for e in errs if not re.match(r"error:?\s+measure", e.lower())]
    measures = dict(meas)
    measures.update(extra)
    missing = [n for n in run["expected"] if n not in meas]
    if status != "timeout":
        if nonconv:
            status = "nonconverged"
        elif fatal or (rc not in (0, None)):
            status = "sim_error"
            if rc not in (0, None):
                errors.append("ngspice exit code %s" % rc)
        elif failed or missing:
            status = "meas_failed"
            if failed:
                errors.append("measurement failed: " + ", ".join(failed))
            if missing:
                errors.append("measurement missing from log: " + ", ".join(missing))
    rec = {"hash": run["hash"], "status": status, "measures": measures, "errors": errors,
           "returncode": rc, "elapsed": round(elapsed, 3), "cached": False}
    with open(res_path, "w") as f:
        json.dump(rec, f, indent=1)
    return rec


# ---------------------------------------------------------------------- orchestration
def _safe(s):
    return re.sub(r"[^A-Za-z0-9_.+-]", "_", s)


def _expand_grid(grid):
    if not grid:
        return [{}]
    keys = list(grid)
    return [dict(zip(keys, vals)) for vals in itertools.product(*[grid[k] for k in keys])]


def build_runs(template, template_dir, work_dir, corners, grid, mc, extra_vars, prep, ngspice_ver):
    corner_list = _corners.get_corner_set(corners)
    mc = mc or {}
    mode = mc.get("mode", "mismatch") if mc else "none"
    seeds = [None]
    if mc:
        seeds = mc.get("seeds") or _mc.make_seeds(int(mc.get("n", 200)), int(mc.get("seed", 1)))
    expected = expected_measures(template)
    lint_deck(template)
    live = "\n".join(ln for ln in template.split("\n") if not ln.lstrip().startswith("*"))   # comments are not expanded
    if mc and "{seed_line}" not in live and "{seed}" not in live:
        # without it every seed renders the same deck: ngspice then draws a fresh RANDOM seed per process,
        # so the campaign is neither reproducible nor cache-safe (found in verification, 2026-11-10)
        raise ValueError("Monte Carlo requested but the deck template has neither {seed_line} nor {seed}; "
                         "put {seed_line} on its own line before the circuit")
    runs = []
    for c in corner_list:
        header = c.header(mc=mode)
        for params in _expand_grid(grid):
            for seed in seeds:
                rid = c.name
                if params:
                    rid += "__" + "_".join("%s%s" % (k, _fmt(v)) for k, v in params.items())
                if seed is not None:
                    rid += "__s%d" % seed
                rid = _safe(rid)
                if len(rid) > 110:
                    rid = rid[:90] + "_" + _sha(rid)[:10]
                run_dir = os.path.join(work_dir, rid)
                v = {"header": header, "vdd": c.vdd, "temp": c.temp, "corner": c.name, "process": c.process,
                     "seed_line": _mc.seed_line(seed) if seed is not None else "",
                     "seed": seed if seed is not None else 0,
                     "deck_dir": template_dir, "run_dir": run_dir}
                v.update(extra_vars or {})
                v.update(params)
                deck, unresolved = render(template, v)
                files = {}
                if prep:
                    files = prep({"run_dir": run_dir, "params": dict(params), "corner": c, "seed": seed, "vars": v}) or {}
                    # files may be referenced as {run_dir}/name; deck was rendered already
                deps = _dep_hashes(deck, [template_dir, run_dir])
                h = _sha(deck, ngspice_ver, json.dumps(sorted(files.items())), json.dumps(deps), HARNESS_VERSION)
                runs.append({"id": rid, "corner": c, "params": params, "seed": seed, "deck": deck,
                             "files": files, "run_dir": run_dir, "hash": h, "expected": expected,
                             "unresolved": unresolved})
    return runs


def run_testbench(template, work_dir, out_dir=None, corners="tt", grid=None, mc=None, jobs=3, timeout=300,
                  force=False, prep=None, post=None, extra_vars=None, template_dir=None, ngspice=NGSPICE,
                  verbose=True, dry_run=False):
    """Run every (corner x grid point x seed).  `template` is deck text.  Returns the records."""
    template_dir = os.path.abspath(template_dir or ".")
    work_dir = os.path.abspath(work_dir)
    os.makedirs(work_dir, exist_ok=True)
    ver = ngspice_version(ngspice)
    runs = build_runs(template, template_dir, work_dir, corners, grid, mc, extra_vars, prep, ver)
    if verbose:
        un = sorted({u for r in runs for u in r["unresolved"]})
        print("[harness] %d runs, ngspice %s, jobs=%d%s" % (len(runs), ver, jobs, "  (unresolved {names} left for SPICE: %s)" % un if un else ""),
              file=sys.stderr)
    if dry_run:
        for r in runs:
            os.makedirs(r["run_dir"], exist_ok=True)
            with open(os.path.join(r["run_dir"], "deck.spice"), "w") as f:
                f.write(r["deck"])
        return []
    results = {}
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=max(1, jobs)) as ex:
        futs = {ex.submit(_execute, r, ngspice, timeout, force): r for r in runs}
        done = 0
        for fu in cf.as_completed(futs):
            r = futs[fu]
            try:
                results[r["id"]] = fu.result()
            except Exception as e:  # runner bug or OS problem: report, never drop
                results[r["id"]] = {"hash": r["hash"], "status": "sim_error", "measures": {},
                                    "errors": ["harness exception: %r" % e], "returncode": None,
                                    "elapsed": 0.0, "cached": False}
            done += 1
            if verbose and (done % max(25, len(runs) // 10) == 0 or done == len(runs)):
                print("[harness] %d/%d done (%.0f s)" % (done, len(runs), time.time() - t0), file=sys.stderr)
    records = []
    for r in runs:
        rr = results[r["id"]]
        metrics = dict(rr["measures"])
        status, errors = rr["status"], list(rr["errors"])
        if post and status == "ok":
            try:
                add = post({"run_dir": r["run_dir"], "params": dict(r["params"]), "corner": r["corner"],
                            "seed": r["seed"], "measures": dict(rr["measures"]),
                            "vars": dict(extra_vars or {}, **r["params"])}) or {}
                metrics.update({k: float(x) for k, x in add.items()})
            except Exception as e:
                status = "post_error"
                errors.append("post-processing raised %r" % (e,))
        records.append({"id": r["id"], "corner": r["corner"].name, "process": r["corner"].process,
                        "temp": r["corner"].temp, "vdd": r["corner"].vdd, "res": r["corner"].res, "params": r["params"],
                        "seed": r["seed"], "status": status, "metrics": metrics, "errors": errors,
                        "elapsed": rr["elapsed"], "cached": rr["cached"], "hash": rr["hash"],
                        "run_dir": os.path.relpath(r["run_dir"], out_dir or work_dir)})
    if out_dir:
        write_results(records, out_dir, ver)
    return records


def write_results(records, out_dir, ngspice_ver=""):
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "results.json"), "w") as f:
        json.dump({"harness": HARNESS_VERSION, "ngspice": ngspice_ver, "runs": records}, f, indent=1,
                  default=lambda o: None if (isinstance(o, float) and np.isnan(o)) else str(o))
    pk = sorted({k for r in records for k in r["params"]})
    mk = sorted({k for r in records for k in r["metrics"]})
    with open(os.path.join(out_dir, "results.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "corner", "process", "temp", "vdd"] + pk + ["seed", "status"] + mk)
        for r in records:
            w.writerow([r["id"], r["corner"], r["process"], r["temp"], r["vdd"]] +
                       [r["params"].get(k, "") for k in pk] + ["" if r["seed"] is None else r["seed"], r["status"]] +
                       [("%.9g" % r["metrics"][k]) if k in r["metrics"] else "" for k in mk])


# ---------------------------------------------------------------------------- spec level
def _load_hook(spec_dir, ref):
    """'file.py:func' (relative to the spec) or 'module:func' -> callable."""
    if not ref:
        return None
    path, func = ref.rsplit(":", 1)
    import importlib.util
    full = path if os.path.isabs(path) else os.path.join(spec_dir, path)
    if os.path.isfile(full):
        sp = importlib.util.spec_from_file_location("hook_" + _safe(os.path.basename(full)), full)
        mod = importlib.util.module_from_spec(sp)
        sys.path.insert(0, os.path.dirname(full))
        sp.loader.exec_module(mod)
    else:
        import importlib
        mod = importlib.import_module(path)
    return getattr(mod, func)


def load_spec(path):
    with open(path) as f:
        txt = f.read()
    if path.endswith((".yaml", ".yml")):
        import yaml  # optional dependency, JSON needs nothing
        return yaml.safe_load(txt)
    return json.loads(txt)


def run_spec(spec_path, jobs=None, force=False, dry_run=False, only_corners=None, n_mc=None, verbose=True):
    """One-line launch: run the testbench described by a spec file, write results + summary.md.
    Returns (records, summary_path)."""
    from . import report
    spec_path = os.path.abspath(spec_path)
    sd = os.path.dirname(spec_path)
    spec = load_spec(spec_path)
    name = spec.get("name") or os.path.splitext(os.path.basename(spec_path))[0]
    deck_path = os.path.join(sd, spec["deck"])
    with open(deck_path) as f:
        template = f.read()
    out_dir = os.path.join(sd, spec.get("out", "results/" + name))
    mc = dict(spec["mc"]) if spec.get("mc") else None
    if mc and n_mc:
        mc["n"] = n_mc
        mc.pop("seeds", None)
    corners = only_corners or spec.get("corners", "tt")
    records = run_testbench(template, os.path.join(out_dir, "work"), out_dir, corners=corners,
                            grid=spec.get("grid"), mc=mc, jobs=jobs or spec.get("jobs", 3),
                            timeout=spec.get("timeout", 300), force=force, dry_run=dry_run,
                            prep=_load_hook(sd, spec.get("prep")), post=_load_hook(sd, spec.get("post")),
                            extra_vars=spec.get("vars"), template_dir=os.path.dirname(deck_path), verbose=verbose)
    if dry_run:
        return records, None
    summ = report.write_summary(records, spec, out_dir, name, mc)
    return records, summ
