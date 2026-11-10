# sim-harness log (2026-11-10)

What was built: `sim/harness/` (Python package, CLI, README, 41 unit/integration tests) and `sim/harness_demo/`
(demos + the Monte Carlo proof).  Everything below was observed by running it in the `apic_headless` container.
Re-run everything: `docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx bash sim/harness_demo/run_demo.sh`.

## 1. Monte Carlo on this PDK: the mechanism (handoff 9.3 was UNVERIFIED, now verified)

How the PDK does mismatch: in `sm141064.ngspice`, section `fets_mm`, each `nfet_03v3`/`pfet_03v3` subcircuit holds
`mis_vth = agauss(0, var_vth, 1)` and `mis_k = agauss(0, var_k, 1)` with
`var_vth = 0.7071*par_vth*1e-6/sqrt(Leff*Weff)`, `Leff = L - 0.15u`, `Weff = W + 0.1u` (`par_w=-1e-7`; W is the TOTAL width,
`nf` and `m` are not in the formula).  They are applied as `delvto = mis_vth*sw_stat_mismatch` and
`mulu0 = 1 - mis_k*sw_stat_mismatch`.  The 0.7071 = 1/sqrt(2) makes the *pair* difference come out as
sigma(dVT) = par_vth/sqrt(Leff*Weff) = **7.148 mV*um** (NMOS) / 6.66 (PMOS) over sqrt(area).

Experiments (`.scratch/sim-harness/mc/t1.py, t3.py`, NMOS pair, ideal 20k loads, offset found by a DC sweep):

| experiment | result |
|---|---|
| `.option seed=N` in the deck, seeds 1,1,2,3 | seed 1 twice: identical (1.48262); different seeds: different offsets (except seeds 1 and 2 which happened to agree to 0.01 mV; the other 8 seeds tried were all distinct). No seed: random every process. |
| `.control` loop: `setseed 5` then `reset` each iteration | 5 different values; iteration 0 equals the `.option seed=5` result (1.49765), so both routes use one generator sequence |
| same loop but WITHOUT `reset` (setseed only) | the same value 5 times: **`setseed` alone does not re-draw** |
| `alterparam ...` + `reset`, `mc_source` | behave like `reset` |
| the pair is a netlist with two identical devices | offset sigma matches the formula (below), which assumes independent draws; identical draws would give about 0, perfectly anti-correlated would give 1.4x |

Decision: **one ngspice process per seed with `.option seed=N`** (parallel, cached by content hash, trivially
reproducible, immune to `.control` loop quirks).  The `reset` loop is kept as a verified alternative
(`harness_demo/mc_loop_check.py`: 200 distinct values, identical in a second process, sigma ratio 0.991, no-reset loop constant).

### Pelgrom check (`harness_demo/check_pelgrom.py`, 12 gate areas x 200 seeds = 2400 runs, 53 s with 6 jobs)

Measured sigma of the input offset of an NMOS pair vs the formula (VT term plus the mobility term, the latter from the
measured gm/ID):

| W/L | Weff*Leff (um2) | measured (mV) | predicted (mV) | ratio |
|---|---|---|---|---|
| 1u/0.5u | 0.385 | 11.90 | 11.65 | 1.021 |
| 4u/0.5u | 1.435 | 6.10 | 5.99 | 1.019 |
| 8u/1u | 6.885 | 2.78 | 2.73 | 1.016 |
| 20u/2u | 37.19 | 1.19 | 1.175 | 1.013 |

All 12 points: ratio 1.013 to 1.021 (mean 1.017); fitted A_VT-equivalent 7.385 mV*um vs 7.148 (VT only) / 7.22 (with the
beta term).  Note the 12 groups use the SAME 200 seeds, so they are one random sample scaled by different areas (common
random numbers), not 12 independent confirmations; the consistent +1.7 % is that sample's sampling error (std error of
sigma at N=200 is 5 %).  Independent confirmation (`check_repro.py`, base seed 777, N = 1000, W/L = 1u/0.5u): sigma 11.946 mV
vs 11.649 predicted, ratio 1.025, **1.11 standard errors**, mean +0.31 mV (+-0.38).  So sigma follows Pelgrom within
sampling error and scales as 1/sqrt(area) over a factor 100 in area.  Plot:
`sim/harness_demo/results/pelgrom_pair/plots/pelgrom_sigma_vs_area.png`.

Reproducibility (c): re-running 1200 runs with `--force` gives results identical to the first campaign (max |diff| = 0 V);
a second run without `--force` serves 1200/1200 from the cache; editing the deck re-runs everything (0/240 cached).

Global statistics: `sw_stat_global=1` needs the PDK section `statistical`, which is a COMPLETE MOS section (it already
loads `fets_mm` and the `*_stat` models).  Loading it together with `typical` fails with "Mismatch: 24 formal but 15 actual
params" (fets_mm defined twice, reproduced with 8 orderings).  So the harness loads `statistical` INSTEAD of `typical`, and
only for process tt (there is no ss/ff/fs/sf statistical section).  Works: `ota_cmp_global.json`, mode `both`, N = 100.

## 2. Other findings that matter for every later bench

1. **Parallel ngspice thrashes by default.**  2 processes at once: 0.1 s run became 3.3 s; 6 at once: 11 s (load average 23).
   `OMP_NUM_THREADS=1` did not fix it; `OMP_THREAD_LIMIT=1` (0.087 s for 2 processes) or `OMP_WAIT_POLICY=PASSIVE` (0.17 s) do.
   The runner sets all three.  After that 2400 runs take 53 s on 6 jobs.
2. **Deck-level `.dc` plus `.tran` with `.meas` loses results in ngspice 46 batch mode**: `.dc` then `.tran` -> the tran
   measures fail ("no such vector as v(out)"); `.tran` then `.dc` -> the dc measures vanish from the log without any error.
   A `.control` block with `dc ...; meas dc ...; tran ...; meas tran ...` works.  The harness lints for this and refuses.
3. `meas ... param='(odp-odm)/0.01'` works for derived values; `meas dc x deriv v(od) at=0` failed in this setup (use two
   `find` + `param`).  `echo RESULT name $&vec` in a `.control` block is the easy way to export any number.
4. A failed `.meas` prints "Error: measure ..." and `... failed!`; those lines must not be classed as simulator errors
   (they are `meas_failed`).  ngspice returns exit code 0 even when measurements fail, so the exit code alone is useless.
5. A `{placeholder}` inside a SPICE comment line must not be expanded (the multi-line header would break the deck); the
   renderer copies comment lines verbatim.  (I hit this myself on the first run.)
6. Harmless noise in every PDK run: `lintnoi <<NAN, error = 7>>` / `llambda <<NAN, error = 7>>` messages; the harness does
   not treat them as errors.

## 3. Demo results (circuit: 5T OTA + inverter from real nfet_03v3/pfet_03v3; the limits are demo values, not design targets)

* `ota_cmp_corners` (worst5 x VIC 0.9/1.65 V, 10 runs, 1 s): all run ok.  Worst tPLH 5.99 ns at ss/125C/3.0 V/VIC 0.9 V
  (limit 5 ns -> FAIL, shown highlighted), tPHL 3.72 ns, vtrip -6.4 mV worst, IDD 87 uA worst.
* `ota_cmp_mc` (tt and ss/125C, N = 200 each): vtrip mean -5.3 mV, sigma 4.7 mV at tt; tPLH sigma 0.10 ns; histograms in
  `results/ota_cmp_mc/plots/`; PASS at mean +- 3 sigma.
* `ota_cmp_global` (mode both, N = 100): vtrip sigma 4.5 mV, IDD mean 95 uA sigma 39 uA (max 202 uA, so the demo limit of 200 uA
  fails).  CORRECTED by the verifier (2026-11-10): that IDD spread is MISMATCH, not global process spread.  Same deck, N=100, tt:
mismatch-only gives vtrip sigma 4.64 mV and IDD sigma 43 uA (42 % of the mean); global-only gives vtrip sigma 0.30 mV and IDD sigma
0.41 uA (0.5 %).  So the PDK `statistical` global section is active but small for this circuit; mismatch dominates, and process
spread is better covered by the ss/ff/fs/sf corners.  (Cause of the large IDD spread not investigated; probably inverter shoot-through following the OTA output offset.)
* `ota_cmp_eye` (PRBS7 100 Mb/s, VOD 100/350 mV, worst5): h-open 0.85 to 0.92 UI; DCD 7.9 to 15.2 % UI (the circuit's
  tPLH-tPHL asymmetry of about 1.3 ns; at TT/VIC 1.65 V the transient bench gives 2.74 vs 1.41 ns and the eye gives 12.6 % DCD =
  1.26 ns, a consistent cross-check); the DCD limit of 5 % FAILS for all runs, which is the demo showing a fail.  Eye PNGs in
  `results/ota_cmp_eye/plots/` (checked visually: clean two-lobe eye, threshold dashed).

## 4. Tests

`python3 -m unittest discover -s sim/harness/tests` -> **41 tests OK** (PRBS7 period 127 / 64 ones / all 127 words, PWL, triangle,
clock, crossings, delays, skew, missed edges, hysteresis with a model Schmitt trigger, DCD, eye with injected jitter and DCD,
wrdata reader, corners/headers, seeds, statistics, Pelgrom formula, log parsing, deck lint, render rules, plus ngspice
integration: RC time constant, cache hit/force/hash change, failed measurement, undefined model, timeout, seeded MC + post hook).

## 5. Interface decisions (and why)

* Spec = JSON (YAML if installed): no dependency, a learner can edit it.  Limits in SI units, `scale`/`unit` only for display.
* Cache key = SHA-256(rendered deck, ngspice version, stimulus files, project `.include` files, harness version).  PDK files
  are not hashed (read-only).  Timeouts are never cached.
* MC pass rule = mean +- k sigma inside the limits AND no failed sample (default k = 3; +-6 sigma always printed because the
  handoff talks about 6 sigma); min/max also printed.  Failed samples are listed, never dropped.
* Worst case = smallest margin to a limit (per metric, over runs or over MC groups).
* Eye "jitter" counts all edges, so data-dependent DCD is inside it (conservative horizontal opening).

## 6. Open items

* PMOS / mixed-pair Pelgrom scaling was not separately measured (same formula, par_vth = 6.66 mV*um); only NMOS pairs were.
* `wnflag` (handoff 9.2) is not tested here; not part of this item.
* Post-layout (extracted) netlists: the runner just takes any deck, but no pex flow was exercised here.
