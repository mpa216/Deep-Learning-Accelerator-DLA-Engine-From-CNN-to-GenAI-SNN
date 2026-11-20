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
| I2 | iteration 2 (D-017): stage-2 alpha / Rs for the hysteresis Monte Carlo; TB3_trip / TB3_hmc solver retries | exploring (2026-11-21) |
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
