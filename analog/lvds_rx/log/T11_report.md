# T11 report: post-layout re-simulation and the second audit (2026-11-14 to 2026-11-22)

T11 re-simulates the drawn and extracted macro against the pre-layout design (gate TBL, PLAN_V2 3.2 / 6.5) and audits the
whole result a second time (AUDIT_2, PLAN_V2 5.2 item 6).  It took three design iterations; the owner decided two test
definition questions (D-019, D-020).  Working notes with every number and run: `log/T11_notes.md`.

Status: **closed.**  Gate TBL PASS (with D-019); iteration-2 full pre-layout regression green with D-020 (19 PASS, TB11
not applicable); `results/AUDIT_2.md`: PASS with findings; `make check` green.

## What happened

| Iteration | Trigger | Change | Outcome |
|---|---|---|---|
| 0 (T10 layout) | first post-layout suite | none (the T10 macro) | gate TBL FAIL: extracted tPD at ss/125C/3.0 V 6.76 ns against 5 ns (VID 350 mV), 8.22 against 8 ns (VID 100 mV); chain bandwidth 56 -> 37 MHz.  The pre-layout netlist had no wiring capacitance and junctions 2.84 x too small. |
| 1 (D-016) | iteration 0 | layout parasitic estimate in the simulation netlist (31 nets, extracted wiring x 1.2, calibrated on 36 TB4 points); stage 2 re-sized (n_t2 5 -> 10, gmid_s2 12 -> 8, L_ld 0.40 -> 0.28); re-layout | extracted TB10 lane delays 3.71 ns (5.36 before); the full regression (5a78f0d) failed TB3_hmc: 17 of 600 hysteresis Monte Carlo runs under 6 mV at ff/-40C/3.6 V (mismatch spread 15-22 % of the mean); TB3_trip 4 solver stalls |
| 2 (D-017, D-018) | iteration 1 | stage-2 positive feedback alpha 1.25 -> 1.5 = (4, 6) fingers, Rs 5 um wide (365 ohm), load fingers 1.85 um; TB3 retry variants (solver only); D-017's alpha 1.4 could not be drawn (D-018) | TB3_hmc 600 / 600 inside 6-35 mV (7.30-24.20 mV); TB3_trip 270 / 270; layout 650 x 194.2 um; extracted TB10 lane delays 3.50 ns; gate TBL failed only two TB8 power-up checks below about 1.2 V of supply -> D-019; the full regression then flagged one TB7_mc run -> D-020 |

## D-019 (the owner's decision)

Gate TBL and TB8 failed only while the supply is below about 1.2 V, before the output chain (a NAND and three inverters)
conducts: a pulse-measurement defect (a 3 ns runt read as 0.084 ns), and an extracted EN = 0 output of 0.363 V against
0.33 V on the bench's 50 ns setup ramp, which is not a spec ramp.  The owner was shown three options (this waiver, a design
change without on-chip resistors, or leaving both gates failing) and the reasons an off-chip pull-down cannot help
(RXn_O and EN are core-side pins), and chose the waiver on 2026-11-21.  Applied 2026-11-22 (commit `ac17072`):

* cases 0-1: off-state judged from 100 ns (as D-011 for the pulse check); whole-run value reported;
* pulses: completed swings only, as `lib_tb.pulses_norm` documents; runts by their own width;
* added: cases 6 / 7 = EN = 0 on the 1 us / 100 us spec ramps, gated 0.33 V (case 7 ends 0.2 us after its ramp: a 10 us
  tail stalled ngspice at four corners in every solver variant); case 5 early_high_v gated;
* gate TBL: the wake-up pulse (cases 3, 5) worst against worst over 45 corners, full coverage required.

Result: TB8 360 / 360, PASS (EN = 0 output 0.262 V worst, shortest pulse 3.0 ns); gate TBL PASS (178 pairs, largest
margin use 23.6 %, wake-up pulse 3.0 -> 4.0 ns; D-012 met: A1 4.78, tPD 2.48 / 3.10 ns at ff/125C/3.6 V, VIC 0.05 V).

## D-020 (the owner's decision)

The iteration-2 full regression (2026-11-22, 7681 s, commit `76d4236`) passed 18 gates and failed TB7_mc in 1 of 1500
runs (fs/27C/3.3 V, VIC 1.2 V, seed 1793293142).  Lane 0 made one clean settling flip whose VDD/2 crossing fell at
149.236 ns, 0.76 ns before the 150 ns idle window; the window saw only the edge's tail and undershoot (0.136 V
peak-to-peak, no crossing), which D-010's "> 0.1 V without a crossing" clause reads as an oscillation.  The owner was
shown three options (a 5 ns guard, leaving TB7_mc failing with the explanation, starting the window later) and chose the
guard on 2026-11-22 (commit `260264a`): the idle window's crossings are counted from 145 ns; the excursion is still
judged in [150, 600] ns.  Re-run from the cache (post only): of 2475 TB7, TB7_mc and tbl_idle runs exactly that run
changed (osc_flag 1 -> 0, one settling flip at 149.2 ns, limit 500 ns).

## Results

Pre-layout full tier (`results/gates.json`, `results/REPORT.md`; `tools/run_full.sh 4` at `ac17072`, D-020 applied
after): **19 PASS, TB11 not applicable** (it needs ladder rung R6, not taken), every gate at its expected run count.

| Gate | Runs | Headline |
|---|---|---|
| SELFTEST | 94 | harness self-test |
| TB1 / TB2 | 987 / 315 | operating point; chain bandwidth |
| TB3_trip / TB3_off / TB3_hmc | 270 / 15000 / 600 | trip points; offset Monte Carlo; hysteresis Monte Carlo 7.30-24.20 mV inside 6-35 mV |
| TB4 / TB4b | 630 / 70 | propagation delay; its change over VID 200-450 mV (TB4b, slowest tPD there 4.597 ns at ss/125C/3.0 V, VID 0.2 V) |
| TB5 | 180 | eye >= 0.926 UI, no bit errors |
| TB6 | 20 | supply / common-mode disturbance |
| TB7 / TB7_mc | 945 / 1500 | idle inputs: no oscillation, no pulse < 2 ns (D-010, D-020) |
| TB8 | 360 | enable and power-up: EN = 0 output 0.262 V worst (limit 0.33 V), shortest wake-up pulse 3.0 ns (D-019) |
| TB9 / TB10 / TB12 | 180 / 10 / 40 | input current; three lanes; package sweep |

Audit records: `tools/audit_hashes.py --tier full` 17 benches, 0 not current; mutants 11 of 11 detected (each control
passed); `results/manifest.json` matches every input except `spec/decisions.yaml`, which gained D-020 after the run.

Post-layout (gate TBL, `results/post_layout/TBL.md`): every timing, gain, eye, hysteresis, offset, package and three-lane
check within 30 % of its margin; slow-corner tPD at VID 350 mV 4.54 -> 4.57 ns (8 % of the margin); layout offset 0.000 mV;
ten gains of margin over 30 % explained in AUDIT_2.

Layout from the GDS alone (AUDIT_2 item 4): KLayout 0 / 0, Magic DRC 0, via arrays 0, LVS unique against the delivered
schematic and, dummies removed by the audit's own rule, against the frozen reference; fresh PEX identical.

## Known limitations (in the package, `package/KNOWN_LIMITS.json`)

* With EN = 0 and the supply below about 1.2 V the outputs float to about a third of the supply: 0.363 V extracted on a
  50 ns ramp, 0.316 V on the 1 us spec ramp at ss/-40C (14 mV under 0.33 V).  The integrator keeps the logic that reads
  RXn_O in reset, and EN = 0, until VDD >= 2.0 V (D-008).
* Failsafe off in v0 (idle output undefined); secondary ESD unqualified; latch-up unverified; pad ESD diode conducts from
  0.58 V into an unpowered DVDD (spec.yaml documented_deviations).
* Chip-integration items (handoff 15-18) open until PLAN_V2 P7/P8.

## Decisions taken in T11

D-015 (gate TBL defined), D-016 (iteration 1), D-017 / D-018 (iteration 2), D-019 (TB8 power-up checks, owner's choice),
D-020 (TB7 idle-window guard, owner's choice).  Rulings: `results/AUDIT_2.md` (all accepted).

## Open

* Push: the branch's commits since 66d34d0 are local; pushing needs the owner's yes.
* AUDIT_2 findings F2 (harness cache key), F8 / F13 (sizing asserts and report text, at the next sizing change).
* T12 packaging (built: `make package` PACKAGE CHECKS PASS, all_ok) and T13 close.
