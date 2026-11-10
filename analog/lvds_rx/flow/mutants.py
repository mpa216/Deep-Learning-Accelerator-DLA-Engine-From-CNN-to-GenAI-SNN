#!/usr/bin/env python3
"""mutants.py -- gate mutation tests (PLAN_V2 5.2 item 2): a gate that cannot fail is not a gate.

    python3 flow/mutants.py [--only id1,id2]      -> results/mutants.json, exit 1 if any mutant survives

Each mutant has a CONTROL (the unbroken variant must pass the gate/rule, so a detection is not vacuous) and a MUTATION
(the broken variant must be caught, for the stated reason).  Mutants work in .scratch/mutants/ and never touch the
design files.  The real gate code (flow/gates.py) and rule code (flow/lint.py) are what is exercised.

Add a mutant in any module: `from mutants import mutant`, then
    @mutant("id", "what it proves", target="TB3_off offset gate")
    def _(ctx): return control_ok, detected, "detail"
and name the module flow/mutants_<task>.py (loaded automatically).  Helpers on ctx: ctx.tmp (scratch dir),
ctx.mini_run(deck_text) -> results.json path (a real harness run of a tiny testbench), ctx.eval_mini(results_path).

T0 mutants: meas_failed, run_removed, limit_exceeded (gates), stale_sizes_hash, m_not_nf, bare_ngspice, frozen_edit,
pin_mismatch (lint rules).
"""
import argparse
import copy
import glob
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402
import gates as G  # noqa: E402
import lint as L  # noqa: E402
from harness import runner  # noqa: E402

MUTANTS = []


def mutant(mid, desc, target):
    def deco(fn):
        MUTANTS.append({"id": mid, "desc": desc, "target": target, "fn": fn})
        return fn
    return deco


MINI_GATE = {"title": "mutation-test mini gate", "phase": "env", "spec": "tb_mini.json",
             "scope": {"corners": {"full": "worst5", "smoke": "worst5"}, "grid": {"vg": 2}},
             "checks": [{"kind": "per_run", "metric": "r_ohm", "min": 500.0, "max": 2000.0}]}
SELFTEST_DECK = C.path("sim", "tb_selftest", "tb_selftest.spice")


class Ctx:
    def __init__(self, tmp):
        self.tmp = tmp
        self.spec = C.load_yaml("spec/spec.yaml")
        self._n = 0

    def mini_run(self, deck_text):
        """Real harness run of a tiny testbench (worst5 x 2 vg = 10 runs) in a scratch directory."""
        self._n += 1
        d = os.path.join(self.tmp, "mini%d" % self._n)
        os.makedirs(d)
        with open(os.path.join(d, "tb_mini.spice"), "w") as f:
            f.write(deck_text)
        with open(os.path.join(d, "tb_mini.json"), "w") as f:
            json.dump({"name": "tb_mini", "deck": "tb_mini.spice", "corners": "worst5", "grid": {"vg": [1.2, 3.3]},
                       "limits": {}, "timeout": 60, "jobs": 6}, f)
        runner.run_spec(os.path.join(d, "tb_mini.json"), jobs=6, verbose=False)
        return os.path.join(d, "results", "tb_mini", "results.json"), os.path.join(d, "tb_mini.json")

    def eval_mini(self, results_path, spec_path, gate=None):
        return G.evaluate_gate("MINI", gate or MINI_GATE, self.spec, "smoke", results_file=results_path, spec_file=spec_path)


def _codes(res):
    return sorted({c for c, _ in res["reasons"]})


# ---------------------------------------------------------------------------------------------- gate mutants
@mutant("meas_failed", "a testbench whose .meas can never succeed must FAIL the gate (ngspice itself exits 0)",
        target="harness status -> gate STATUS check")
def _meas_failed(ctx):
    good = open(SELFTEST_DECK).read()
    rp, sp = ctx.mini_run(good)
    control = ctx.eval_mini(rp, sp)
    bad = good.replace(".control\nop\n", ".control\ndc vg 1.2 1.2 0.1\nmeas dc never_met when v(a)=5\n")
    assert bad != good
    rp2, sp2 = ctx.mini_run(bad)
    res = ctx.eval_mini(rp2, sp2)
    return (control["status"] == "PASS",
            res["status"] == "FAIL" and "STATUS" in _codes(res),
            "control %s; mutant %s %s %s" % (control["status"], res["status"], _codes(res), res["status_counts"]))


@mutant("run_removed", "removing one run from the results must trip the run-count check",
        target="expected-run-count check")
def _run_removed(ctx):
    rp, sp = ctx.mini_run(open(SELFTEST_DECK).read())
    control = ctx.eval_mini(rp, sp)
    data = C.load_json(rp)
    data["runs"] = data["runs"][:-1]
    rp2 = os.path.join(ctx.tmp, "removed.json")
    json.dump(data, open(rp2, "w"))
    res = ctx.eval_mini(rp2, sp)
    return (control["status"] == "PASS", res["status"] == "FAIL" and "COUNT" in _codes(res),
            "control %s (%s runs); mutant %s %s expected %s found %s" %
            (control["status"], control["actual_runs"], res["status"], _codes(res), res["expected_runs"], res["actual_runs"]))


@mutant("limit_exceeded", "a metric pushed beyond its limit in one run must FAIL the gate",
        target="per_run limit check")
def _limit_exceeded(ctx):
    rp, sp = ctx.mini_run(open(SELFTEST_DECK).read())
    control = ctx.eval_mini(rp, sp)
    data = C.load_json(rp)
    data["runs"][3]["metrics"]["r_ohm"] *= 10.0
    rp2 = os.path.join(ctx.tmp, "limit.json")
    json.dump(data, open(rp2, "w"))
    res = ctx.eval_mini(rp2, sp)
    return (control["status"] == "PASS", res["status"] == "FAIL" and "LIMIT" in _codes(res),
            "control %s; mutant %s %s" % (control["status"], res["status"], _codes(res)))


# ---------------------------------------------------------------------------------------------- lint mutants
@mutant("stale_sizes_hash", "a sizes.spice whose header hash is stale must be refused",
        target="lint rule sizes / assert_fresh_sizes (netlist build refusal)")
def _stale_hash(ctx):
    good = os.path.join(ctx.tmp, "sizes_good.spice")
    bad = os.path.join(ctx.tmp, "sizes_bad.spice")
    body = "* body\n.param w_m1=20u\n"
    open(good, "w").write("\n".join(C.sizes_header_lines()) + "\n" + body)
    hdr = C.sizes_header_lines()
    h = C.input_hashes()
    open(bad, "w").write(hdr[0] + "\n" + hdr[1].replace(h["spec"], "0" * 64) + "\n" + body)
    refused = False
    try:
        C.assert_fresh_sizes(bad)
    except C.StaleSizesError:
        refused = True
    return (L.check_sizes(good) == [], bool(L.check_sizes(bad)) and refused,
            "control findings %s; mutant findings %s, build refused=%s" % (L.check_sizes(good), len(L.check_sizes(bad)), refused))


@mutant("m_not_nf", "a matched device written with m=4 instead of nf must FAIL lint", target="lint rule matched")
def _m_not_nf(ctx):
    good = os.path.join(ctx.tmp, "good.spice")
    bad = os.path.join(ctx.tmp, "bad.spice")
    open(good, "w").write(".subckt t d g s b\nxm1 d g s b nfet_03v3 w=20u l=0.5u nf=4\n.ends\n")
    open(bad, "w").write(".subckt t d g s b\nxm1 d g s b nfet_03v3 w=5u l=0.5u m=4\n.ends\n")
    return (L.check_matched([good]) == [], bool(L.check_matched([bad])), "mutant findings: %s" % L.check_matched([bad]))


@mutant("bare_ngspice", "a flow script that starts ngspice itself must FAIL lint", target="lint rule ngspice")
def _bare_ngspice(ctx):
    good = os.path.join(ctx.tmp, "good.py")
    bad = os.path.join(ctx.tmp, "bad.py")
    open(good, "w").write("from harness import run_spec\nrun_spec('sim/x/x.json')\n")
    open(bad, "w").write("import subprocess\nsubprocess.run(['ngspice', '-b', 'deck.spice'])\n")
    return (L.check_ngspice([good]) == [], bool(L.check_ngspice([bad])), "mutant findings: %s" % len(L.check_ngspice([bad])))


def _tmp_root(ctx):
    root = os.path.join(ctx.tmp, "root")
    if os.path.isdir(root):
        shutil.rmtree(root)
    shutil.copytree(C.path("spec"), os.path.join(root, "spec"))
    return root


@mutant("frozen_edit", "an edit of a frozen criteria file without a decisions.yaml entry must FAIL lint; with a matching entry it passes",
        target="lint rule frozen")
def _frozen_edit(ctx):
    root = _tmp_root(ctx)
    control = L.check_frozen(root)
    gp = os.path.join(root, "spec", "gates.yaml")
    with open(gp, "a") as f:
        f.write("\n# sneaky edit\n")
    bad = L.check_frozen(root)
    # the legitimate path: a decisions entry carrying the new hash
    dp = os.path.join(root, "spec", "decisions.yaml")
    d = C.load_yaml("spec/decisions.yaml", root)
    d["entries"] = [{"id": "D-test", "kind": "note", "files_after": {"spec/gates.yaml": C.sha256_file(gp)}}]
    import yaml
    yaml.safe_dump(d, open(dp, "w"))
    legit = L.check_frozen(root)
    return (control == [] and legit == [], bool(bad),
            "control %s; edit findings %d; with decisions entry %s" % (control, len(bad), legit))


@mutant("pin_mismatch", "a subckt that lacks a pin of spec/pins.yaml must FAIL the pin-name equality check", target="lint rule pins")
def _pin_mismatch(ctx):
    root = _tmp_root(ctx)
    pins = C.load_yaml("spec/pins.yaml", root)
    names = [p["name"] for p in pins["pins"]]
    os.makedirs(os.path.join(root, "netlist"))
    sp = os.path.join(root, "netlist", "lvds_rx_core.spice")
    open(sp, "w").write(".subckt %s %s\n.ends\n" % (pins["macro"], " ".join(names)))
    control = L.check_pins(root)
    open(sp, "w").write(".subckt %s %s\n.ends\n" % (pins["macro"], " ".join(n for n in names if n != "EN")))
    bad = L.check_pins(root)
    return control == [], bool(bad), "control %s; mutant %s" % (control, bad[:1])


# ---------------------------------------------------------------------------------------------- driver
def load_extra_modules():
    for fp in sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mutants_*.py"))):
        name = os.path.splitext(os.path.basename(fp))[0]
        __import__(name)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", default="")
    a = ap.parse_args(argv)
    load_extra_modules()
    only = [x for x in a.only.split(",") if x]
    base = C.path(".scratch", "mutants")
    out, t0 = [], time.time()
    for m in MUTANTS:
        if only and m["id"] not in only:
            continue
        tmp = os.path.join(base, m["id"])
        shutil.rmtree(tmp, ignore_errors=True)
        os.makedirs(tmp)
        try:
            control_ok, detected, detail = m["fn"](Ctx(tmp))
        except Exception as e:  # a crashing mutant counts as not detected
            control_ok, detected, detail = False, False, "mutant raised %r" % (e,)
        out.append({"id": m["id"], "target": m["target"], "desc": m["desc"], "control": "PASS" if control_ok else "FAIL",
                    "detected": bool(detected and control_ok), "detail": detail})
        print("MUTANT %-18s control %s  detected %s  | %s" % (m["id"], "PASS" if control_ok else "FAIL",
                                                              "YES" if (detected and control_ok) else "NO", detail[:150]))
    survived = [m["id"] for m in out if not m["detected"]]
    C.write_json("results/mutants.json", {"generated": time.strftime("%Y-%m-%d %H:%M:%S"), "git": C.git_state(),
                                          "seconds": round(time.time() - t0, 1), "mutants": out, "survived": survived})
    print("MUTANTS %d run, %d survived %s" % (len(out), len(survived), survived))
    return 1 if survived else 0


if __name__ == "__main__":
    sys.exit(main())
