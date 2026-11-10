# Verification of the "luts" foundation item (2026-11-11)

Verdict: the deliverable reproduces and is usable. Two gaps found and fixed (below). Scripts: `lut_regen/work/verify/` (git-ignored).

## What I re-ran and saw

| check | result |
|---|---|
| `sizing/selftest_gmid.py` on delivered tables, from default cwd | `296/296 checks passed`, exit 0 |
| same on the kit tables (`GF180_LUT_DIR` = kit `simulation/`, run from `/tmp`) | `296/296 checks passed`, exit 0; 6.3 NMOS ID=83.33 uA W=30.84 um nf=7 VGS=0.8016 |
| self-test can fail (mutation: corner tables renamed as typical) | exits 1 (ValueError from the gm/ID guard) |
| delivered typical tables vs kit, VSB 0/0.2/0.4, 13 fields x 2 devices | `np.array_equal` True everywhere, max abs diff 0 (TEMP label 300.15 vs 300.0 only) |
| grid integrity | VSB multiples of 0.2 exactly; no NaN; ID(VGS) never decreasing; ID falls with VSB (body effect) |
| corner tables vs typical | physically right: ss/125C VT up (0.716 vs 0.711 V NMOS), ID at VGS=1.5 x0.64; ff/-40C VT down (0.673), ID x1.53; weak-inversion ID higher when hot |
| regenerated ss/125C NMOS from scratch (fresh decks into /tmp, run from `/tmp`, own output dir) | decks identical to delivered; 240 s ngspice, 619116 rows; all fields and axes `array_equal` True vs delivered table |
| **independent** ngspice check, my own script, `.option temp` instead of `.temp`, new seed, on-grid random points (8 per typical device, 4 per corner device, VSB up to 2.0 V) | ID, gm, gds, gmb, VT, Cgg, Cgd, Cdd all <= 0.05 % (worst: gds 0.04 %). Cgg/Cgd/Cdd taken from AC analysis at 1 MHz (not from `@m[cgg]`), so the converter's overlap-capacitance formulas are verified, not just copied from the kit |
| fact 9 (L between nodes) | builder's numbers (22 %/47 %) in report are consistent with `validation_report.txt` |

Not independently re-run: the 15-minute typical sweeps (builder's from-scratch reproduction plus my corner reproduction and the 0.04 % direct-simulation check cover this).

## Problems found

1. **`spice_line()` emitted instances ngspice cannot load** when total W > 100 um (the handoff 6.3 PMOS: W=107.9 um nf=22 gives
   "could not find a valid modelname"). The builder's checks never simulated a sized device. FIXED: instances are split with `m=`
   (`W=53.95u nf=11 m=2`); `m=1` output is unchanged for smaller devices.
2. **LUT-faithful netlisting needs `.option wnflag=1`** (undocumented). Sizing with the wrapper, netlisting with `spice_line`,
   simulating `.op`:
   - with `wnflag=1`: ID, gm, Cgg match the prediction to 0.02-0.1 % (NMOS 1 mS: 1.0010 / 1.0005 / 1.0011; PMOS 1 mS: 1.0001 / 1.0003 / 1.0006);
   - without it (default): gm 0.98-1.01, ID 0.98-1.01 of prediction, gds down to 0.97, and Cgg 1.099 for L=0.28, W=29.8 um (a different
     BSIM4 width bin than the 5 um table; Cgg is independent of nf when wnflag=0, 36.5 fF vs 33.2 predicted, and 33.2 with wnflag=1).
   Documented in the docstring and README. Design decks must set `.option wnflag=1` and use nf ~ W/5 um.
3. Minor: `pygmid.lookup` with a non-GM_ID X above the table max prints a warning but returns a number (GM_GDS=1000 -> -6e-4); only
   `at_gmid` (X = GM_ID) is range-guarded. Documented. The builder's correction about fact 8 (no "Crossing warning" for GM_GDS=100) is right:
   at L=0.5 there is a single crossing at VGS=1.025 V, so it is not actually ambiguous there.

## Caveats for downstream users (unchanged from builder, confirmed)
* Use L on the grid (0.28 0.29 0.3 0.4 0.5 0.6 0.7 0.8 0.9 1 2 3 um); corner tables only 0.28 0.3 0.4 0.5 0.7 1 2 and VSB <= 0.8 V.
* The nfet/pfet 5 V tables were not regenerated (kit versions remain reachable through the wrapper fallback).
* Numeric precision of the tables is about 4 digits (kit deck writes `numdgt = 3`); it only matters in deep weak inversion.

## Files changed by the verifier
`sizing/gmid_gf180.py` (spice_line m-split, docstring), `lut_regen/README.md` (appended section), `log/luts.md` (addendum), this file.
