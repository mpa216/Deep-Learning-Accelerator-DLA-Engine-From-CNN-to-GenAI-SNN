"""Unit tests for the pure-Python helpers.  Run:  python3 -m unittest discover -s sim/harness/tests -v
(from analog/lvds_rx).  No ngspice needed for this file."""
import math
import os
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from harness import analysis, corners, mc, runner, stimulus, report  # noqa: E402


class TestStimulus(unittest.TestCase):
    def test_prbs7_period_and_balance(self):
        b = stimulus.prbs7(254)
        self.assertEqual(b[:127], b[127:254])                      # period 127
        for p in (1, 7, 31, 63):                                   # not a shorter period
            self.assertNotEqual(b[:127 - p], b[p:127])
        self.assertEqual(sum(b[:127]), 64)                         # 64 ones, 63 zeros
        words = {tuple(b[i:i + 7]) for i in range(127)}
        self.assertEqual(len(words), 127)                          # maximal-length: all non-zero 7-bit words
        self.assertNotIn((0,) * 7, words)

    def test_prbs7_seed_zero_rejected(self):
        with self.assertRaises(ValueError):
            stimulus.prbs7(10, seed=0)

    def test_pwl_points_edges(self):
        t, v = stimulus.pwl_points([0, 0, 1, 0], ui=10e-9, tr=1e-9, vhi=1.0, vlo=0.0, t0=5e-9)
        self.assertEqual(v[0], 0.0)
        # first transition at bit 2: starts 5n+20n = 25n, ends 26n
        self.assertAlmostEqual(t[1], 25e-9)
        self.assertAlmostEqual(t[2], 26e-9)
        self.assertEqual((v[1], v[2]), (0.0, 1.0))
        self.assertAlmostEqual(t[3], 35e-9)                        # falls at bit 3
        self.assertEqual(len(t), len(v))
        self.assertTrue(all(b >= a for a, b in zip(t, t[1:])))     # monotonic time

    def test_pwl_tr_longer_than_ui_rejected(self):
        with self.assertRaises(ValueError):
            stimulus.pwl_points([0, 1], ui=1e-9, tr=2e-9, vhi=1, vlo=0)

    def test_diff_prbs_complementary(self):
        bits = stimulus.prbs7(40)
        (tp, vp), (tn, vn) = stimulus.diff_prbs(bits, 10e-9, 1e-9, vos=1.2, vod=0.1)
        self.assertEqual(tp, tn)
        for a, b in zip(vp, vn):
            self.assertAlmostEqual(a + b, 2.4)                      # common mode constant
            self.assertAlmostEqual(abs(a - b), 0.1)                 # differential = VOD
        self.assertAlmostEqual(max(vp), 1.25)
        self.assertAlmostEqual(min(vp), 1.15)

    def test_pwl_text_and_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.inc")
            txt = stimulus.write_diff_prbs(p, stimulus.prbs7(30), 10e-9, 1e-9, 1.2, 0.1)
            self.assertEqual(open(p).read(), txt)
            self.assertIn("VP inp 0 PWL(", txt)
            self.assertIn("VN inn 0 PWL(", txt)
            self.assertTrue(all(len(l) < 120 for l in txt.splitlines()))   # continuation lines, no giant line

    def test_triangle(self):
        t, v = stimulus.triangle(-0.15, 0.15, 2e-6, ncycles=2)
        self.assertEqual(v[:3], [-0.15, 0.15, -0.15])
        self.assertAlmostEqual(t[-1], 4e-6)
        self.assertAlmostEqual(t[1], 1e-6)

    def test_clock(self):
        t, v = stimulus.clock_pwl(10e-9, 0, 1, 0.1e-9, duty=0.5, ncycles=3)
        r = analysis.crossings(t, v, 0.5, "rising")
        f = analysis.crossings(t, v, 0.5, "falling")
        self.assertAlmostEqual(f[0] - r[0], 5e-9, places=15)
        self.assertAlmostEqual(r[1] - r[0], 10e-9, places=15)
        line = stimulus.clock_source_line("CK", "ck", 0, 3.3, 10e-9, 0.2e-9)
        self.assertTrue(line.startswith("VCK ck 0 PULSE("))


class TestAnalysis(unittest.TestCase):
    def test_crossings_interpolated(self):
        t = np.array([0.0, 1.0, 2.0, 3.0])
        v = np.array([0.0, 1.0, 3.0, 0.0])
        self.assertTrue(np.allclose(analysis.crossings(t, v, 0.5, "rising"), [0.5]))
        self.assertTrue(np.allclose(analysis.crossings(t, v, 2.0, "rising"), [1.5]))
        self.assertTrue(np.allclose(analysis.crossings(t, v, 2.0, "falling"), [2 + 1 / 3]))
        self.assertEqual(len(analysis.crossings(t, v, 5.0)), 0)

    def test_crossings_sine(self):
        t = np.linspace(0, 1e-6, 20001)
        v = np.sin(2 * np.pi * 5e6 * t)
        r = analysis.crossings(t, v, 0.0, "rising")
        self.assertTrue(np.allclose(r, [i * 200e-9 for i in range(1, 5)], atol=1e-12) or len(r) >= 3)
        self.assertAlmostEqual(r[1] - r[0], 200e-9, places=12)

    def _square(self, delay_r, delay_f, n=6):
        t = np.linspace(0, 7e-6, 700001)
        tin = []
        vin = np.zeros_like(t)
        vout = np.zeros_like(t)
        for k in range(n):
            a = 0.5e-6 + k * 1e-6          # input rises at a, falls at a+0.5u
            vin[(t >= a) & (t < a + 0.5e-6)] = 1
            vout[(t >= a + delay_r) & (t < a + 0.5e-6 + delay_f)] = 1
        return t, vin, vout

    def test_prop_delays_and_skew(self):
        t, vin, vout = self._square(3e-9, 1e-9)
        d = analysis.prop_delays(t, vin, vout, 0.5, 0.5)
        self.assertAlmostEqual(d["tplh_mean"], 3e-9, delta=3e-11)
        self.assertAlmostEqual(d["tphl_mean"], 1e-9, delta=3e-11)
        self.assertAlmostEqual(d["skew"], 2e-9, delta=5e-11)
        self.assertAlmostEqual(d["tpd"], 2e-9, delta=5e-11)
        self.assertEqual(d["n_missed"], 0)

    def test_prop_delays_inverting(self):
        t, vin, vout = self._square(3e-9, 1e-9)
        d = analysis.prop_delays(t, vin, 1 - vout, 0.5, 0.5, inverting=True)
        # inverted output: out falls when in rises (delay 3n), rises when in falls (1n)
        self.assertAlmostEqual(d["tphl_mean"], 3e-9, delta=3e-11)
        self.assertAlmostEqual(d["tplh_mean"], 1e-9, delta=3e-11)

    def test_prop_delay_missed_edge_counted(self):
        t, vin, vout = self._square(3e-9, 1e-9)
        vout[:] = 0                                   # output never toggles
        d = analysis.prop_delays(t, vin, vout, 0.5, 0.5)
        self.assertGreater(d["n_missed"], 0)
        self.assertTrue(math.isnan(d["tpd"]))

    def test_hysteresis(self):
        # ideal Schmitt trigger: rises at +20 mV, falls at -10 mV (offset +5 mV, VH 30 mV)
        t, vid = stimulus.triangle(-0.15, 0.15, 2e-6, ncycles=3)
        tt = np.linspace(0, 6e-6, 60001)
        x = np.interp(tt, t, vid)
        out = np.zeros_like(tt)
        state = 0
        for i, xv in enumerate(x):
            if state == 0 and xv > 0.020:
                state = 1
            elif state == 1 and xv < -0.010:
                state = 0
            out[i] = state
        h = analysis.hysteresis(tt, x, out, 0.5)
        self.assertAlmostEqual(h["vth_plus"], 0.020, delta=1e-4)
        self.assertAlmostEqual(h["vth_minus"], -0.010, delta=1e-4)
        self.assertAlmostEqual(h["vh"], 0.030, delta=2e-4)
        self.assertAlmostEqual(h["offset"], 0.005, delta=1e-4)
        self.assertEqual((h["n_up"], h["n_dn"]), (3, 3))

    def test_hysteresis_no_edges_is_nan(self):
        tt = np.linspace(0, 1, 100)
        h = analysis.hysteresis(tt, tt - 0.5, np.zeros_like(tt), 0.5)
        self.assertTrue(math.isnan(h["vth_plus"]) and math.isnan(h["vh"]))

    def test_duty_cycle(self):
        t, v = stimulus.clock_pwl(10e-9, 0, 1, 0.1e-9, duty=0.55, ncycles=6)
        d = analysis.duty_cycle(t, v, 0.5)
        self.assertAlmostEqual(d["t_high"], 5.5e-9, delta=1e-13)
        self.assertAlmostEqual(d["dcd"], 0.5e-9, delta=1e-13)       # |th - tl| / 2
        self.assertAlmostEqual(d["duty"], 0.55, places=6)

    def _eye_wave(self, ui, jitter, dcd_shift, nbits=400, tr=1e-9):
        """Synthetic NRZ with known edge-time offsets: rising edges delayed by +dcd_shift,
        falling by 0, plus deterministic jitter list."""
        bits = stimulus.prbs7(nbits)
        t = np.arange(0, (nbits + 2) * ui, ui / 100.0)
        v = np.zeros_like(t)
        prev = bits[0]
        v[:] = prev
        edges = []
        for i, b in enumerate(bits):
            if b != prev:
                j = jitter[i % len(jitter)]
                te = 5e-9 + i * ui + j + (dcd_shift if b == 1 else 0.0)
                edges.append((te, b))
                prev = b
        v = np.full_like(t, float(bits[0]))
        for te, b in edges:
            ramp = np.clip((t - (te - tr / 2)) / tr, 0, 1)
            v = v + (ramp if b == 1 else -ramp) * 1.0
        return t, v

    def test_eye_metrics_known_jitter(self):
        ui = 10e-9
        j = [0.0, 0.3e-9, -0.3e-9, 0.15e-9, -0.15e-9]
        t, v = self._eye_wave(ui, j, 0.0)
        m = analysis.eye_metrics(t, v, ui, 0.5, t_skip_ui=20, t0=5e-9)
        self.assertAlmostEqual(m["jitter_pp"], 0.6e-9, delta=0.05e-9)
        self.assertAlmostEqual(m["h_open_ui"], 1 - 0.06, delta=0.006)
        self.assertLess(m["dcd_ui"], 0.01)
        self.assertAlmostEqual(m["v_open"], 1.0, delta=0.01)

    def test_eye_metrics_dcd(self):
        ui = 10e-9
        t, v = self._eye_wave(ui, [0.0], 0.5e-9)       # rising edges 0.5 ns late
        m = analysis.eye_metrics(t, v, ui, 0.5, t_skip_ui=20, t0=5e-9)
        self.assertAlmostEqual(m["dcd_ui"], 0.05, delta=0.004)
        self.assertAlmostEqual(m["jitter_pp"], 0.5e-9, delta=0.05e-9)

    def test_eye_closed_flag(self):
        t = np.linspace(0, 1e-6, 1000)
        m = analysis.eye_metrics(t, np.zeros_like(t), 10e-9, 0.5)
        self.assertTrue(math.isnan(m["h_open_ui"]))                  # no edges: explicit NaN, not 0 or 1

    def test_load_wrdata_paired_and_single(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "w.txt")
            t = np.arange(5.0)
            np.savetxt(p, np.column_stack([t, t * 2, t, t * 3]))
            tt, (a, b) = analysis.load_wrdata(p, nvec=2)
            self.assertTrue(np.allclose(tt, t) and np.allclose(a, 2 * t) and np.allclose(b, 3 * t))
            np.savetxt(p, np.column_stack([t, t * 2, t * 3]))
            tt, (a, b) = analysis.load_wrdata(p, nvec=2)
            self.assertTrue(np.allclose(a, 2 * t) and np.allclose(b, 3 * t))

    def test_eye_png(self):
        ui = 10e-9
        t, v = self._eye_wave(ui, [0.0, 0.2e-9], 0.0)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "eye.png")
            analysis.plot_eye(t, v, ui, p, threshold=0.5, t0=5e-9, metrics=analysis.eye_metrics(t, v, ui, 0.5, t0=5e-9))
            self.assertGreater(os.path.getsize(p), 3000)


class TestCorners(unittest.TestCase):
    def test_header_deterministic_and_explicit(self):
        h = corners.Corner("ss", 125, 3.0).header()
        self.assertIn(".param sw_stat_global=0 sw_stat_mismatch=0", h)
        for tok in ("res_mc_skew=3", "fnoicor=0", "sm141064.ngspice ss", "res_ss", "moscap_ss", "diode_ss", ".temp 125"):
            self.assertIn(tok, h)
        self.assertNotIn("design.ngspice", h)
        self.assertEqual(h, corners.Corner("ss", 125, 3.0).header())

    def test_header_sets_wnflag(self):
        # PLAN_V2 1.5: binning on W per finger is required for LUT-faithful netlists
        for mc in corners.MC_MODES:
            proc = "tt"
            h = corners.Corner(proc, 27, 3.3).header(mc=mc)
            self.assertIn(".option wnflag=1", h.splitlines())

    def test_resistor_corner_follows_process_and_cross_corners(self):
        fam = {"tt": "typical", "ss": "ss", "ff": "ff", "fs": "typical", "sf": "typical"}
        for c in corners.get_corner_set("full45"):
            self.assertEqual(c.res, "res_" + fam[c.process])
            self.assertIn(".lib %s %s" % (corners.PDK_LIB, c.res), c.header())
        cross = corners.get_corner_set("cross2")
        self.assertEqual([(c.process, c.res) for c in cross], [("ss", "res_ff"), ("ff", "res_ss")])
        names = {c.name for c in corners.get_corner_set("full47")}
        self.assertEqual(len(names), 47)                  # cross corners do not collide with ss/ff 125C/3.0V, -40C/3.6V
        self.assertEqual(len(corners.get_corner_set("worst7")), 7)
        self.assertEqual(len(corners.get_corner_set("eye15")), 15)
        self.assertEqual(len(corners.get_corner_set("extreme2")), 2)
        self.assertEqual(corners.parse_corner("ss:125:3.0:res=res_ff").name, cross[0].name)

    def test_fs_sf_use_typical_passives(self):
        h = corners.Corner("fs", 27, 3.3).header()
        self.assertIn("sm141064.ngspice fs", h)
        self.assertIn("res_typical", h)
        self.assertIn("moscap_typical", h)

    def test_mc_modes(self):
        c = corners.Corner("tt")
        self.assertIn("sw_stat_global=0 sw_stat_mismatch=1", c.header(mc="mismatch"))
        g = c.header(mc="global")
        self.assertIn("sw_stat_global=1 sw_stat_mismatch=0", g)
        self.assertIn("statistical", g)
        self.assertNotIn("sm141064.ngspice typical", g)     # statistical REPLACES typical
        with self.assertRaises(ValueError):
            corners.Corner("ss").header(mc="global")
        with self.assertRaises(ValueError):
            c.header(mc="bogus")

    def test_sets_and_names(self):
        self.assertEqual(len(corners.get_corner_set("full45")), 45)
        self.assertEqual(len({c.name for c in corners.get_corner_set("full45")}), 45)
        self.assertEqual(len(corners.get_corner_set("worst5")), 5)
        self.assertEqual(corners.Corner("ff", -40, 3.6).name, "ff_m40c_3v60")
        self.assertEqual(corners.Corner("tt", 27, 3.3).name, "tt_27c_3v30")
        c = corners.parse_corner("fs:27:3.3:res=res_ss")
        self.assertEqual((c.process, c.res), ("fs", "res_ss"))
        self.assertEqual(len(corners.get_corner_set(["tt", "worst5"])), 5)   # de-duplicated
        with self.assertRaises(KeyError):
            corners.get_corner_set("nope")


class TestMC(unittest.TestCase):
    def test_seeds_deterministic_distinct(self):
        a, b = mc.make_seeds(200, 7), mc.make_seeds(200, 7)
        self.assertEqual(a, b)
        self.assertEqual(len(set(a)), 200)
        self.assertNotEqual(a, mc.make_seeds(200, 8))
        self.assertEqual(mc.seed_line(12), ".option seed=12")

    def test_stats(self):
        s = mc.stats([1, 2, 3, 4, float("nan")])
        self.assertEqual((s["n"], s["n_bad"]), (4, 1))
        self.assertAlmostEqual(s["mean"], 2.5)
        self.assertAlmostEqual(s["sigma"], math.sqrt(5 / 3))
        self.assertAlmostEqual(s["hi3"], 2.5 + 3 * s["sigma"])
        self.assertTrue(math.isnan(mc.stats([float("nan")])["mean"]))

    def test_check_limits(self):
        x = np.random.RandomState(1).normal(0, 1.0, 500)
        self.assertTrue(mc.check_limits(x, -4, 4, k=3)["ok"])
        self.assertFalse(mc.check_limits(x, -2, 2, k=3)["ok"])
        self.assertFalse(mc.check_limits(list(x) + [float("nan")], -4, 4, k=3)["ok"])   # a bad sample fails the check
        r = mc.check_limits(x, None, 4, k=3)
        self.assertIsNone(r["margin_lo"])
        self.assertGreater(r["margin_hi"], 0)

    def test_pelgrom_formula(self):
        # W=1u L=0.5u nfet: 7.148 mV*um / sqrt(0.35 * 1.1) = 11.52 mV
        self.assertAlmostEqual(mc.pelgrom_pair_sigma(1e-6, 0.5e-6), 11.52e-3, delta=0.01e-3)
        # 4x area -> half sigma
        a = mc.pelgrom_pair_sigma(1e-6, 1e-6)
        b = mc.pelgrom_pair_sigma(2e-6, 2e-6)
        self.assertGreater(a / b, 1.7)

    def test_histogram_png(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "h.png")
            mc.histogram(np.random.RandomState(2).normal(0, 1, 300), p, title="t", lo=-4, hi=4)
            self.assertGreater(os.path.getsize(p), 3000)
            mc.histogram([], os.path.join(d, "e.png"))          # empty sample must not crash


class TestRunnerPure(unittest.TestCase):
    def test_render(self):
        txt, unres = runner.render("* {header} stays\nvdd a 0 {vdd}\nr1 a b {rval}\n.param x={y*2}\n{header}",
                                   {"header": "HDR\nHDR2", "vdd": 3.3, "rval": "1k"})
        self.assertIn("* {header} stays", txt)                  # comment lines are not expanded
        self.assertIn("vdd a 0 3.3", txt)
        self.assertIn("r1 a b 1k", txt)
        self.assertIn("{y}" if False else "{y*2}", txt)         # SPICE expression untouched
        self.assertTrue(txt.endswith("HDR\nHDR2"))
        self.assertEqual(unres, [])
        _, unres = runner.render("r1 a b {typo}", {})
        self.assertEqual(unres, ["typo"])

    def test_expected_measures(self):
        deck = "* meas dc commented x\n.meas dc vos when v(a)=0\n.MEAS TRAN tpd trig v(a) val=1 targ v(b) val=1\n.control\nmeas dc g find v(x) at=1\n.endc\n"
        self.assertEqual(runner.expected_measures(deck), ["vos", "tpd", "g"])

    def test_parse_log(self):
        log = ("vos                 =  1.482620e-02 at=  1.5\n"
               "tpd                 = failed\n"
               "other               =  5\n"
               "RESULT custom 2.5e-9\n"
               "Error: something bad\n")
        meas, extra, failed, errs, nc = runner.parse_log(log, ["vos", "tpd", "g"])
        self.assertAlmostEqual(meas["vos"], 0.0148262)
        self.assertTrue(math.isnan(meas["tpd"]))
        self.assertEqual(failed, ["tpd"])
        self.assertNotIn("other", meas)
        self.assertEqual(extra, {"custom": 2.5e-9})
        self.assertEqual(len(errs), 1)
        self.assertFalse(nc)
        _, _, _, errs, nc = runner.parse_log("doAnalyses: TRAN:  Timestep too small", [])
        self.assertTrue(nc)

    def test_lint_deck(self):
        runner.lint_deck(".tran 1n 1u\n.meas tran a max v(x)\n")
        runner.lint_deck(".dc v1 0 1 0.1\n.tran 1n 1u\n")                        # no meas: fine
        runner.lint_deck(".control\ndc v1 0 1 0.1\ntran 1n 1u\nmeas tran a max v(x)\n.endc\n")
        with self.assertRaises(ValueError):
            runner.lint_deck(".dc v1 0 1 0.1\n.meas dc a max v(x)\n.tran 1n 1u\n.meas tran b max v(x)\n")


class TestReport(unittest.TestCase):
    def test_margin_and_verdict(self):
        lim = {"min": -1.0, "max": 2.0}
        self.assertAlmostEqual(report.margin(0.5, lim), 1.5)
        self.assertAlmostEqual(report.margin(2.5, lim), -0.5)
        self.assertTrue(math.isnan(report.margin(float("nan"), lim)))
        recs = [{"id": "a", "status": "ok", "metrics": {"x": 0.5}, "params": {}, "corner": "c", "errors": [], "cached": False},
                {"id": "b", "status": "ok", "metrics": {}, "params": {}, "corner": "c", "errors": [], "cached": False},
                {"id": "c", "status": "meas_failed", "metrics": {"x": 0.1}, "params": {}, "corner": "c", "errors": [], "cached": False}]
        v = report.evaluate_runs(recs, {"x": lim})
        self.assertEqual([x["ok"] for x in v], [True, False, False])           # missing metric / failed status = FAIL


class TestVerificationFixes(unittest.TestCase):
    """Regressions found by the independent verification (2026-11-10)."""

    def test_fractional_temperature_names_distinct(self):
        n = {corners.Corner("tt", t, 3.3).name for t in (27, 27.5, 28, -0.5, 0, -40)}
        self.assertEqual(len(n), 6)
        self.assertEqual(corners.Corner("ff", -40, 3.6).name, "ff_m40c_3v60")      # unchanged integer names
        self.assertEqual(corners.Corner("ss", 125, 3.0).name, "ss_125c_3v00")

    def test_mc_requires_seed_placeholder(self):
        deck = "{header}\nr1 a 0 1k\nv1 a 0 1\n.tran 1n 10n\n.meas tran x max v(a)\n.end\n"
        with self.assertRaises(ValueError):
            runner.build_runs(deck, ".", "/tmp/_w", "tt", None, {"n": 2}, None, None, "x")
        # a mention inside a comment does not count
        with self.assertRaises(ValueError):
            runner.build_runs("* {seed_line}\n" + deck, ".", "/tmp/_w", "tt", None, {"n": 2}, None, None, "x")
        runs = runner.build_runs("{seed_line}\n" + deck, ".", "/tmp/_w", "tt", None, {"n": 2}, None, None, "x")
        self.assertEqual(len(runs), 2)


if __name__ == "__main__":
    unittest.main()
