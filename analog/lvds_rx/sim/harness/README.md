# harness: reusable ngspice automation for the LVDS RX project

Python standard library + numpy (+ matplotlib for PNGs only).  Runs inside the `apic_headless` container
(ngspice-46 + the GF180 PDK).  A testbench author writes **one deck template, one spec file, one launch line**.

```
docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx \
    python3 sim/harness/cli.py run sim/<tb>/<tb>.json            # add --jobs 6 --force --corners worst5 --n-mc 50
```
(or from Python: `from harness import run_spec; run_spec("sim/<tb>/<tb>.json")`, with `sim/` on `sys.path`)

Exit code 0 = every run ran cleanly and every limit is met; 1 otherwise.

## What you get per run of a spec

`<spec dir>/results/<name>/` contains `summary.md` (pass/fail table, worst case highlighted, failed runs listed),
`results.json` / `results.csv` (every run, including failed ones, with status), `plots/` (histograms for Monte Carlo;
whatever your hooks write) and `work/<run-id>/` (the rendered `deck.spice`, `ngspice.log`, `result.json`, your `wrdata`
files).  `work/` is git-ignored.  Reruns are incremental: a run is skipped when the SHA-256 of the rendered deck
(+ ngspice version + stimulus files + `.include`d project files) is unchanged; `--force` re-runs everything.

## 1. The deck template (plain SPICE)

```spice
* my_tb.spice
{header}                      <- corner header: .param sw_stat_*, .lib sections, .temp
{seed_line}                   <- '.option seed=N' in Monte Carlo runs, empty otherwise
vdd vdd 0 {vdd}
vcm inn 0 {vic}               <- {vic} comes from the spec "grid" or "vars"
.include {deck_dir}/../../netlist/lvds_rx_core.spice     <- {deck_dir} = directory of the template (cwd of a run is its run dir)
...
.control
tran 20p 60n
meas tran tplh trig v(vid) val=0 fall=2 targ v(out) val='{vdd}/2' rise=2     <- parsed from the log
echo RESULT idd $&idd         <- optional: any number you want as a metric ("RESULT name value")
wrdata eye.txt v(out)         <- lands in the run dir; read it in a `post` hook
.endc
.end
```

* Known placeholders: `{header} {seed_line} {seed} {vdd} {temp} {corner} {process} {deck_dir} {run_dir}` plus every key of
  `grid` / `vars`.  A `{word}` that is not known is left alone (SPICE `{expr}` stays legal) and is listed in the run
  log so a typo is visible.  Comment lines (starting with `*`) are never expanded.
* **One analysis per deck, or use a `.control` block.**  Measured on ngspice 46: deck-level `.dc` + `.tran` together
  with `.meas` loses the measurements of one of them (tran meas: "no such vector"; reverse order: dc meas vanish).
  The harness refuses such a deck with an explanation.  Inside `.control`, `dc ...; meas dc ...; tran ...; meas tran ...`
  works.
* Every `.meas` / `meas` name must appear in the log; one that is missing or printed as `failed` makes the run
  `meas_failed`.  Nothing is ever dropped silently.

## 2. The spec file (JSON; YAML also works if PyYAML is installed)

```json
{
  "name": "my_tb",
  "deck": "my_tb.spice",
  "corners": "worst5",                       // set name, "proc:temp:vdd[:res=res_ss]" string, or a list of those
  "grid": {"vic": [0.1, 1.2, 2.3]},          // cartesian product; values go to {vic}
  "vars": {"ui": 1e-8},                      // constant extra placeholders
  "mc":   {"n": 200, "mode": "mismatch", "seed": 1234, "k": 3},   // optional; see section 4
  "limits": {
     "tplh": {"max": 5e-9, "scale": 1e9, "unit": "ns"},           // limits in SI units, scale only for display
     "vtrip": {"min": -0.05, "max": 0.05, "scale": 1000, "unit": "mV"}
  },
  "prep": "hooks.py:prep_stim",              // optional: writes stimulus files into the run dir
  "post": "hooks.py:post_eye",               // optional: reads wrdata, returns extra metrics
  "timeout": 120, "jobs": 3
}
```
(The `//` comments are for explanation only; real JSON has none.)  All paths are relative to the spec file.  `limits` may omit `min` or `max`.  A limited metric that is missing or
NaN FAILS (never skipped).  Without MC: every run is checked, the worst case per metric (smallest margin) is shown in
bold.  With MC: the runs of one (corner, grid point) form a group; it passes if mean +- k sigma is inside the limits
and no sample failed (min/max and +-6 sigma are printed as well).

Hooks: `prep(ctx) -> {filename: text}` (ctx: run_dir, params, corner, seed, vars); `post(ctx) -> {metric: float}`
(ctx: run_dir, params, corner, seed, measures, vars), called only for runs with status ok.

Run statuses: `ok`, `meas_failed`, `nonconverged` (no convergence / timestep too small / singular matrix ...),
`sim_error` (netlist error, undefined model, nonzero exit ...), `timeout`, `post_error`.

## 3. Corners (`corners.py`)

`Corner(process, temp, vdd, res, moscap, diode)`; the passive sections default to the process family
(fs/sf use typical passives, as the PDK does).  Names look like `ss_125c_3v00`, `ff_m40c_3v60`.
Sets: `tt` (1), `worst5` (tt 27C 3.3V, ss 125C 3.0V, ff -40C 3.6V, fs, sf at 27C 3.3V), `speed4` (ss/ff paired and
cross-paired hot/cold, 4), `tt_temps` (9), `full45` (5 process x 3 T x 3 VDD).
`python3 sim/harness/cli.py header ss:125:3.0 --mc mismatch` prints a header.  The header always sets
`sw_stat_global`, `sw_stat_mismatch`, `mc_skew`, `res_mc_skew`, `cap_mc_skew`, `fnoicor` explicitly and never includes
`design.ngspice`; missing `sw_stat_global`/`sw_stat_mismatch`/`res_mc_skew`/`fnoicor` is a hard ngspice error.

## 4. Monte Carlo: how it works on this PDK (measured, see `log/sim_harness.md`)

* The mismatch values are `agauss()` parameters inside the PDK subcircuit `fets_mm`: one independent draw **per
  device instance**, made when the netlist is parsed.  Two identical transistors in one netlist differ.
* **`.option seed=N` in the deck** makes the draws reproducible (same N, same numbers, also in a new process);
  different N, different numbers.  The harness therefore runs **one ngspice process per seed** (`mc.n` seeds derived
  from `mc.seed`), in parallel and cached.  This is the default and the recommended method.
* In-deck alternative: `setseed N` once, then `reset` before every iteration inside a `.control` loop.
  `setseed` without `reset` returns the same value every time.  Demonstrated in `harness_demo/mc_loop_check.py`.
* `mode`: `mismatch` (sw_stat_mismatch=1), `global` (sw_stat_global=1), `both`.  For global the PDK section
  `statistical` is loaded **instead of `typical`** (it is a complete MOS section; loading both fails with
  "Mismatch: 24 formal but 15 actual params"), so global statistics exist only around the tt process; the harness raises
  an error for other processes.
* Pelgrom check: for the NMOS pair offset, sigma(pair) = A_VT / sqrt(Weff * Leff), A_VT = 7.148 mV*um (PMOS 6.66),
  Weff = W + 0.1 um, Leff = L - 0.15 um (`mc.pelgrom_pair_sigma`).
* Helpers in `mc.py`: `make_seeds`, `stats` (n, n_bad, mean, sigma, min, max, mean +- k sigma), `check_limits`,
  `histogram` (PNG with Gaussian fit, +-k sigma and limits).

## 5. Stimulus and analysis helpers

`stimulus.py`: `prbs7`, `pwl_points`, `diff_prbs` / `write_diff_prbs` (complementary P/N PWL include file around VOS
with differential amplitude VOD, UI, rise time), `triangle` (hysteresis sweeps), `clock_pwl`, `clock_source_line`.

`analysis.py` (numpy): `load_wrdata`, `crossings` (interpolated), `prop_delays` (tPLH, tPHL, mean, pulse skew,
missed-edge count), `slew_times`, `hysteresis` (VTH+, VTH-, VH, offset from a slow triangle), `duty_cycle` (t_high,
t_low, DCD = |t_high - t_low|/2), `eye_fold`, `eye_metrics` (peak-to-peak crossing jitter, horizontal opening, DCD in UI,
vertical opening; edges are re-centred on their circular mean; all edges count, so data-dependent DCD is part of the
jitter number), `plot_eye` (PNG).  Missing quantities are NaN, never 0.

## 6. Worked example: a new testbench in three files

`sim/tb4_pd/tb4_pd.spice` (template as in section 1), `sim/tb4_pd/tb4_pd.json`:
```json
{"name": "tb4_pd", "deck": "tb4_pd.spice", "corners": "full45", "grid": {"vic": [0.1, 1.2, 2.3]},
 "limits": {"tplh": {"max": 5e-9, "scale": 1e9, "unit": "ns"}, "tphl": {"max": 5e-9, "scale": 1e9, "unit": "ns"}}}
```
launch: `python3 sim/harness/cli.py run sim/tb4_pd/tb4_pd.json --jobs 6`, then read
`sim/tb4_pd/results/tb4_pd/summary.md`.  Full examples with all features: `sim/harness_demo/`
(`ota_cmp_corners.json`, `ota_cmp_mc.json`, `ota_cmp_global.json`, `ota_cmp_eye.json` + `demo_hooks.py`,
`pelgrom_pair.json`).

## 7. Gotchas found while building this

* **Parallel ngspice thrashes unless OpenMP is limited.**  ngspice is OpenMP-built; with 2 or more processes at
  once a 0.1 s run took 3 to 10 s (load average 23).  `OMP_NUM_THREADS=1` alone did NOT help; `OMP_THREAD_LIMIT=1`
  (or `OMP_WAIT_POLICY=PASSIVE`) did.  The runner sets all three.  If you start ngspice yourself in parallel, set them.
* Statistical (global) mode replaces `typical`; see section 4.
* A `{header}` mentioned inside a comment line would expand into several lines and break the deck, so comment lines
  are copied verbatim.
* The runner starts ngspice with the run directory as working directory: use `{deck_dir}` / absolute paths in
  `.include`.

## 8. Tests

`python3 -m unittest discover -s sim/harness/tests -v` (from `analog/lvds_rx`; 41 tests: PRBS period/balance, PWL,
crossings, delays, hysteresis, eye with known jitter/DCD, headers, seeds/stats, log parsing, and ngspice integration
tests for cache/force/failed-meas/timeout/seeded runs).
`bash sim/harness_demo/run_demo.sh` re-runs all demos and the Monte Carlo mechanism checks from a clean state.
