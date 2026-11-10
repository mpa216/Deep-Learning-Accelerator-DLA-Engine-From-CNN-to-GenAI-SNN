# lut_regen - regenerate the gm/ID lookup tables (LUTs) on this machine

A gm/ID LUT is a 4-D table of transistor small-signal quantities (ID, gm, gds, capacitances, ...)
over `[L, VGS, VDS, VSB]` for a fixed width (W = 5 um, one finger). It is produced by sweeping one
transistor in ngspice, writing the numbers to text, and converting the text to a `.mat` file that
`pygmid` (and `sizing/gmid_gf180.py`) reads. This folder reproduces the kit's tables on our
`gf180mcuD` models, with a wider body-bias range (VSB up to 2.0 V instead of 0.4 V).

## One command

Run inside the container (host has no tools). From the worktree root on the host:

    docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx bash lut_regen/regen_all.sh all

`regen_all.sh [typical|corners|all]`:

| output (in `../luts/`, git-ignored)        | corner / T      | L values | VSB (V)   | size  |
|--------------------------------------------|-----------------|----------|-----------|-------|
| `nfet_03v3.mat`, `pfet_03v3.mat`           | typical, 27 C   | 12 (as kit) | 0..2.0 step 0.2 | 243 MB each |
| `{n,p}fet_03v3_ss_125C.mat`                | ss, 125 C       | 7: 0.28 0.3 0.4 0.5 0.7 1 2 | 0..0.8 | 64 MB each |
| `{n,p}fet_03v3_ff_n40C.mat`                | ff, -40 C       | same 7   | 0..0.8    | 64 MB each |

Measured here (machine otherwise idle, 2 jobs in parallel): ~15.5 min per typical sweep (927 s ngspice
+ 11 s conversion), ~4.3 min per corner sweep. A from-scratch re-run of both typical sweeps with the final scripts
reproduced the delivered `luts/nfet_03v3.mat` and `pfet_03v3.mat` exactly (`np.array_equal` True on all fields). `all` ends with `validate_all.sh`, which writes `validation_report.txt`.
Peak extra disk about 1 GB per running typical sweep (raw text, deleted right after conversion).
`LUT_OUT=<dir>` redirects the output folder (used for the reproducibility check below).

## Files

| file | role |
|------|------|
| `make_decks.py` | derives the 6 decks in `decks/` from the **kit's** `techsweep_*.spice` (snapshot in `decks/kit_original/`; the kit folder is never written). Changes only: model paths C->D, `.lib` corner + `.temp`, VSB sweep stop, L list, `set num_threads=1`, output names. |
| `run_sweep.sh` | one ngspice sweep -> text -> `.mat`, then deletes text/raw/log. |
| `techsweep_txt2mat.py` | CLI port of the kit notebook `techsweep_txt_to_mat.ipynb` (same column handling, same CGG/CGD/CDD overlap-capacitance definitions) plus reshape self-checks. |
| `validate_vs_kit.py` | regenerated vs kit tables on the shared grid. |
| `spot_check.py` | independent direct-ngspice `.op` check at random points. |
| `facts_check.py` | live evidence for the "ten facts". |
| `validate_all.sh` | runs all of the above plus `sizing/selftest_gmid.py`. |
| `validation_report.txt` | output of the last `validate_all.sh`. |

Use of the tables: `GF180_LUT_DIR` overrides the table folder; otherwise `sizing/gmid_gf180.py`
looks in `analog/lvds_rx/luts`, then in the kit's `simulation/` folder. Corner tables are loaded by
name: `lut('nfet_03v3_ss_125C')`.

## Validation results (all observed 2026-11-10/11, see `validation_report.txt`)

* **Regenerated vs kit** (typical, VSB 0/0.2/0.4, all 12 x 133 x 133 points): ID, GM, GDS, CGG, CDD,
  VT, CGD, STH are **bit-identical** (`np.array_equal` True, max abs difference 0.0). So the kit's
  `gf180mcuC` paths and our `gf180mcuD` models give the same numbers: the C/D worry is closed. The only
  metadata difference is TEMP 300.15 K (ours, 27 C) vs 300.0 K (kit label); the data are the same.
* **Spot check vs direct ngspice `.op`** (6 random points per device and mode, ID, gm, gds, cgg):
  - on grid nodes, VSB up to 2.0 V: worst 0.034 % (n), 0.041 % (p);
  - VGS/VDS off the 25 mV grid, ID > 1 uA (interpolation exercised): worst 0.060 % (n), 0.085 % (p);
  - weak inversion off-grid (informative): worst 0.15 % (n), 0.83 % (p);
  - corner tables on grid: ss 125 C 0.025 % / 0.032 %, ff -40 C 0.032 % / 0.042 % (n / p).
  The first run of the off-grid mode (before the ID > 1 uA filter was added) showed 3.7 % / 6.1 %, all at ID of
  1e-10..1e-7 A (VGS 0.9 V, L = 0.4 or 3 um, VSB >= 1.4 V): linear interpolation of an exponential subthreshold
  current over a 25 mV step. That is an interpolation property, not a data error.
* **Interpolation in L is NOT accurate** (fact 9): L midway between grid nodes (e.g. 1.5 um between 1 and 2 um)
  is off by up to 22 % (n) and 47 % (p) in gds, 10-16 % in ID. Use L on the grid.

## The ten "facts that will bite you" (handoff section 6.1) on this machine

| # | claim | status | evidence |
|---|-------|--------|----------|
| 1 | one key = device name; fields INFO..SFL; 4-D `[L,VGS,VDS,VSB]`; no leakage / VDSAT | **confirmed** | `facts_check.py`: keys `['nfet_03v3']`, 22 fields listed, ID shape (12,133,133,11), no IG/VDSAT field. |
| 2 | typical/NOM, 27 C, W=5, nf=1; L list; VGS,VDS 0..3.3 step 25 mV; VSB only {0,0.2,0.4} | **confirmed for the kit tables; deliberately changed in ours** | kit: VSB [0,0.2,0.4] (selftest prints the grid), L = 0.28 0.29 0.3 0.4 0.5 0.6 0.7 0.8 0.9 1 2 3, 133 points per voltage axis. Ours: VSB 0..2.0 (11 points). |
| 3 | 3.3 V LUTs were netlisted on gf180mcuC; C and D share front-end models | **confirmed** | regenerated on D is bit-identical to the kit tables (max abs diff 0.0 for 7 fields x 2 devices). |
| 4 | PMOS tables store magnitudes | **confirmed** | pfet: min ID = 0.0 (>= 0), min VT = 0.703 V (> 0), VGS min 0. Spot-check decks use gate = -VSG, drain = -VSD, bulk = +VSB and reproduce the LUT to 0.04 %. |
| 5 | first keyword of `lookup` sets the independent variable; `GM_ID` second silently gives a sweep | **confirmed** | selftest probe: GM_ID first -> size 1, GM_ID second -> size 133. |
| 6 | default VDS = max/2 = 1.65 V | **confirmed** | probe: ID/W default 2.7203 uA/um equals VDS=1.65 (2.7203), VDS=1.0 gives 2.7024. |
| 7 | pygmid extrapolates silently; negative ID/W at VSB = 0.8 V (kit) | **confirmed (kit)**; the wrapper guard blocks it | kit tables: unguarded ID/W at VSB 0.8 V = -1.1029 uA/um. Ours: at VSB 2.4 V (outside our table) 1.2963 uA/um, still extrapolated garbage. The guard raises `ValueError` in both. (`lookupVGS` mode 2 at VGB = 2.0 V -> 83 V was not re-tested; we never use mode 2.) |
| 8 | GM_ID as X uses the strong-inversion branch; GM_GDS (non-monotonic) fails | **confirmed (partly)** | GM_ID X -> single value (GM_CGG at gm/ID 12 = 2.07e10 rad/s = 3.298 GHz x 2 pi). The probe `GM_GDS=100` returned a value (5.0006 for GM_ID) with no "Crossing warning" print captured, so the "returns []" part of the claim is **not reproduced** here; treat any non-monotonic X ratio as unreliable anyway. |
| 9 | L grid coarse, linear interpolation in L | **confirmed** | `spot_check.py --mode lmid`: up to 22 % (n) / 47 % (p) error in gds at off-grid L. |
| 10 | upstream design.ngspice turns statistics on | **not applicable here / different**: this install's `design.ngspice` has `sw_stat_global = 0`, `sw_stat_mismatch = 0` (lines 64-65) | `grep` of the file inside the container. Our sweeps are deterministic; the direct-ngspice spot check (which includes this file) agrees to 0.04 %. Decks of other agents should still set the switches explicitly. |

## Gotchas hit while building this

* The kit folder's `xschemrc` makes xschem overwrite the kit's `techsweep_nfet_03v3.spice`; that is why `decks/kit_original/` holds a snapshot and `make_decks.py` reads it, not the live file.
* ngspice is OpenMP-threaded; on a one-transistor circuit extra threads only spin-wait (3 sweeps were ~30x slower on a busy machine). Decks set `num_threads=1` and `run_sweep.sh` exports `OMP_NUM_THREADS=1`.
* The sweep stop values carry a +0.001 overshoot (`-2.001`) so the last grid point is not lost to floating-point accumulation in `compose`.
* The ngspice log of a full sweep is ~280 MB (it prints the operating-point vector); `run_sweep.sh` deletes it.
* Capacitance names in ngspice are `capbd/capbs`, not `cbd/cdd` (the latter print ~0 silently).

## Added by the independent verification (2026-11-11, see `log/verify_luts.md`)

* **Netlisting a sized device: use `.option wnflag=1`.** The LUT was swept at W = 5 um, one finger. ngspice picks the BSIM4
  width bin from the instance's *total* W unless `wnflag=1` (then from W/nf). Measured with `sizing/gmid_gf180.size()` plus a
  direct `.op`: with `wnflag=1` ID, gm, gds and Cgg match the LUT prediction to 0.1 % (nf ~ W/5 um); without it ID/gm are ~1 %
  off and Cgg is 10 % off at L = 0.28 um (W = 30 um sits in a different bin than the 5 um table).
* **Total W > 100 um cannot be netlisted without `wnflag=1`** ("could not find a valid modelname"; the 1 mS PMOS of handoff 6.3
  is 107.9 um). `spice_line()` now splits such devices into `m=2` (or more) identical instances.
* `pygmid.lookup` with a ratio other than GM_ID as X (e.g. `GM_GDS=1000`, above the table maximum) prints "Look up warning ...
  Output is NaN" but *returns a number* (-6e-4 here). Only the wrapper's `at_gmid` (GM_ID as X) has a range guard.
