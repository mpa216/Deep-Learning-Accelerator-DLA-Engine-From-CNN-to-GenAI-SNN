"""mutants_t5.py -- circuit-specific gate mutants (T5, PLAN_V2 5.2 item 2).  Loaded automatically by flow/mutants.py.

  offset_area_div4   input-pair area (mp1 and mn1 W) divided by 4 in a scratch copy of sizes.spice -> real DC offset
                     Monte Carlo (hysteresis off, extreme2 x 3 VIC x N = 100, the real tb3_off deck and hook) must
                     FAIL the TB3_off gate.  Control: the real full-tier TB3_off results (N = 1000) pass the same gate.
  polarity_swap      the DUT's RX0_P / RX0_N swapped in the TB5 deck -> every bit is inverted: BER must be > 0 and the
                     TB5 gate FAIL.  Control: the unswapped deck (tt, VIC 1.2 V, VID 350 mV, 100 Mb/s) has BER 0 and passes.
  nf_to_m_core       `nf={nf_mp1}` replaced by `m={nf_mp1}` in a scratch copy of the REAL netlist/lvds_rx_core.spice ->
                     lint rule `matched` must flag it; the real netlist passes.
"""
import copy
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402
import gates as G  # noqa: E402
import lint as L  # noqa: E402
from harness import runner  # noqa: E402
from mutants import mutant, _codes  # noqa: E402


def _scratch_tree(tmp, tb):
    """<tmp>/sim/<tb>/ (a copy of the real bench directory without results), symlinks for harness, lib_tb, netlist, and a
    REAL sizing/ directory (so a mutant can edit sizes.spice).  Returns the bench directory."""
    sim = os.path.join(tmp, "sim")
    os.makedirs(sim, exist_ok=True)
    for name in ("harness", "lib_tb.py"):
        dst = os.path.join(sim, name)
        if not os.path.lexists(dst):
            os.symlink(C.path("sim", name), dst)
    if not os.path.lexists(os.path.join(tmp, "netlist")):
        os.symlink(C.path("netlist"), os.path.join(tmp, "netlist"))
    os.makedirs(os.path.join(tmp, "sizing"), exist_ok=True)
    shutil.copy(C.path("sizing", "sizes.spice"), os.path.join(tmp, "sizing", "sizes.spice"))
    d = os.path.join(sim, tb)
    shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(C.path("sim", tb), d, ignore=shutil.ignore_patterns("results", "__pycache__", "work"))
    return d


def _edit_json(path, fn):
    d = C.load_json(path)
    fn(d)
    with open(path, "w") as f:
        json.dump(d, f, indent=1)


def _scaled_gate(gid, spec_gates, corners, grid=None, mc=None, keep=None):
    g = copy.deepcopy(spec_gates["gates"][gid])
    g["scope"]["corners"] = {"full": corners, "smoke": corners}
    if grid is not None:
        g["scope"]["grid"] = grid
    if mc is not None:
        g["scope"]["mc"] = {"full": mc, "smoke": mc}
    if keep is not None:
        g["checks"] = [c for c in g["checks"] if c.get("metric") in keep]
    return g


@mutant("offset_area_div4", "input-pair area (mp1, mn1) divided by 4 must FAIL the TB3_off offset gate",
        target="TB3_off mc_offset_window (|mean| + 6 sigma + VHmax/2 + 3 mV <= 95 mV, sigma <= 8 mV)")
def _offset_area(ctx):
    gy = C.load_yaml("spec/gates.yaml")
    spec = ctx.spec
    # control: the real full-tier results
    real = G.evaluate_gate("TB3_off", gy["gates"]["TB3_off"], spec, "full")
    ctl_sigma = [c.get("sigma") for c in real["checks"] if c["kind"] == "mc_offset_window"]
    control_ok = real["status"] == "PASS"
    # mutant
    d = _scratch_tree(ctx.tmp, "tb3_off")
    sz = os.path.join(ctx.tmp, "sizing", "sizes.spice")
    txt = open(sz).read()
    n = 0
    for stem in ("mp1", "mn1"):
        m = re.search(r"^\.param w_%s = ([0-9.]+)u$" % stem, txt, re.M)
        assert m, stem
        txt = txt.replace(m.group(0), ".param w_%s = %.4fu" % (stem, float(m.group(1)) / 4.0))
        n += 1
    open(sz, "w").write(txt)
    _edit_json(os.path.join(d, "tb3_off.json"), lambda j: (j.update(corners="extreme2"), j["mc"].update(n=100)))
    gate = _scaled_gate("TB3_off", gy, "extreme2", mc=100)
    runner.run_spec(os.path.join(d, "tb3_off.json"), jobs=6, verbose=False)
    rf = os.path.join(d, "results", "tb3_off", "results.json")
    sp = os.path.join(d, "tb3_off.json")
    res = G.evaluate_gate("TB3_off", gate, spec, "full", results_file=rf, spec_file=sp)
    chk = [c for c in res["checks"] if c["kind"] == "mc_offset_window"][0]
    detected = res["status"] == "FAIL" and "LIMIT" in _codes(res)
    return (control_ok, detected,
            "control (real, N=1000) %s sigma %.2f mV; mutant (W/4 on %d devices, N=100) %s sigma %.2f mV worst %.1f mV (limit 95) %s" %
            (real["status"], 1e3 * (ctl_sigma[0] or 0), n, res["status"], 1e3 * (chk.get("sigma") or 0),
             1e3 * (chk.get("worst") or 0), _codes(res)))


@mutant("polarity_swap", "RX0_P / RX0_N swapped at the DUT must FAIL the TB5 BER check",
        target="TB5 per_run ber_errors <= 0 (and toggle_diff)")
def _polarity(ctx):
    gy = C.load_yaml("spec/gates.yaml")
    spec = ctx.spec
    gate = _scaled_gate("TB5", gy, "tt", grid={"vic": 1, "vid": 1, "rate": 1}, keep=("ber_errors", "toggle_diff"))
    outs = []
    for tag in ("control", "mutant"):
        d = _scratch_tree(os.path.join(ctx.tmp, tag), "tb5_eye")
        _edit_json(os.path.join(d, "tb5_eye.json"),
                   lambda j: j.update(corners="tt", grid={"vic": [1.2], "vid": [0.35], "rate": [100e6]}))
        if tag == "mutant":
            p = os.path.join(d, "tb5_eye.spice")
            t = open(p).read()
            t2 = t.replace("Xdut vdd 0 rx0_p rx0_n ", "Xdut vdd 0 rx0_n rx0_p ")
            assert t2 != t
            open(p, "w").write(t2)
        runner.run_spec(os.path.join(d, "tb5_eye.json"), jobs=6, verbose=False)
        rf = os.path.join(d, "results", "tb5_eye", "results.json")
        res = G.evaluate_gate("TB5", gate, spec, "full", results_file=rf, spec_file=os.path.join(d, "tb5_eye.json"))
        runs = C.load_json(rf)["runs"]
        outs.append((res, runs[0]["metrics"].get("ber_errors") if runs else None))
    (rc, bc), (rm, bm) = outs
    return (rc["status"] == "PASS", rm["status"] == "FAIL" and "LIMIT" in _codes(rm),
            "control %s ber_errors %s; mutant %s ber_errors %s %s" % (rc["status"], bc, rm["status"], bm, _codes(rm)))


@mutant("nf_to_m_core", "nf replaced by m on a matched input device of the real core netlist must FAIL lint",
        target="lint rule matched (on netlist/lvds_rx_core.spice)")
def _nf_to_m(ctx):
    src = C.path("netlist", "lvds_rx_core.spice")
    txt = open(src).read()
    bad_txt = txt.replace("nf={nf_mp1}", "m={nf_mp1}", 1)
    assert bad_txt != txt
    bad = os.path.join(ctx.tmp, "lvds_rx_core.spice")
    open(bad, "w").write(bad_txt)
    control = L.check_matched([src])
    found = L.check_matched([bad])
    return control == [], bool(found), "real netlist findings %d; mutant findings %d (%s)" % (len(control), len(found),
                                                                                         (found[0][-70:] if found else ""))
