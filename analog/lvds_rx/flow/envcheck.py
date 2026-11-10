#!/usr/bin/env python3
"""envcheck.py -- `make check`: observe the environment and write results/env.json (the data of the ENV gate).

    python3 flow/envcheck.py [--skip-layout]

Records: tool versions, LUT load test + selftest_gmid (296 checks), harness unit tests, lint, the OMP exports of
tools/cx, and the toy layout regression (layout/magic_flow/scripts/run_all.sh: Magic DRC, KLayout deck, strict LVS and
its negative control).  Nothing is assumed: a step that cannot run is written as such (ok = 0).
The layout regression rewrites the committed copies in layout/magic_flow/results/; they are snapshotted and restored.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402
import lint as L  # noqa: E402

# version probes only, no simulation is started here
VERSION_CMDS = {"ngspice": ["ngspice", "--version"], "python3": ["python3", "--version"], "make": ["make", "--version"],  # lint:allow-ngspice
                "magic": ["magic", "--version"], "klayout": ["klayout", "-v"], "openroad": ["openroad", "-version"],
                "sta": ["sta", "-version"], "iverilog": ["iverilog", "-V"], "yosys": ["yosys", "-V"],
                "netgen": None}


def run(cmd, timeout=60, **kw):
    t0 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL, cwd=C.ROOT, **kw)
        return p.returncode, p.stdout + p.stderr, time.time() - t0
    except subprocess.TimeoutExpired as e:
        return None, ((e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or "")), time.time() - t0
    except FileNotFoundError:
        return 127, "", 0.0


def tool_versions():
    pa = C.load_yaml("spec/paths.yaml")["tools"]
    out = {}
    for name in pa["required"] + pa["optional"]:
        p = shutil.which(name)
        ver = None
        if p and VERSION_CMDS.get(name):
            rc, txt, _ = run(VERSION_CMDS[name], timeout=30)
            lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
            ver = lines[0][:100] if lines else None
        out[name] = {"path": p, "version": ver, "present": bool(p)}
    try:
        import numpy, scipy, yaml, pygmid  # noqa: F401
        out["python_packages"] = {"numpy": numpy.__version__, "scipy": scipy.__version__, "pyyaml": yaml.__version__,
                                  "pygmid": getattr(pygmid, "__version__", "present")}
    except Exception as e:
        out["python_packages"] = {"error": repr(e)}
    return out


def lut_checks():
    rc, txt, sec = run([sys.executable, "sizing/selftest_gmid.py"], timeout=600)
    m = re.search(r"(\d+)/(\d+) checks passed", txt)
    passed, total = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
    selftest = {"passed": passed, "total": total, "failed": (total - passed) if m else 1, "rc": rc, "seconds": round(sec, 1)}
    load = {}
    try:
        sys.path.insert(0, C.path("sizing"))
        import gmid_gf180 as g
        r = g.size("nfet_03v3", gm=1e-3, gmid=12, L=0.5, VDS=1.0)
        load = {"vgs_v": float(r["VGS"]), "ft_hz": float(r["fT"]),
                "id_w_a_per_um": float(g.at_gmid("nfet_03v3", "ID_W", 12, 0.5, 1.0))}
    except Exception as e:
        load = {"error": repr(e)}
    return selftest, load


def harness_tests():
    rc, txt, sec = run([sys.executable, "-m", "unittest", "discover", "-s", "sim/harness/tests"], timeout=600)
    m = re.search(r"Ran (\d+) tests?", txt)
    run_n = int(m.group(1)) if m else 0
    fails = len(re.findall(r"^(FAIL|ERROR):", txt, re.M))
    ok = rc == 0 and "OK" in txt.splitlines()[-1] if txt.strip() else False
    return {"run": run_n, "failures": 0 if ok else max(fails, 1), "rc": rc, "seconds": round(sec, 1)}


def omp_check():
    want = {"OMP_NUM_THREADS": "1", "OMP_THREAD_LIMIT": "1", "OMP_WAIT_POLICY": "PASSIVE"}
    have = {k: os.environ.get(k) for k in want}
    text = open(C.path("tools", "cx")).read()
    in_script = all(re.search(r"export .*%s=%s" % (k, v), text) for k, v in want.items())
    return {"ok": int(have == want and in_script), "environment": have, "exports_in_tools_cx": in_script}


def layout_toy():
    res_dir = C.path("layout", "magic_flow", "results")
    snap = C.path(".scratch", "magic_results_snapshot")
    if os.path.isdir(snap):
        shutil.rmtree(snap)
    if os.path.isdir(res_dir):
        shutil.copytree(res_dir, snap)
    try:
        rc, txt, sec = run(["bash", "layout/magic_flow/scripts/run_all.sh"], timeout=900)
    finally:
        if os.path.isdir(snap):
            shutil.rmtree(res_dir, ignore_errors=True)
            shutil.copytree(snap, res_dir)
    summ = C.path("layout", "magic_flow", "work", "summary.txt")
    s = open(summ).read() if os.path.isfile(summ) else ""
    first = lambda pat: (re.search(pat, s).group(1) if re.search(pat, s) else None)  # noqa: E731
    d = {"magic_drc_mag": first(r"magic_drc_mag: MAGIC_DRC_TOTAL (\d+)"),
         "magic_drc_gds": first(r"magic_drc_gds: MAGIC_DRC_TOTAL (\d+)"),
         "klayout_main": first(r"KLAYOUT_DRC_MAIN (\d+)"),
         "klayout_antenna": first(r"KLAYOUT_DRC_ANTENNA (\d+)"),
         "lvs_unique": "LVS_RESULT: Circuits match uniquely (no property errors)" in s,
         "negative_control_not_clean": "LVS_RESULT: NOT CLEAN" in s,
         "total_wall_seconds": first(r"total_wall_seconds=(\d+)"), "rc": rc, "seconds": round(sec, 1)}
    d["ok"] = int(rc == 0 and d["magic_drc_mag"] == "0" and d["magic_drc_gds"] == "0" and d["klayout_main"] == "0"
                  and d["klayout_antenna"] == "0" and d["lvs_unique"] and d["negative_control_not_clean"])
    return d


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skip-layout", action="store_true", help="do not run the 40 s toy layout regression (ok = 0 then)")
    a = ap.parse_args(argv)
    env = {"generated": time.strftime("%Y-%m-%d %H:%M:%S"), "git": C.git_state(), "tools": tool_versions()}
    env["lut_selftest"], env["lut_load"] = lut_checks()
    env["harness_tests"] = harness_tests()
    env["omp"] = omp_check()
    lint = L.run_all()
    env["lint"] = {"failed": lint["failed"], "rules": {k: v["failed"] for k, v in lint["rules"].items()}}
    env["layout_toy"] = {"ok": 0, "skipped": True} if a.skip_layout else layout_toy()
    C.write_json("results/env.json", env)
    print("ENV lut_selftest %d/%d | lut_load %s | harness_tests run=%d failures=%d | omp ok=%d | lint failed=%d | layout_toy ok=%s" %
          (env["lut_selftest"]["passed"], env["lut_selftest"]["total"],
           {k: round(v, 4) for k, v in env["lut_load"].items() if isinstance(v, float)},
           env["harness_tests"]["run"], env["harness_tests"]["failures"], env["omp"]["ok"], env["lint"]["failed"],
           env["layout_toy"]["ok"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
