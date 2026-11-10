# luts log (2026-11-10/11): the gm/ID lookup-table toolkit

Full how-to, tables and the "ten facts": `lut_regen/README.md`. Raw validation output: `lut_regen/validation_report.txt`.

## What exists now

* `sizing/gmid_gf180.py` - guarded wrapper around pygmid (finds tables via `$GF180_LUT_DIR`, then `analog/lvds_rx/luts`, then the
  kit folder). `sizing/selftest_gmid.py` - 296 checks against the handoff numbers (6.3 example, 6.6 tables, facts 5-7); passes on
  the kit tables and on ours.
* `luts/` (git-ignored, 709 MB): `nfet_03v3.mat`, `pfet_03v3.mat` (typical, 27 C, VSB 0..2.0 V in 0.2 V steps, 12 L values),
  `*_ss_125C.mat` and `*_ff_n40C.mat` (7 L values, VSB 0..0.8 V).
* `lut_regen/`: decks derived from the kit's, one-command regeneration (`regen_all.sh`), converter, validators.

## What the numbers mean (plain language)

* **Kit load test** (handoff 2.4): at gm/ID = 12, L = 0.5 um, VDS = 1.0 V, VSB = 0, the NMOS needs VGS = 0.8016 V, gives
  fT = 3.298 GHz and ID/W = 2.70 uA/um (pygmid; handoff expects 0.802 / 3.30 / 2.70: match). A 1 mS NMOS at gm/ID = 12 draws
  83 uA and is 30.8 um wide (7 fingers), gm/gds = 153. The PMOS is ~3x slower (fT 0.78 GHz) and 3.5x wider (108 um).
* **The regenerated tables equal the kit tables exactly** where they overlap (VSB 0, 0.2, 0.4): not "close", bit-identical.
  Meaning: the kit's gf180mcuC paths and our gf180mcuD models are the same for these devices, and my sweep is a faithful copy.
* **Independent check**: direct ngspice `.op` runs at random points agree with the table to 0.03-0.09 % in normal use (on grid,
  and between 25 mV nodes), at VSB up to 2.0 V, for both devices and for both corner tables. The only large errors are
  (a) between L grid nodes (up to 47 %: never interpolate in L) and (b) deep weak inversion between VGS nodes before filtering
  (a few %, that is linear interpolation of an exponential).
* **Corner tables**: ss 125 C (slow, hot) and ff -40 C (fast, cold) both built and spot-checked (0.025-0.042 %). They
  only reach VSB = 0.8 V and have 7 L values to keep size and time down.

## Decisions

* Kept the earlier interrupted attempt's work after re-checking it: deck derivation, converter, typical + ss sweeps (their
  numbers re-validated), then ran the ff sweeps myself and re-ran both typical sweeps from scratch to prove the pipeline
  reproduces the delivered files exactly.
* Default table location: env var, then our folder, then the kit (so the wrapper works even before regeneration).
* Corner tables are named `nfet_03v3_ss_125C` / `nfet_03v3_ff_n40C` (the `-` would be awkward in file names).
* Off-grid spot check now skips ID < 1 uA (and reports weak inversion separately) because its 2 % tolerance is meaningless
  for interpolated exponentials.

## Pitfalls hit

* `run_sweep.sh` and `regen_all.sh` disagreed (3 vs 4 arguments, output names `*_vsb2`): fixed; the ff run exercised the fixed script.
* ngspice's own log of a sweep is ~280 MB and was left behind by the interrupted attempt; now deleted by the script.
* Only claim not reproduced from the handoff: fact 8's "non-monotonic X ratio returns []" (our probe returned a number, no
  warning). Fact 10 differs: this install's design.ngspice already has statistics off.

## Verifier addendum (2026-11-11)
Independent re-check found the deliverable sound; two wrapper/documentation gaps fixed: `spice_line()` produced un-netlistable
W > 100 um instances (now splits with `m=`), and the `.option wnflag=1` requirement for LUT-faithful netlists was undocumented.
Details and evidence: `log/verify_luts.md`.
