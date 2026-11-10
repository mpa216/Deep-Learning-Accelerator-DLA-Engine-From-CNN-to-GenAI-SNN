"""Integration tests that call ngspice (skipped when it is not on PATH).  They use a plain RC circuit,
no PDK, so they are fast.  Run: python3 -m unittest discover -s sim/harness/tests -v"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from harness import runner  # noqa: E402

HAVE = shutil.which("ngspice") is not None

RC = """* rc
{header}
vin in 0 pulse(0 1 1u 1n 1n 1 2)
r1 in out {r}
c1 out 0 1n
.tran 10n 20u
.meas tran t50 trig v(in) val=0.5 rise=1 targ v(out) val=0.5 rise=1
.end
"""
# the header is irrelevant for an RC circuit but is part of the template contract; keep it tiny
HDR_TEMPLATE = RC.replace("{header}", "{header_stub}")


@unittest.skipUnless(HAVE, "ngspice not available")
class TestRunner(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="harness_test_")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def _run(self, template, **kw):
        kw.setdefault("jobs", 2)
        kw.setdefault("verbose", False)
        return runner.run_testbench(template, os.path.join(self.d, "work"), self.d, **kw)

    def test_ok_cache_force_and_result_files(self):
        # no PDK header needed: pass extra_vars header_stub
        recs = self._run(HDR_TEMPLATE, grid={"r": ["1k", "2k"]}, extra_vars={"header_stub": "* nothing"})
        self.assertEqual([r["status"] for r in recs], ["ok", "ok"])
        t1k, t2k = recs[0]["metrics"]["t50"], recs[1]["metrics"]["t50"]
        self.assertAlmostEqual(t1k, 0.6931e-6, delta=0.02e-6)               # ln2 * RC
        self.assertAlmostEqual(t2k / t1k, 2.0, delta=0.05)
        self.assertFalse(any(r["cached"] for r in recs))
        recs2 = self._run(HDR_TEMPLATE, grid={"r": ["1k", "2k"]}, extra_vars={"header_stub": "* nothing"})
        self.assertTrue(all(r["cached"] for r in recs2))                      # incremental: nothing re-run
        self.assertEqual([r["metrics"] for r in recs], [r["metrics"] for r in recs2])
        recs3 = self._run(HDR_TEMPLATE, grid={"r": ["1k", "2k"]}, extra_vars={"header_stub": "* nothing"}, force=True)
        self.assertFalse(any(r["cached"] for r in recs3))                     # --force
        recs4 = self._run(HDR_TEMPLATE.replace("1n\n.tran", "2n\n.tran"), grid={"r": ["1k", "2k"]},
                          extra_vars={"header_stub": "* nothing"})
        self.assertFalse(any(r["cached"] for r in recs4))                     # deck changed -> hash changed
        self.assertTrue(os.path.isfile(os.path.join(self.d, "results.csv")))
        with open(os.path.join(self.d, "results.json")) as f:
            data = json.load(f)
        self.assertEqual(len(data["runs"]), 2)

    def test_failed_measurement_is_explicit(self):
        deck = HDR_TEMPLATE.replace("val=0.5 rise=1 targ", "val=0.5 rise=1 targ").replace("targ v(out) val=0.5", "targ v(out) val=7.0")
        recs = self._run(deck, grid={"r": ["1k"]}, extra_vars={"header_stub": "*"})
        self.assertEqual(recs[0]["status"], "meas_failed")
        self.assertTrue(any("t50" in e for e in recs[0]["errors"]))

    def test_bad_netlist_is_sim_error(self):
        recs = self._run("* bad\nr1 a\n.tran 1n 1u\n.end\n")
        self.assertIn(recs[0]["status"], ("sim_error", "meas_failed", "nonconverged"))
        self.assertNotEqual(recs[0]["status"], "ok")

    def test_undefined_model_is_sim_error(self):
        recs = self._run("* x\nvdd a 0 1\nXn a a 0 0 nosuchmodel w=1u l=1u\n.op\n.end\n")
        self.assertEqual(recs[0]["status"], "sim_error")

    def test_timeout(self):
        deck = "* long\n.control\nshell sleep 30\n.endc\n.end\n"
        recs = self._run(deck, timeout=1.0)
        self.assertEqual(recs[0]["status"], "timeout")

    def test_mc_seed_runs_and_post_hook(self):
        deck = ("* seeded\n{seed_line}\n.param a=agauss(0,1,1)\nvin in 0 1\nbx x 0 V='a'\nr1 in 0 1k\n"
                ".dc vin 0 2 1\n.meas dc av find v(x) at=1\n.end\n")
        post = lambda ctx: {"double": 2 * ctx["measures"]["av"]}
        recs = self._run(deck, mc={"n": 4, "seed": 3}, post=post, extra_vars={})
        self.assertEqual(len(recs), 4)
        self.assertTrue(all(r["status"] == "ok" for r in recs), [r["errors"] for r in recs])
        vals = [r["metrics"]["av"] for r in recs]
        self.assertEqual(len(set(vals)), 4)                                    # each seed draws differently
        self.assertTrue(all(abs(r["metrics"]["double"] - 2 * r["metrics"]["av"]) < 1e-12 for r in recs))
        recs2 = self._run(deck, mc={"n": 4, "seed": 3}, post=post, force=True)
        self.assertEqual(vals, [r["metrics"]["av"] for r in recs2])             # same seeds -> same draws


if __name__ == "__main__":
    unittest.main()
