# Independent verification of "sim-harness" (2026-11-10)

Verdict: the deliverable reproduces and is usable.  Two small defects and one wrong interpretation were found and fixed
(listed below).  Nothing in the builder's numbers failed to reproduce.

## Re-run from clean state
* `bash sim/harness_demo/run_demo.sh` (deletes results/, then runs everything), exit code 0 (wall time not measured
  precisely; it was still running some minutes after start).  41 unit tests OK; Pelgrom 12 areas x 200 seeds (2400 runs, 0 failed):
  ratio mean 1.017 (min 1.013, max 1.021), fitted A = 7.385 mV*um; `pelgrom_check.md` is byte-identical to the
  builder's earlier output (deterministic).  check_repro: forced re-run 1200 runs max |diff| 0 V, second run 1200/1200
  cached, edited deck 0/240 cached, independent seed 777 N=1000 ratio 1.025 (1.11 standard errors).  mc_loop_check:
  200 distinct values, same in a 2nd process (diff 0), no-reset loop constant, sigma ratio 0.991.
* Demo numbers match the report: worst tPLH 5.992 ns at ss_125c_3v00 vic 0.9 (limit 5 ns, FAIL, highlighted),
  vtrip sigma 4.667 mV at tt (N=200, PASS).
* CLI from a different working directory (cwd=/tmp, absolute paths): works; exit code 0 for a passing spec, 1 for a failing
  one; `header` and `corners` work; global at ss gives a clear error.

## Attempts to break it (scripts in .scratch/verify_sim_harness/)
`indep_analysis.py` (synthetic signals with known answers, independent of the builder's tests): crossings on a sine
exact to 6e-16 s; tPLH 1.3 ns / tPHL 2.1 ns / skew 0.8 ns recovered to under 1 ps incl. the inverting case; eye with
injected 100 ps edge offset + 80 ps uniform jitter + 0.1 UI DCD gives jitter_pp 170 ps (grid 10 ps), DCD 0.1016 UI,
h-open 0.83 UI; hysteresis of a model Schmitt (+0.05/-0.03) recovered to 0.1 mV, NaN when no output edge; PRBS7 period 127,
64 ones, max run 7; differential PWL common mode and amplitude exact; full45 = 45 unique names; stats/limits treat NaN as bad.
`indep_failures.py` (runner): good tran measure (RC ln2 = 0.6937 us) ok; unreachable `.meas` and control-block `meas`
-> meas_failed with the NaN kept; voltage-source loop -> nonconverged; unknown model / missing include / garbage netlist /
undefined parameter -> sim_error; `shell sleep` with timeout 3 s -> timeout; a deck with no .meas/.print -> sim_error
(ngspice batch refuses it, correctly reported); cache counts 0 / 2 / 0 for first / repeat / forced; the corner (temperature)
changes the cache key.  Failure detection is explicit everywhere I tried.
PMOS Pelgrom (not measured by the builder; own deck, 4 areas x N=400, 1600 runs, 0 failed, new seed 4242): measured/predicted
(VT-only formula with par_vth 6.66) = 1.106 (2u/0.5u), 1.171 (2u/2u), 1.062 (20u/0.5u), 1.075 (20u/2u).  Sigma ratio between
2u/0.5u and 20u/2u is 7.32 vs 7.11 predicted (3 %), so the 1/sqrt(area) scaling holds.  The excess over the VT-only formula
(about 6-17 %) is larger than for NMOS (about 2 %) and is largest at small W/L, i.e. high overdrive at the fixed 20 uA tail, which
is where the mobility (par_k = 0.007) term adds; I did not compute that term precisely and the four groups share seeds
(correlated), so treat PMOS as "consistent within about 10 %, VT-only formula slightly optimistic for small W/L".
Global statistics (own spec, tt, N=100, same seeds): global-only gives vtrip sigma 0.30 mV, IDD sigma 0.41 uA (0.5 %);
mismatch-only gives vtrip sigma 4.64 mV, IDD sigma 43 uA (42 %).  Global MC is active but small.

## Defects found and fixed
1. `corners._fmt_temp` truncated fractional temperatures: 27.5 C got the same corner name (hence run directory and cache
   identity) as 27 C, so two such corners would overwrite each other.  Now `%g` with `.` -> `p` (27.5 -> `tt_27p5c_3v30`);
   integer temperatures keep their old names (checked: `ss_125c_3v00`, `ff_m40c_3v60`).
2. A Monte Carlo spec whose deck template lacks `{seed_line}`/`{seed}` was accepted silently: every seed renders the same
   deck, ngspice draws a random seed per process, and the result is not reproducible while the cache pretends it is.
   `runner.build_runs` now raises ValueError (mentions in comment lines do not count).
3. Wrong interpretation in `log/sim_harness.md` section 3: the 200 uA IDD limit failure of `ota_cmp_global` was blamed on
   "global process spread".  It is mismatch (see numbers above).  Corrected in the log.
Two regression tests added to `sim/harness/tests/test_helpers.py` (`TestVerificationFixes`); suite now 43 tests OK.

## Remaining caveats (not fixed, minor)
* README spec example contains `//` comments, so it is not literally valid JSON (illustrative only).
* Unknown `{names}` in a template are only printed once on stderr, not stored in the run record or log as README says; a typo
  will usually surface as an ngspice error (sim_error) anyway.
* `pwl_points` with all-equal bits produces a single-point PWL (ngspice may reject it); not a case the eye bench uses.
* Global MC exists only around tt, as the builder documented.
