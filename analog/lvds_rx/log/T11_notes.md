# T11 working notes: post-layout re-simulation and final audit (started 2026-11-14, owner's go-ahead "Yes go ahead")

Solo, small pieces with one local commit each. Simulations with 4 parallel jobs. Report and wait for the owner before T12.

## Scope (PLAN_V2 6.5, gate TBL of spec/gates.yaml)

About 100 runs on the PEX netlists of T10 (`results/layout/`): TB1 op at VIC 1.2 V (tt), TB2 ac, TB3 DC trips and offset
at 3 VIC x worst5, TB4 tPD at 2 VID, TB5 eye at 100 and 200 Mb/s with the TB12 package corners at the worst corners, TB7
idle, TB8 EN, TB10 three lanes. Gate: every metric within 30 % of its margin to the limit of its pre-layout gate. Audit
condition D-012 (AUDIT_1): re-check the fast-hot-3.6 V corner after extraction.

Findings so far: every bench instantiates the whole macro `lvds_rx_x3` as `xdut` (the PEX subckt has the same name and
port order). TB1, TB2 and TB3_off also probe internal nodes by the pre-layout hierarchy (`v(xdut.xl0.xpre.tp)`,
`v(xdut.vbn)`, ...); TB2 and TB3_off reference devices (`xdut.xl0.xhyst.xmlc1.m0`). Node probes can be served by naming
the PEX nodes after the pre-layout paths (the layout uses the reference's own net names); device probes cannot (one
schematic device is several layout fingers).

## Pieces

| Piece | What | State |
|---|---|---|
| 0 | `results/layout.json` for gate LAYOUT (T10 left it out), evaluated with `flow/gates.py --phases layout --out results/gates_layout.json` | done: PASS |
| A | PEX node names = pre-layout hierarchical paths (probe-compatible macro netlists) | done (b91c4d2) |
| B | `sim/tbl_*` specs (the pre-layout benches with the PEX include, the 6.5 corner / grid subset) + cost of one run each | done (8893ac1); RC repair ccff3ff |
| C | the runs (detached, 4 jobs) | iteration 0 done (c9190a5): TBL FAIL -> iteration 1 |
| D | evaluator (post vs pre, 30 % of margin) and gate TBL | done (evaluate.py, D-015) |
| I1 | iteration 1 (D-016): estimate in the sim netlist + stage-2 re-size; full regression; re-layout (lane, bias, macro); PEX; TBL again | design 96c5c2e, layout 9a957e2; regression 5a78f0d: TB3_hmc FAIL (hysteresis spread) -> iteration 2 |
| I2 | iteration 2 (D-017, corrected by D-018): stage-2 alpha / Rs for the hysteresis Monte Carlo; TB3_trip / TB3_hmc solver retries | design + layout 29faf2c (alpha 1.5 = (4, 6), Rs 5 um wide); post-layout suite and full regression running (2026-11-21, `.scratch/t11/iter2/chain_after_tbl.py` fills freed slots, max 4 simulations) |
| E | AUDIT_2, REPORT, DESIGN_LOG, make check; report to the owner and wait | open |

## Piece B findings (2026-11-14, after the owner's "keep going without waiting for my approval")

- ngspice keeps every node of a transient in memory: TB4 on the RC netlist (about 9400 nodes, 18000 time points) asked
  for 548 MB and was refused. `make_benches.py` now writes one `.save` line per deck with the vectors its control section
  reads (no circuit change; pre and pex share the deck).
- Cost of one extracted (RC) run, tt, first grid point: tbl_op 3.8 s, tbl_ac 15.6 s, tbl_trip 158 s, tbl_pd 252 s
  (C-only 75 s), tbl_idle 92 s, tbl_en 108 s.
- **tPD rises a lot**: TB4 at tt, VIC 0.05 V, VID 100 mV: pre-layout 3.71 ns (the TBL deck with the pre-layout core
  reproduces TB4 exactly), C-only extraction 5.54 ns, RC extraction 6.45 ns (+2.74 ns, 64 % of the 4.29 ns margin to 8 ns).
  Two thirds capacitance, one third wire resistance. Being diagnosed stage by stage (`.scratch/t11/diag_tb4.py`).
- D-012 (sizing/FROZEN.md) asks for op, gain, delay and one eye run at ff/125C/3.6 V, VIC 0.05 V after extraction:
  tbl_op now covers the 7 VIC x VID +-100 mV at tt and that corner; new bench tbl_eye (TB5 deck) at that corner.

## Criterion reading for gate TBL (fixed here before the full runs)

Per pair (same deck, corner, grid point): margin = distance of the value to the source TB gate's limit (the nearer side
of a two-sided limit, as flow/gates.py). used = (margin_pre - margin_pex) / margin_pre. PASS when used <= 0.30.
Checks with no margin by construction (ber_errors, toggle_diff, osc_flag, model_warnings) pass when the extracted value
meets the limit. A GAIN of margin over 30 % is listed and explained, not failed. Spread checks use the same rule on the
spread. The systematic offset added by the layout (TB3_trip off_v delta) is compared with 30 % of the TB3_off window
margin. D-012 is judged on the absolute limits (A1 >= 4, TB4 limits, TB5 eye limits) at ff/125C/3.6 V, VIC 0.05 V.
Evaluator: `sim/tbl/evaluate.py` -> `results/post_layout/tbl.json`, `TBL.md`.

## Finding: the T10 RC netlists counted every coupling twice (Magic 8.3.636 extresist)

Diagnosis of the TB4 slow-down (`.scratch/t11/diag_tb4.py`, `node_cap_ac.py`, `lane_res.py`, `c_vs_rc.py`, `rc_test*.py`):
- Stage by stage (tt, VIC 0.05 V, VID 100 mV, rise/fall): pre 3.46/3.71 ns, C-only 5.12/5.51, RC 5.91/6.42; the
  hysteresis stage takes the largest part (+0.7-0.8 ns C-only), then stage 3, stage 1, the output chain.
- The extracted resistances are small (largest element 83 ohm, largest per-net sum 1.8 kohm over 80 elements): they
  cannot explain the 0.9 ns between C-only and RC.  The RC netlist carries 4304 fF of wiring C against 2843 fF in the
  C-only one: for every net that extresist splits, the capacitance to VSS equals that net's whole C-coupled total
  (oa 27.56 fF, d2a 24.04, d3 14.41: exactly the C-only totals) while all coupling capacitors are written as well; the
  n-well node of the PMOS pair (tp) lost its 103 fF well capacitance and all its couplings.
- `ext2sim -p` before extresist (the sak-pex.sh full-RC flow) gives the identical netlist; a decoupled RC extraction
  (`extract no coupling`) drops the capacitance of every split net.  The Magic tech file gives diffusion no area cap
  (no double count of junctions); the n-well has 120 aF/um2 (the tp well capacitance is real).
- Fix: `check.rc_repair()` keeps the RC netlist's devices and resistor networks and takes the capacitance from the
  C-coupled extraction of the same layout (ground capacitors of each net and coupling capacitors of each net pair
  scaled to the C extraction's totals, lost pairs added between representative nodes).  On the lane: every one of the
  145 net-pair totals equals the C extraction (largest relative error 3e-6), 3125 resistors kept.
  `run_macro.py --stage pex` redoes step 6 with the repair on the delivered GDS (same sha256).
- The TBL run started on the double-counted netlist was stopped (op, ac, trip-pre had finished); it is re-run.
- What stays true: with the correct capacitance the slow-down is the C-only one, +49 % at that point (3.71 -> 5.54 ns,
  43 % of the margin to 8 ns); node capacitance on the chain is +35 to +120 % (effective, AC at 1 GHz).  The pre-layout
  netlist carries no wiring estimate at all (sizing assumed cw = 10 fF on oa/ob in its pole estimate only; extracted
  wiring is 27.6 fF there) and models junctions with 0.18 um of diffusion per side (layout: about 0.27 um average).

## Iteration 1 (the frozen sizing misses tPD after layout): plan and first results

Evidence (iteration 0, correct capacitance): TB4 tt, VIC 0.05 V, VID 100 mV: pre 3.71 ns, extracted 5.55 ns. Scaled to the
slow corner, ss/125C/3.0 V at VID 350 mV lands near 6.5-6.8 ns against the 5 ns limit (pre-layout margin there was only
0.435 ns, 9.5 %): no layout can keep a +3 % change, which is what the 30 % rule allows there. The full iteration-0 TBL run
(corrected netlists) is the record; it runs in parallel with 3 slots.

Method: (1) put the layout's loads into the simulation netlist, (2) re-size for speed against them, (3) regression,
re-layout, PEX, TBL.  No limit changes; this is a sizing iteration (like D-013), logged with flow/iterate.py.
- Estimate (`sim/tbl/make_estimate.py` -> `sizing/parasitic_estimate.json`, consumed by the sizing script and
  `lvds_circuit.ESTIMATE`, simulation netlist only, never in the LVS reference): junction diffusion length ldiff = 0.511 um
  (extracted area / formula area = 2.84 over lane 0's signal nets, dummies included) and one wiring capacitor per net
  (extracted totals, lane nets the mean of the three lanes; 31 nets).  Validation on the T10 layout, TB4 tt/0.05/0.1:
  pre 3.71, pre + estimate 5.37, extracted 5.55 ns (the estimate carries 90 % of the added delay).
- Candidates (sizing `--set`, `.scratch/t11/iter_explore*.py`, TB4 VIC 0.05 V with the estimate, tPD ns tt-0.1 / tt-0.35 /
  ss-0.1 / ss-0.35): base 5.37/4.63/7.93/6.51; n_t2=10 4.39/3.76/6.39/5.26; + gmid_s2=8 + L_ld=0.28 (C) 3.68/3.19/5.35/4.50
  (I_lane 757 uA at tt, 0 asserts failed); L_ld=0.28 alone 4.74/4.08/7.00/5.78; r3=3 on top of C: no gain (+139 uA).
- Stage split of C at ss/0.35 (rise): stage 1 1.66, stage 2 +1.47, stage 3 +0.64, chain +0.60 ns (base: 1.67 / +2.66 /
  +1.30 / +0.65): the stage-2 change works; stage 1 (fold and output nodes with the pair + dump junctions and wiring) is
  now the largest part.
- Device changes of C: mt2 nf 6 -> 12, ms nf 3 -> 2 (W 11.58 -> 8.74 um), mld/mlc/mp3 L 0.40 -> 0.28 um (same fingers),
  mn3 nf 1 -> 2, Rs 4573 -> 1690 ohm (8.86 -> 3.17 um); alpha fingers unchanged 4/5.

Order after the iteration-0 run has finished and is committed (the frozen sizes / netlist must not change under it):
choose the candidate (TB4, TB3 V_H, TB2 at worst5 x 3 VIC), calibrate the wiring part of the estimate on one extracted
point, write the estimate, sizing defaults, netlists; decisions note D-016, iterations log, freeze note; make full
(detached); re-layout (lane, bias, macro: make layout); PEX; TBL; AUDIT_2; then T12, T13.
- Round 2 (worst5 x 3 VIC, estimate core; limits of gates.yaml: V_H 6-35 mV since D-009): base FAILS TB2 with the estimate
  (stage f3dB 0.46 x DR, chain 35 MHz: what tbl_ac_pex showed); C: tPD 4.50 / 5.35 ns (VID 0.35 / 0.1), V_H 8.3-14.3 mV,
  A1 min 5.15, stage f3dB 1.05 x DR, chain 66 MHz; J (C + i_ref 60 uA): 4.11 / 4.90 ns, but 19 of 35 devices change (both
  input quads, mirrors, bias block; odd finger counts) and I_lane 935 uA; H (C + PMOS pair gm/ID 13): A1 assert fails;
  C + gmid_m5 10: fold-pole asserts fail; C + vr_tt 1.10: 4.42 ns for 0.3 less A1 margin.
- DECISION: candidate C (n_t2 5 -> 10, gmid_s2 12 -> 8, L_ld 0.40 -> 0.28; everything else frozen): it fixes TB4 and TB2
  with the layout's loads, changes 5 small devices and Rs, keeps the stage-1 quads and the bias block, and keeps the slow
  corner margin of the original design (0.5 ns, 10 %).  The wiring part of the estimate is calibrated on the 36 TB4 points
  of the iteration-0 extraction (`.scratch/t11/calib.py`) so that the estimate is not below the extraction.
- tools/run_full.sh now runs the make-full sequence with --jobs 4 (make full had no --jobs: run_all defaults to 6) and
  always writes mutants + report; flow/mutants.py mini bench 6 -> 4 jobs.

## Iteration 0 record (the T10 layout, corrected RC netlists): gate TBL FAIL

`results/post_layout/iter0/` (tbl.json, TBL.md, run_log.txt): 172 pairs, every run ok, counts exact, 7 checks failed,
D-012 condition MET (ff/125C/3.6 V, VIC 0.05 V: A1 4.78, tPD 3.53 / 4.75 ns, eye ok, nodes within 6.7 mV) -> ladder R6 is not
triggered by the freeze condition.  Failed (extracted against pre-layout):
- TB2 stage f3dB 0.837 -> 0.435 x DR and chain f3dB 56.4 -> 37.4 MHz at ss/125C/3.0 V (limits 0.8 x DR, 50 MHz): absolute fail.
- TB4 tPD VID 0.35: 4.565 -> 6.755 ns at ss/125C/3.0 V (limit 5 ns); VID 0.1: 5.553 -> 8.221 ns (limit 8 ns); DCD at VID 0.1
  over 30 % at 3 points.  Absolute fails at the slow corner; +46-49 % delay everywhere.
- TB8 vout_off_v (EN = 0, supply ramp): 0.21 -> 0.28 V at tt / ss (limit 0.33 V): within the limit, 50-57 % of the margin
  (supply coupling: the extraction has 4-5 fF from OUT and i2 to VDD).
- TB8 min_pulse_s (ramps, EN follows the supply): the shortest power-up pulse falls from 0.1-15 us to 13-280 ns (limit
  2 ns); 6 runt excursions appear at tt case 4 (13 ns wide).  Within the limit, over 30 % of the margin.
Passed: TB1 subset, TB2 gain, TB3 V_H (DC), systematic offset (0.000 mV added), TB5 eye at the D-012 corner, TB7, TB10,
TB12 (worst eye 0.929 -> 0.887 UI).  Extracted run cost: TB10 one run 5.3 h (76 x pre-layout), TB12 ~15 min, TB4 ~4 min.
(Correction, 2026-11-21: the 5.3 h was the other benches' time.  run_tbl.py logged the parallel TB10 run's wall when it
joined it after them; it now also logs the run's own simulation time.  The iteration-1 extracted TB10 took 9046 s.)

## Iteration 1: first post-layout number (2026-11-15)

TB10 (three lanes) on the iteration-1 extraction, tt: lane delays 3714 / 3720 / 3719 ps (iteration 0 extracted:
5358 / 5355 / 5360 ps; iteration-0 pre-layout 3659 / 3641 / 3652 ps), skew 6 ps, crosstalk jitter 0.0010 UI (limit 0.05),
no missed edges; 9046 s on one job.  The re-sized design on its extracted layout is as fast as the first sizing was
before layout.  Its pre-layout partner (tbl_lanes_pre with the estimate core) runs with the TBL suite.
Owner, 2026-11-15: finish the running batch (this run + the iteration-1 full regression), commit, then pause; the hourly
auto-resume job was deleted.  Next steps after the pause: `CARRY_ON_GUIDE.md` sections 5-6.

## Iteration 1 pre-layout regression (2026-11-20/21)

The container was killed on 2026-11-15 mid-run (exit 137, host restart); `tools/run_full.sh 4` was relaunched on 2026-11-20
(the harness cache kept TB3_off / TB3_hmc from the interrupted run; the log is unbuffered now).  Result (commit 5a78f0d):
17 PASS, 2 FAIL, TB11 not applicable; mutants 11 of 11 detected.

* **TB3_hmc FAIL (design):** 17 of 600 Monte Carlo runs below the 6 mV floor, all at ff/-40C/3.6 V (mean 8.3-8.6 mV, sd
  1.4-1.6 mV, min 4.0 mV); ss/125C/3.0 V mean 13.4-14.4 mV, max 20.5 mV.  After iteration 0 (D-009) the same corner had
  mean 10.7-11.0 mV with sd 12 % of the mean; iteration 1 lowered the mean (L_ld 0.40 -> 0.28 changed the load behaviour the
  trip model does not capture: simulation 0.74 x the model at tt) and raised the spread to 15-22 % (the load VT mismatch grows
  1.4x at L 0.28).  R3 is exhausted (rung 1 = 6-35 mV), so the design must change.
* **TB3_trip FAIL (solver):** 4 of 270 runs (sf, 27/125 C, VIC 2.35 V, sweep 1) stall in the first operating point of the
  DC sweep, where VDD is 0.3 V: gmin and source stepping fail, the transient op hangs to the 300 s timeout.  Fix: the
  TB3_off retry variants (itl/gmin) added to tb3_trip.json and tb3_hmc.json; the circuit and stimulus are untouched.

## Iteration 2: stage-2 hysteresis (2026-11-21, exploration)

Why alpha: with source degeneration the trip voltage is dI x Rs + dVGS, dI = I_T2 (alpha-1)/(alpha+1), so the relative
V_H error per relative alpha error is 2 alpha/(alpha^2-1): 4.4 at alpha 1.25, 2.4 at 1.5, 1.9 at 1.67.  The alpha error is
the diode / cross-coupled load VT mismatch, so a larger alpha cuts the Monte Carlo spread.  The cost: less Rs, so the
corner spread of V_H grows (dVGS dominates), and V_H,in is largest where A1 is lowest (ff/125C/3.6 V, VIC 0.05 V).
Tool: `.scratch/t11/iter2/explore_vh.py` (candidate sizing -> trip at worst5 + sf/-40/3.0 + ff/125/3.6 + fs/-40/3.3, the
hysteresis Monte Carlo with the regression's first 40 seeds per group, delay and AC with the estimate core).
New sizing knob `vh_scale` (multiplies the V_H target of the Rs solve) and a new assert: every ppolyf_u_1k >= 1.0 um long
(Magic lmin; the solve had produced 0.26 um and a negative length without complaint).

| candidate | Rs length | trip V_H (8 corners) | MC low: min of mean-3sd | MC high: max of mean+3sd | tPD ss/125 VID 0.35 |
|---|---|---|---|---|---|
| base (4,5) alpha 1.25 | 3.169 um | 7.9-16.7 mV | 2.95 mV (6 of 240 < 6 mV) | 20.5 (ss/125) | 4.50 ns (iteration 1) |
| (4,6) alpha 1.5 | 0.262 um (not drawable) | 8.7-23.9 | 6.34 | 22.4 (ss/125; ff/125 not run) | - |
| (5,7) alpha 1.4 | 1.014 um | 8.7-22.3 | 5.61 | 21.9 (ss/125) | - |
| (3,5) alpha 1.67 | negative (invalid) | 9.5-28.3 | 7.88 | 25.4 | - |
| (4,6) vh_scale 1.3 | 1.328 um | 11.9-29.9 | 8.57 | 37.4 (ff/125 VIC 0.05; 1 of 480 > 35 mV) | 4.665 ns |
| (4,6) vh_scale 1.25 | 1.157 um | 11.3-29.1 | 8.25 | 36.2 (ff/125 VIC 0.05) | - |

Monte Carlo relative sd: base 15-22 % at ff/-40C, alpha 1.5 7-11 %, alpha 1.4 9-13 %.  Alpha 1.5 with a drawable Rs sits
too high (the balance point needs vh_scale about 1.05, a 0.45 um resistor); next round: alpha 1.4 with vh_scale 1.10-1.20.

Rounds 3-4 (alpha 1.4, Rs raised a little; then narrower load fingers to win back the delay):

| candidate | Rs length | trip V_H (8 corners) | MC low: min of mean-3sd | MC high: max of mean+3sd | tPD ss/125 VID 0.35 / 0.1 |
|---|---|---|---|---|---|
| (5,7) vh_scale 1.10 | 1.436 um | 9.7-24.3 mV | 6.24 mV | 31.40 mV | - |
| (5,7) vh_scale 1.15 | 1.641 um | 10.3-25.1 | 6.57 | 32.65 | 4.815 / 5.675 ns |
| (5,7) vh_scale 1.20 | 1.851 um | 10.7-26.1 | 6.89 | 33.89 | - |
| (5,7) 1.15, wf_ld 1.8 | 1.641 um | 10.3-24.9 | 6.55 | 32.23 | 4.739 / 5.578 |
| **(5,7) 1.15, wf_ld 1.6** | 1.641 um | 10.1-24.5 | 6.51 | 31.68 | **4.659 / 5.482** |

Chosen: alpha 1.4 (5, 7), vh_scale 1.15, wf_ld 1.6 (D-017, FROZEN.md iteration-2 table; 128 sizing asserts pass; AC: A1
min 4.78, stage f3dB 1.00 x DR, chain 60.7 MHz).  Margins at +-3 sd: 8.5 % above the 6 mV floor (ff/-40C/3.6 V, VIC
2.35 V), 10.5 % below the 35 mV ceiling (ff/125C/3.6 V, VIC 0.05 V, not one of the gate's two Monte Carlo corners).
tPD margin 6.8 % at the slowest corner with the estimate (iteration 1: 10 %).  The load-finger width did not change
the spread: less area raises sigma(VT) but the denser loads have a lower gm/ID.  Next: make layout, the post-layout suite
(TBL first: the timing margin is the risk), then the full pre-layout regression.

**Correction (D-018): (5,7) cannot be built.**  `make layout` failed twice: load fingers below 1.81 um leave no room for the
three contact bars of the interdigitated load row (1.6 um: 1.47 um available, 1.68 um needed), and `mirror_interdig` takes
at most two devices with an odd finger count (a single finger sits at a row end; (5,7) has four).  Layout-feasible: alpha
1.5 = (4,6) (both even).  Its Rs must be small (about 0.3-0.4 kohm) to centre V_H, which at 2 um width is shorter than
the 1 um gencell minimum; Rs is not part of the gain ratio (RL/Rb/Rf/divider), so it gets its own width (new knob rw_rs).
The model's terminal resistors are 85.45 ohm/sq x 1 um / W each, so the end resistance scales 1/W: sizing.res_len and
passives.seg_len now use 85 x 2/W ohm (unchanged at 2 um: the default sizing came out byte-identical).
Also fixed: check.magic_drc compared Magic's total (144) with the per-rule CO.6 count (160) and failed t_block on a
negative difference; it now counts the boxes of the rules that are not on the allow-list.

Round 5 (alpha 1.5 (4,6), wf_ld 1.85, Rs 5 um wide):

| vh_scale | Rs | trip V_H | MC +-3 sd (4 corners) | tPD ss/125 VID 0.35 / 0.1 |
|---|---|---|---|---|
| 1.03 | 270 ohm, 1.167 um | 8.7-24.3 mV | 6.31-30.32 mV | - |
| 1.06 | 329 ohm, 1.456 um | 9.1-24.9 | 6.54-31.15 | 4.533 / 5.243 ns |
| 1.10 | 402 ohm, 1.817 um | 9.5-25.7 | 6.87-32.07 | - |
| **1.08 (final)** | about 365 ohm, 1.637 um | 9.3-25.3 | **6.68-31.59** (observed 7.3-30.4, 0 of 480 outside) | **4.541 / 5.257** |

Final AC: A1 min 4.78, stage f3dB 0.99 x DR, chain 60.7 MHz; 128 sizing asserts pass.  `make layout`: all leaf tests,
lane, bias block and macro PASS; frame 650 x 194.2 um (+2.1 um: core 600 x 144.2 um, spec limit 600 x 150); extracted
wiring 2842.6 fF (2836.2 before); gate LAYOUT PASS.  TBL cores regenerated (lane-0 MLC fingers 12).  Next: the post-layout
suite (TBL) first, then the full pre-layout regression.

## Iteration 2: post-layout suite, gate TBL (2026-11-21)

`results/post_layout/` (TBL.md, tbl.json), `results/gates_postlayout.json`: **gate TBL FAIL**, 172 pairs, every run ok,
counts exact, 2 checks failed (iteration 0: 7), largest margin use 0.82 (iteration 0: 11.0), D-012 condition MET
(ff/125C/3.6 V, VIC 0.05 V: A1 4.779, tPD 2.48 / 3.10 ns, edge 0.12 ns, eye 0.996 UI, no bit errors).  Every timing,
gain, eye, hysteresis, idle and package check is within 30 % of its margin (tPD ss/125C/3.0 V, VID 0.35 V: 8.3 %; chain
f3dB at ss/125C gains 6 %); systematic offset added by the layout 0.000 mV.  Extracted three-lane TB10: lane delays
3.498 / 3.498 / 3.507 ns at tt (iteration 1: 3.71 ns), no missed edges, crosstalk 0.0008 UI, 10686 s on one job.
Suite wall time 5.1 h (other benches on 3 workers); `run_tbl.py` is still the old copy in that run (joined after 18305 s).

The two failed checks are both TB8 (EN and supply ramps), both power-up transients, both within their absolute limits at
the TBL corners:
- vout_off_v, cases 0-1 (EN = 0): 0.23 -> 0.28 V at ss/125C and tt (limit 0.33 V), 39-46 % of the margin; ff/125C 12-15 %.
  The maximum is reached 13-23 ns into the bench's 50 ns setup ramp at VDD 0.53-0.93 V, before any device can hold the
  outputs: capacitive coupling to VDD.  From 100 ns on the outputs are 0.000 V in both netlists.  The same setup ramp
  is the reason D-011 starts min_pulse_s at 100 ns for cases 0-2; vout_off_v still takes the whole run.
- min_pulse_s, case 3 (1 us supply ramp, a spec ramp): ss/125C 148 -> 28 ns, ff/125C 16 -> 8 ns (limit 2 ns), 82 % and
  57 % of the margin.  The pulses are the copy-b outputs going HIGH for 22-49 ns at VDD 0.75-1.06 V while the chain wakes
  up.  The metric is chaotic: other points gain as much (tt case 3 40 -> 49 ns, ss/125C case 4 0.54 -> 8.4 us).
Risk the 30 % rule points at: the iteration-1 pre-layout TB8 (45 corners) has vout_off_v up to 0.296 V at ss/-40C, a
temperature TBL does not run (+40-45 mV would be about 0.34 V, still inside the setup ramp), and min_pulse_s down to
3.0 ns at ss/125C case 3.  No ladder rung covers TB8 or TBL.

Next (evidence before any decision; `.scratch/t11/iter2/chain2.py` replaced the first scheduler and adopted its running
pre-runs, max 4 simulations): TB8 pre-layout on the iteration-2 sizing (45 corners), then the extracted macro at the
least-margin corners, `sim/tbl_en/tbl_en_pexw_off.json` (ss/-40C x 3 supplies, cases 0-1) and
`sim/tbl_en/tbl_en_pexw_pulse.json` (every process at 125 C x 3 supplies, cases 3 and 5), then TB4 / TB4b / TB5 and the
full regression.  If every absolute TB8 limit holds on the extraction, gate TBL's two checks go to a waiver entry with
that evidence for AUDIT_2 to rule on (the owner can overrule); if not, a design or test-definition question for the owner.

Iteration-2 pre-runs (simulations only, `run_all.py --stage sim`; gates evaluated into a scratch table): **TB3_hmc PASS**
600 / 600 runs, V_H 7.30-24.20 mV (window 6-35 mV), mean +- 3 sd 6.96-24.70 mV; ff/-40C/3.6 V mean 9.8-10.1 mV, sd
0.78-0.94 mV (iteration 1: mean 8.3-8.6, sd 1.4-1.6, min 4.0 mV, 17 runs below 6 mV).  **TB3_trip PASS** 270 / 270, V_H
9.10-25.30 mV, no run needed a retry variant.

## Iteration 2: TB8 power-up checks (2026-11-21)

**TB8 pre-layout FAIL** (270 / 270 runs ok, `sim/tb8_en/results/tb8_en`): min_pulse_s 0.084 ns (limit 2 ns) at tt/125C/3.6 V,
case 3 (1 us ramp, EN tied high).  Copy b (expected LOW) makes a runt from 9 % to 51 % of the supply (0.505 V at VDD
0.99 V, 273-277 ns) and back; the 84 ps is the part above 50 %.  `lib_tb.pulses_norm` documents completed swings but takes
every pair of consecutive 50 % crossings, so a runt grazing 50 % counts as a pulse; the runt's own width is 3 ns.  The
other TB8 checks pass (vout_off_v 0.296 V, idd_en0, valid_time).  The wake-up runts arrived with iteration 1's stage-2
re-size: case-3 runs with a runt 2 / 45 at iteration 0 (000897c), 34 at iteration 1 (5a78f0d), 35 now; outputs leave the
LOW rail at 0.69 V at iteration 0, 0.94 V since.

**Extracted evidence** (`sim/tbl_en/results/tbl_en_pexw_off`, `_pexw_pulse`): the pulse limit holds everywhere (worst
4 ns, ff/125C/3.0 V, a runt); **vout_off_v exceeds 0.33 V** at ss/-40C (0.346-0.363 V), 15-28 ns into the 50 ns setup ramp
of cases 0-1 at VDD 1.07-1.12 V, for 2-3 ns; 0.000 V once the supply settles.  With EN = 0 every output is <= 10 % of the
instantaneous supply from VDD = 1.15 V on (case 0), 1.10 V (case 1), 0.85 V (20 us ramp, case 5), pre-layout and
extracted alike (`.scratch/t11/iter2/tb8_low_from.py`).  The extracted 28 ns at ss/125C/3.0 V case 3 (TBL's 82 % pair) is a
full-swing wrong-level pulse on copy b while the chain wakes (all six outputs rise at VDD 1.05 V, copy b falls at
1.13 V); the wake-up width does not pair corner by corner (125 C: extracted longer in 13 of 30 pairs, shorter in 15).

Not covered by the bench: the EN = 0 off-state on the spec ramps (1 us, 100 us; spec.yaml en.supply_ramps_s); only case
5 (20 us ramp, EN low until 2.0 V; early_high_v pre-layout worst 0.228 V, reported) comes near it.  Scratch bench
`.scratch/tb8x/` (frozen deck and hooks plus cases 6 / 7 = 1 us / 100 us ramp with EN = 0) runs pre-layout at 45 corners
and extracted at the six worst; `sim/tbl_en/tbl_en_pexw_cold.json` (-40 C, cases 3 / 5) and `tbl_en_pexw_rest.json` (the
23 corners left) give the extracted macro every corner on the spec-rate ramps.  Queue: `.scratch/t11/iter2/queue.json`,
scheduler chain5.py.

Offline re-measurement of the kept waveforms (`.scratch/t11/iter2/tb8_option_a.py`): vout_off_v from 100 ns (D-011's
window) gives 0.000 V pre-layout and extracted; completed-swing pulse widths give pre-layout worst 3.0 ns (the runt), the
extracted runs unchanged.  A limit failed on the extraction, so the test-definition change (draft D-019,
`.scratch/t11/iter2/D-019_draft.md`: the two measurement changes, the EN = 0 spec-ramp checks added, TBL's pulse check
worst against worst) or a design change is the owner's decision; nothing is changed until then.

Evidence, continued (2026-11-21 15:50-18:26; scheduler `.scratch/t11/iter2/chain5.py`, queue file, max 4 simulations):
`tbl_en_pexw_cold` (-40 C) and `tbl_en_pexw_rest` (the 23 corners left) give the extracted macro all 45 corners on
cases 3 / 5.  Pulse widths (completed-swing rule, offline): worst 4.0 ns extracted (ff/125C/3.0 V) against 3.0 ns
pre-layout; per pair longer in 62 of 90, shorter in 25 (chaotic, `.scratch/t11/iter2/tb8_45pairs.py`).  EN = 0 off-state
on the 20 us ramp (case 5 early_high_v): higher extracted at **all 45 corners**, worst 0.228 -> 0.275 V (46 % of the
margin, ss/-40C): systematic.  Scratch bench `.scratch/tb8x/` (cases 6 / 7 = EN = 0 on the 1 us / 100 us spec ramps;
`.option reltol=0.01` as the frozen bench gives cases 1 / 3 / 4, after 21 of the first 24 case-7 runs stalled to the
reltol-0.05 retry): pre-layout 85 / 90 ok (5 case-7 runs stall in every variant), worst 0.262 V (1 us) / 0.213 V
(100 us); extracted at the six worst corners 0.316 V / 0.254 V (ss/-40C): the layout uses 80 % / 35 % of the margin
there and leaves 14 mV on the 1 us ramp; at TBL's own corners at most 24 %.  The EN = 0 off-state peak sits at VDD
0.8-1.15 V at a third of the supply: the output is held LOW through a NAND and three inverters (`lvds_out`), none of
which conducts fully below about 1 V.  Draft D-019 updated; the owner is asked (briefing page version 2).

Owner's decision (2026-11-21, about 19:50): the owner rules out on-chip resistors (area) and asked whether an external
pull-up / pull-down could do the job.  Answer: no.  RX0_O-RX2_O and EN are core-side pins (`spec/pins.yaml`) that never
reach a package pin; only the RX pairs do, and they already carry the off-chip 100 ohm termination (`spec.yaml`
input.termination).  A resistor on the input side does not act on the output stage (the failing cases already hold the
inputs at +-350 mV).  The owner then chose **option 1, waiver D-019** (`.scratch/t11/iter2/D-019_draft.md`), to be applied
after the iteration-2 full regression (`tools/run_full.sh 4`, started 19:13 by chain5): TB8 post-processing is not part of
the harness cache key, so editing `sim/tb8_en/hooks.py` or `sim/lib_tb.py` mid-run would mix definitions.
`lib_tb.pulses_norm` is used only by TB8 (`sim/tb8_en/hooks.py`; the TBL power-up bench reuses those hooks), so the
completed-swing fix touches no other bench.  Also done: `tb8x_pex_rt` (the six extracted corners with reltol 0.01) equals
`tb8x_pex` within 0.1 mV at all 12 points; TB4b PASS (70 / 70, worst tPD 4.597 ns at ss/125C/3.0 V, VID 0.2 V); TB5 PASS
(180 / 180, eye >= 0.926 UI, no bit errors).  Briefing page version 3 adds a plain-language guide (guide.html) and
expected / actual for every check.  Note on the "1.15 V" level: `tb8_low_from.py` reports the supply at the last sample
above 10 %; interpolated, the outputs come down at about 1.18 V on the worst run (ss/-40C/3.3 V, case 0), so the brief
now says "about 1.2 V".

Owner follow-up (2026-11-21, evening): route each RXn_O to a spare pad so an off-chip pull-down can reach it?  Answer: it
would hold the node down, but the output stage is sized for 30 fF (`spec.yaml` output.load_f) and a pad plus package adds
about 1.8 pF (pad 1.0-1.15 pF, package 0.7 pF, `spec.yaml` input_network), about 60x; extracted tPD is already 4.57 ns of
5 ns at ss/125C/3.0 V.  A pad driver in between would isolate the node the core reads; a 60x last inverter adds the very
VDD coupling that causes the bump; three more pins; board noise / ESD path into the core; 33 uA per output at 100 kohm.
The protection belongs on the digital side (consumer logic held in reset until the supply is up; EN = 0 until 2 V, D-008).
D-019 stays the plan.  Brief guide section "Follow-up: why not wire each output out to a pin?".

**PAUSED 2026-11-21 20:35 at the owner's request (machine needed).**  Stopped the scheduler chain5 (background task), then
`tools/run_full.sh 4` and its `flow/run_all.py --tier full --phases env,prelayout --jobs 4` (process group 250739) and the
three live ngspice runs (each in its own session, killed separately), during the TB3 offset Monte Carlo after SELFTEST,
TB1, TB2 and TB3_trip had passed.  The hourly auto-resume cron was deleted.  Completed runs stay in the harness cache, so a
restart continues from there.  To resume: start the iteration-2 full regression again (`python3 .scratch/t11/iter2/chain5.py`
in the background; `queue.json` now holds only the full run, max 4 simulations), then apply D-019 (task list: re-run TB8 and
the TBL power-up benches), AUDIT_2, T11 report, T12 package, T13.

**Resumed 2026-11-22 00:30 (owner: "resume the LVDS work"); D-019 applied BEFORE restarting the full regression** (it had to
restart anyway; this way it carries the new TB8 in one pass and no run mixes old and new definitions).  Code:
`sim/lib_tb.py` pulses_norm (completed swings, timed at their last 50 % crossing); `sim/tb8_en/hooks.py` (cases 6 / 7 =
EN = 0 on the 1 us / 100 us ramps, reltol 0.01; vout_off_v from 100 ns in cases 0-1, vout_off_all_v, vdd_at_peak_v,
vdd_low_from_v; final_ok for the EN = 0 cases); `tb8_en.json` grid 0-7; `spec/gates.yaml` TB8 (vout_off_v cases 0, 1, 6, 7;
early_high_v case 5; reports); `sim/tbl/make_benches.py` tbl_en grid 0-7 (regenerated: only tbl_en_pre / _pex.json changed);
`sim/tbl/evaluate.py` (TB8 min_pulse_s of cases 3 / 5 worst against worst over 45 corners, incomplete coverage fails);
`spec/decisions.yaml` D-019 (files_after gates.yaml ac4c7945...).  `flow/lint.py`: 0 findings (frozen ok).
Checks: the new post-processing on the 270 stored TB8 waveforms reproduces the offline analysis (0.084 ns -> 3.0 ns, the
runt; five case-5 runs 13.7-18.9 -> 17.9-20 ns; none shorter; cases 0-1 at most 3.7 uV from 100 ns).  rshunt of cases 6 / 7:
1e13 (case 0's value) against 1e11 moves the peak at ss/-40C/3.6 V by 0.0 / 0.5 mV before layout and 0.1 / 2.2 mV extracted
(`.scratch/tb8z`), so 1e11 stays.  TB8 (5001 s at 2 jobs): 356 / 360 ok; four case-7 runs time out in all three variants
(ss/125C/3.6 V, fs/125C/3.6 V, sf/-40C/3.0 V, sf/27C/3.6 V; the scratch run had five, a slightly different set: chaotic);
case 6 worst 0.262 V (45 / 45), case 7 worst 0.213 V (41 runs), shortest pulse 3.0 ns.  tbl_en_pre / _pex 24 / 24 ok each;
at TBL's corners the layout uses 23.6 % (case 6, tt/27C/3.3 V), 9.5 % (case 7), 12.2 % (case 5 early_high_v), 0 % (cases
0-1 from 100 ns).  The case-7 stalls (`.scratch/tb8s`, the four corners, first attempt cut at 5 s so the candidate runs at
once): gear, tmax / 2, trtol 10 and rshunt 1e13 all time out at 300 s; with the settled tail cut from 10 us to 0.2 us all four
finish in 15-17 s (peaks 0.017-0.174 V).  The stall sits in the settled tail, as in cases 1 / 3 / 4, so case 7 is now the
100 us ramp plus 0.2 us (the gated peak falls mid-ramp at VDD about 0.8 V; final_ok reads the last 100 ns).  TB8 and
tbl_en re-run with it.

**D-019 result (2026-11-22 03:00):** TB8 360 / 360 ok, **gate TB8 PASS** (flow/gates.evaluate_gate): vout_off_v cases 0, 1, 6, 7
worst 0.262 V (case 6, ss/-40C/3.6 V; cases 0-1 from 100 ns at most 3.7 uV; case 7 0.213 V), early_high_v 0.228 V, shortest
pulse 3.0 ns (tt/125C/3.6 V case 3, the runt), idd_en0 133 nA, valid time 28.8 ns; reported vout_off_all_v 0.296 V and
vdd_low_from_v up to 1.154 V.  Extracted evidence sets re-measured (94 runs ok; cases 3 / 5 cover 90 of 90 corner-case pairs,
shortest extracted pulse 4.0 ns at ff/125C/3.0 V).  tbl_en 24 / 24 + 24 / 24 ok.  **Gate TBL PASS**: 178 pairs, 0 failed,
largest margin use 23.6 % (vout_off_v case 6 at tt/27C/3.3 V), early_high_v 12.2 %, min_pulse_s per pair (cases 0-2, 4, 6, 7)
19.6 %, worst against worst (cases 3 / 5) 3.0 -> 4.0 ns (a gain), D-012 met.

## Iteration-2 full pre-layout regression (2026-11-22 02:54-05:02, `tools/run_full.sh 4`, 7681 s)

18 PASS, 1 FAIL, TB11 not applicable (`results/gates.json`, `results/REPORT.md`); every gate at its expected run count;
`tools/audit_hashes.py` 17 benches, 0 not current; mutants 11 of 11 detected.  TB1 987, TB2 315, TB3_trip 270, TB3_off 15000,
TB3_hmc 600, TB4 630, TB4b 70, TB5 180, TB6 20, TB7 945, TB8 360 (with D-019), TB9 180, TB10 10, TB12 40: PASS.

**TB7_mc FAIL: osc_flag 1 in 1 of 1500 runs**, fs_27c_3v30__vic1.2__s1793293142 (the same Monte Carlo sample as one of
D-010's four).  Waveform (kept): lane 0 goes HIGH during the 50 ns power-up ramp (VDD/2 crossing at 32.9 ns), makes ONE clean
falling flip with its VDD/2 crossing at 149.236 ns, 0.76 ns before the idle window opens (150 ns), and holds LOW (6e-8 V at
600 ns); lanes 1-2 never move.  The window sees no crossing, only the end of that edge and its undershoot (0.079 V ->
-0.057 V within the first ns), 0.136 V peak-to-peak, which D-010's rule reads as "> 0.1 V without a crossing" = oscillation.
In D-010's analysis (iteration-0 sizing) this sample flipped at 217-275 ns, inside the window, and counted as the settling
flip it is; the iteration-2 sizing moved the flip 70-125 ns earlier, onto the window edge.  Not an oscillation: a window-edge
artefact of the measurement.  Offline (`.scratch/t11/iter2/tb7_window_guard.py`, all kept waveforms): counting a crossing
up to 5 ns before the window as inside it changes exactly this run (osc 1 -> 0, one settling flip at 149.2 ns, within the
500 ns limit of D-010) and no other of the 1500 TB7_mc and 945 TB7 runs.  That is a test-definition change: drafted as
D-020 for the owner (asked; not applied).
Harness cache quirk (AUDIT_1 finding F2, still open, seen in action today): `runner._dep_hashes` adds `{run_dir}/body.inc`
to the key only when that file exists, i.e. not on a run's first simulation, so a run simulated once gets a different key
the next time and is simulated once more (identical deck, identical result).  This is why the evidence sets tbl_en_pexw_* re-simulated today (new on
2026-11-21) while TB8 cases 0-5 and tbl_en (work dirs from earlier iterations) stayed cached; the 90 new TB8 runs will
re-simulate once on TB8's next run.  Changing the key formula would invalidate the existing cache instead, so it stays.
