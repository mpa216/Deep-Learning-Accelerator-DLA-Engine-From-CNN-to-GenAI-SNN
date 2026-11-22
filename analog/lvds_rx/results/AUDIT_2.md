# AUDIT_2: final audit after layout (task T11), 2026-11-21 to 2026-11-22

**Verdict: PASS with findings.** The delivered macro (iteration-2 sizing, GDS sha256 `892add3b...`) meets every frozen
criterion before and after layout and may be packaged (T12). Two waivers came after the results and are accepted here,
both chosen by the owner after the alternatives were laid out, neither changing a limit: D-019 (TB8 power-up off-state
and pulse rule) and D-020 (a 5 ns guard at the start of TB7's idle window). The open findings (F2, F8, F13) are low or
cosmetic and change no verdict.

## How this audit differs from the plan

PLAN_V2 5.2 item 6 asks for an agent other than the builder, in a clean work directory. As for AUDIT_1, the owner asked
for less machine time and no further agents, so the orchestrating session did this audit in place. Every step is a
script whose record is committed, so anyone can run it again:

| Plan step | What was done | Script and record |
|---|---|---|
| (a) rebuild from `sizing/` | Fresh copy of `sizing/`, `netlist/`, `flow/`, `spec/` in `.scratch/audit2/rebuild`; sizing, core netlist and LVS references regenerated there and compared with the committed and the frozen files | `tools/audit_rebuild.py`, `results/audit2_rebuild.json` |
| (b) results tied to the current inputs | Every stored run of the full tier checked against the current inputs, without simulating | `tools/audit_hashes.py` (run by `tools/run_full.sh`, and again after D-020), `results/audit_hashes.json` |
| (c) DRC / LVS / PEX from the GDS | From `results/layout/lvds_rx_x3.gds` alone: frame, KLayout main and antenna decks, flat Magic DRC, via arrays, LVS against the delivered schematic and against the frozen reference, fresh PEX against the delivered netlists | `tools/audit_layout.py`, `results/audit2_layout.json` |
| (d) mutation tests | The 11 mutants, run by the regression | `flow/mutants.py`, `results/mutants.json` |
| (e) hash chain | `results/manifest.json` against the files on disk, the rebuild and `sizing/FROZEN.md` | this report |
| (f) UNVERIFIED items of the handoff | All 18 walked: 1-14 closed with a file and line as evidence; 15-18 need chip integration and are listed in `package/KNOWN_LIMITS.json` | `tools/audit_unverified.py`, `results/audit2_unverified.json` |
| (g) look at the pictures | Layout pictures of the macro, a lane and the bias block; eye, offset and hysteresis plots of the regression | this report |

Independence: the auditor also directed the iterations and decisions it audits (D-016 to D-020). The scripts are the
independent part: (a) and (c) start from the committed sources and the GDS only, and (c) removes dummy devices by its own
electrical rule, not by the generator's names.

## What was checked and what came out

1. **Full-tier gates on the iteration-2 sizing: PASS** (`results/full_run.log`, `results/gates.json`).
   `tools/run_full.sh 4`, 2026-11-22 02:54-05:02 (7681 s) at commit `ac17072`: 18 PASS, TB11 not applicable (it needs
   ladder rung R6, not taken), 1 FAIL: TB7_mc osc_flag 1 in 1 of 1500 runs, a window-edge artefact of the measurement
   (F17), closed by D-020 (commit `260264a`; post hook only, every run from the cache: of the 2475 TB7, TB7_mc and
   tbl_idle runs exactly that run changed). Now 19 PASS, TB11 not applicable, every gate at its expected run count:
   SELFTEST 94, TB1 987, TB2 315, TB3_trip 270, TB3_off 15000, TB3_hmc 600, TB4 630, TB4b 70, TB5 180, TB6 20, TB7 945,
   TB7_mc 1500, TB8 360, TB9 180, TB10 10, TB12 40 (ENV, SIZE and TB0 have no runs).
2. **Rebuild: PASS.** `sizing/lvds_rx_sizing.py` (128 asserts, 0 failed), `netlist/gen_core.py` and
   `netlist/gen_lvs_ref.py` in a fresh copy: `sizes.spice`, `layout/device_table.json`, `lvds_rx_core.spice`, both
   LVS references, `results/sizing.json` and `sizing/sizing_report.md` came out byte-identical to the committed files,
   and the five frozen ones equal the iteration-2 table of `sizing/FROZEN.md`. (AUDIT_1 found two stale LVS
   references here, F1; none now.)
3. **Results tied to the current inputs: PASS.** `tools/audit_hashes.py --tier full`, run by the regression and again
   after D-020: 17 benches, every planned run stored and hash-matching, 0 stale, 0 missing, 0 not ok
   (`results/audit_hashes.json`, all_current true).
4. **Layout from the GDS alone: PASS, 7 of 7.**
   - Identity and frame: GDS sha256 `892add3b...`, the file both delivered PEX netlists were extracted from; one top
     cell, DBU 0.001; bounding box 650 x 194.2 um equals the recorded FIXED_BBOX; core 600 x 144.2 um within the spec's
     600 x 150 um.
   - KLayout foundry deck: 0 main-deck and 0 antenna violations.
   - Magic DRC on the flattened macro: 0 (the macro needs none of the CO.6 allow-list that the L = 0.28 um leaf tests use).
   - Via arrays (`scripts/check_via_arrays.py`, the copy the chip sign-off uses): 0 violations.
   - LVS against the delivered schematic (`layout/macro/results/lvds_rx_x3.spice`): unique match, no property or port
     errors.
   - LVS against the frozen reference (`netlist/lvds_rx_lvs_ref.spice`, sha256 as in `FROZEN.md`). The layout carries
     68 dummy devices that the reference leaves out (46 in the lane cell, 22 in the bias cell). The audit removes them
     with its own rule: a MOS whose gate and bulk sit on its own type's rail with one diffusion on that rail, or a
     resistor with every terminal on one rail. On the delivered schematic the rule finds exactly the 68 devices the
     generator named as dummies; on the reference it finds none; on the extraction it finds the same 68 per cell. The
     stripped extraction matches the reference uniquely, devices and nets equal.
   - PEX: a fresh C-only extraction equals the delivered one (93 nets, largest difference 0 fF); a fresh RC extraction
     with `check.rc_repair` equals the delivered one (1047 subcircuit, 5813 C, 10601 R, 12 diode elements, 3.45 Mohm
     total; repair 475 coupling pairs, largest relative error 4e-6; wiring capacitance 2842.6 fF after the repair,
     4285.7 fF before).
5. **Post-layout re-check (gate TBL) and the D-012 conditions: PASS** (with D-019, commit `ac17072`; re-evaluated
   unchanged after D-020, whose re-run changed none of the 30 tbl_idle runs; `results/post_layout/TBL.md`,
   `results/gates_postlayout.json`).  178 pairs, 0 failed checks, 0 runs not ok, 0 count errors; largest use of margin
   23.6 % (TB8 vout_off_v, case 6 = EN = 0 on the 1 us ramp, tt/27C/3.3 V: 0.191 -> 0.224 V); 10 gains of margin over
   30 % listed (TB2 chain bandwidth 3, TB7 idle min_pulse 5, TB8 min_pulse 2), explained below.  TB8's wake-up pulse
   (cases 3, 5) worst against worst over the 45 corners: 3.0 ns before layout, 4.0 ns extracted, coverage 90 / 90 on
   both sides.  D-012 at ff/125C/3.6 V, VIC 0.05 V on the extraction: operating point within 2.5 mV, A1 4.78 (limit 4),
   tPD 2.48 / 3.10 ns at VID 350 / 100 mV, DCD 0.00003 / 0.030 UI, edge 117 ps, eye 0.996 UI, no bit errors: met,
   consequence none.  Before D-019 the same suite failed two TB8 checks (46 % and 82 %, see F14, F15).
6. **Mutation tests: PASS, 11 of 11 detected** (`results/mutants.json`, run by the regression at `ac17072`; each
   control passed): meas_failed, run_removed, limit_exceeded, stale_sizes_hash, m_not_nf, bare_ngspice, frozen_edit,
   pin_mismatch, offset_area_div4 (TB3_off), polarity_swap (TB5), nf_to_m_core.  None targets TB7, so D-020 cannot
   change a detection.
7. **Hash chain: PASS.** `results/manifest.json` (written by the regression at `ac17072`, harness 1.3) against the
   files on disk: the sizing script, the LUTs, `spec.yaml`, `gates.yaml`, `pins.yaml`, `paths.yaml`, the five netlists
   and `sizes.spice` match; `spec/decisions.yaml` differs only by the D-020 entry appended after the run (a waiver
   without files_after: no frozen file changed, `flow/lint.py` frozen ok).  The generated netlists and `sizes.spice`
   equal the rebuild (item 2) and the iteration-2 table of `sizing/FROZEN.md`.  The T13 regression writes a new
   manifest.
8. **UNVERIFIED items (handoff section 16): 14 of 18 closed, 4 listed.** Items 1-14 (mismatch coefficients,
   sw_stat defaults, C-vs-D model identity, xschem flags, gencell syntax, pygmid keys, ngspice `.control` in batch
   mode, Monte Carlo seeding, wnflag, pad capacitance, resistor tolerance and TC, diode and MOS-cap names, deep N-well,
   sak scripts) each have a file and line as evidence in `results/audit2_unverified.json`. Items 15-18 (OpenSTA /
   OpenROAD clocks and input delays on macro output pins; whether RSZ_DONT_TOUCH_RX stops port buffering of the RX
   inputs; the analog template geometry and slot; the LVS key semantics) can only be closed in chip integration
   (PLAN_V2 P7/P8, owner-gated, section 9) and are listed in `package/KNOWN_LIMITS.json` under `integration_open`,
   confirmed in the rebuilt package (T12, 2026-11-22).
9. **Pictures.** Layout (`results/layout/lvds_rx_x3.png`, `layout/lane/results/lvds_lane.png`,
   `layout/bias/results/lvds_bias.png`, all rendered from the iteration-2 GDS): three identical lanes and the bias
   block at the east end inside the frame, continuous supply rails, no overlapping blocks.  Simulation plots of the
   regression: TB3_hmc V_H at ff/-40C/3.6 V, VIC 1.2 V (the corner of iteration 1's failures): mean 9.8 mV, sigma
   0.88 mV, the whole histogram inside 6-35 mV; TB3_off at ss/125C/3.0 V, VIC 0.05 V: N = 1000, mean 0.08 mV, sigma
   3.2 mV, +-6 sigma at about +-19 mV against the 95 mV window; TB5 eye at the slowest case (ss/125C/3.0 V, VID 100 mV,
   200 Mbit/s): horizontal opening 0.95 UI, jitter 238 ps peak-to-peak, DCD 1.6 %, full swing, no bit errors.

## Findings

| # | Finding | Severity | State |
|---|---|---|---|
| F2 | (AUDIT_1) Harness 1.3 run hash takes a prep-written include from the previous execution. | Low | Open, unchanged (harness 1.3). `tools/audit_hashes.py` stays the staleness test. Seen in action on 2026-11-22: the key of a run simulated only once lacks `{run_dir}/body.inc` (absent then), so its next run misses the cache and simulates once more (the 94 extracted evidence runs of 2026-11-21, about 2 h; identical decks, identical results). Changing the key now would invalidate the whole cache instead. |
| F4 | (AUDIT_1) `flow/run_all.py --stage gates` prints PASS for results simulated from older inputs. | Medium | Fixed where the guide runs the regression: `tools/run_full.sh` runs the hash audit after the full tier and a stale result fails the run (D-017). `make full` itself still does not. |
| F6 | (AUDIT_1) Hysteresis histograms drew the old 8-25 mV window. | Cosmetic | Fixed (D-017): 6-35 mV. |
| F8 | The D-017 sizing could not be built. The sizing script does not know two limits of the layout generator: an interdigitated row with three source/drain nets needs fingers of at least 1.81 um, and `mirror_interdig` takes at most two devices with an odd finger count. `make layout` found both, and one iteration went to the correction (D-018). | Low | Open. Recommended: two sizing asserts next to the resistor-length assert added in D-017, at the next sizing change. |
| F9 | `check.magic_drc` compared Magic's total with its per-rule box counts; leaf test t_block failed on a negative difference. | Low | Fixed (D-018): counts the boxes of the rules off the allow-list. |
| F10 | Resistor end resistance was a constant 85 ohm per end at any width; the model's terminal resistors scale as 1/W. | Low (latent) | Fixed (D-018) in sizing and layout. Every resistor other than Rs is 2 um wide, where both forms agree, so no earlier result changes. |
| F11 | `sim/tbl/run_tbl.py` logged the parallel extracted TB10 run's wall time when it joined it, after the other benches: the 5.3 h quoted for that run was the other benches' time (iteration 1: 9046 s). | Info | Fixed (commit `a96f153`): the log shows the run's own simulation time; the notes and the guide are corrected. |
| F12 | TB3_trip: 4 of 270 runs stalled in the first operating point at VDD 0.3 V (iteration 1, solver). | Info | Retry variants (solver options only, D-017). Iteration 2: 270 / 270 ok, no run needed a variant (`sim/tb3_trip/results/tb3_trip`). Closed. |
| F14 | TB8's pulse measurement does not do what it documents: `sim/lib_tb.py` `pulses_norm` says a level change is a completed swing (one rail zone to the other), but takes every pair of consecutive 50 % crossings of v_out / VDD(t). A runt that grazes 50 % counts as a pulse: iteration 2 pre-layout tt/125C/3.6 V case 3, a 3 ns runt on the LOW-expected copy peaking at 51 % of the supply (VDD 0.99 V), reads 0.084 ns and fails TB8. | Medium (gate verdict) | Closed by D-019 (`ac17072`, chosen by the owner): `pulses_norm` now counts completed swings as documented; TB8's only user.  TB8 shortest pulse 3.0 ns (the runt, judged by its own width), five case-5 runs read longer, none shorter. |
| F15 | TB8 never tests the EN = 0 off-state on the spec supply ramps (1 us and 100 us, `spec.yaml` en.supply_ramps_s): cases 3-4 tie EN high, the off-state check (vout_off_v, cases 0-1) sees only the bench's 50 ns setup ramp, which is not a spec ramp (D-011's argument), and case 5's EN = 0 phase (20 us ramp) is reported only. The extracted macro exceeds 0.33 V on that 50 ns ramp at ss/-40C (0.363 V at VDD 1.1 V, 2-3 ns). | Medium (coverage) | Closed by D-019 (`ac17072`): cases 6 / 7 (EN = 0 on the 1 us / 100 us ramps) gated 0.33 V, case 5 early_high_v gated; cases 0-1 judged from 100 ns.  TB8 worst 0.262 V (case 6, ss/-40C/3.6 V); extracted 0.316 V at ss/-40C (14 mV left, listed as a known limitation together with the 0.363 V on the 50 ns setup ramp, now reported). |
| F16 | TB8 case 7 as first defined (100 us ramp, case 4's 10 us settled tail, EN = 0) stalled ngspice at four corners (ss/125C/3.6 V, fs/125C/3.6 V, sf/-40C/3.0 V, sf/27C/3.6 V) in every solver variant tried: the three retry variants, method gear, tmax / 2, trtol 10, rshunt 1e13. With a 0.2 us tail all four finish in 15-17 s: the stall sits in the settled tail, as in cases 1 / 3 / 4 (D-006). | Info | Closed in D-019: case 7 ends 0.2 us after its ramp; the gated peak falls mid-ramp (VDD about 0.8 V) and final_ok reads the last 100 ns. 360 / 360 TB8 runs ok, none of case 7 retried. |
| F17 | TB7's idle classification (D-010's rule) depends on where a settling flip's edge falls against the window start. Iteration 2, fs/27C/3.3 V, VIC 1.2 V, seed 1793293142: one clean falling transition with its VDD/2 crossing at 149.236 ns, 0.76 ns before the 150 ns window, left only its tail and undershoot in the window (0.136 V peak-to-peak, no crossing), which the "> 0.1 V without a crossing" clause reads as an oscillation; the iteration-2 sizing had moved this sample's flip 70-125 ns earlier than in D-010's analysis. | Medium (gate verdict) | Closed by D-020 (`260264a`, chosen by the owner): crossings counted from 145 ns.  Offline and in the re-run exactly that run of 2475 changes (osc_flag 1 -> 0, one settling flip at 149.2 ns, limit 500 ns). |
| F13 | `sizing/sizing_report.md` section 3 still describes the first sizing's choice: Rs solved for 14 mV and "the largest alpha whose spread is <= 2.2 wins" against the 8-25 mV window. Since D-017/D-018 the Rs solve aims at vh_scale x 14 mV = 15.1 mV, and the only candidate, (4, 6), was chosen from the simulated Monte Carlo spread (its hand-model spread is 2.74). The `D` dict comments and the decision entries are correct. | Cosmetic | Open. The sizing script's sha256 is written into the frozen `sizes.spice` (the staleness check of `flow/common.py`), so even a wording fix re-opens the freeze. Fix it with the next sizing change, together with F8. |

### Gains of margin over 30 % in gate TBL (listed, not failed; each explained)

| Check | Pairs | Before layout -> extracted | Reading |
|---|---|---|---|
| TB2 chain bandwidth, ss/125C/3.0 V, three VIC | 3 | 60.7-61.1 -> 64.6-65.0 MHz (limit 50 MHz) | The simulation netlist carries the layout parasitic estimate at scale 1.2 (D-016), which is at least the extraction at 35 of 36 calibration points: the pre-layout model is pessimistic by design, so the extracted chain is a little faster. |
| TB7 idle min_pulse_s, VIC 1.2 V with the termination (VID = 0) | 5 | 500 ns -> none | With the inputs shorted the idle output is not defined in v0 (failsafe off, a documented deviation): before layout the output makes one 500 ns excursion in the window (osc_flag 0, n_settle_flip 0), extracted none. Both meet the 2 ns limit by orders of magnitude; no improvement is claimed. |
| TB8 min_pulse_s case 4, ss/125C/3.0 V | 1 | 540 ns -> 8.4 us | The wake-up race of D-019 (EN tied high on the 100 us ramp): the pulse width does not pair corner by corner. |
| TB8 min_pulse_s cases 3 / 5, worst against worst | 1 | 3.0 -> 4.0 ns | D-019: the layout did not shorten the shortest wake-up pulse over the 45 corners. |

## Rulings on decisions since AUDIT_1

| ID | Change | Ruling | Reason and condition |
|---|---|---|---|
| D-015 | Gate TBL defined: a json gate on the post-layout evaluator | **Accept** | No limit changed. The criterion (every metric within 30 % of its margin) is the frozen one; how it is read (losses of margin gated, gains over 30 % listed and explained) was fixed in the notes before the runs. |
| D-016 | Layout parasitic estimate in the simulation netlist; stage 2 re-sized (iteration 1) | **Accept** | No limit changed. The estimate was calibrated on 36 extracted points (at scale 1.2 it is at least the extraction at 35 of 36) and is never in the LVS reference. The iteration-2 layout extracts 2842.6 fF of wiring against the 2836.2 fF the estimate was calibrated on. Side effect found later: the iteration-1 stage-2 re-size made the power-up wake-up runts common (TB8 case 3, runs with a runt 2 / 45 at iteration 0, 34 at iteration 1, 35 at iteration 2; outputs leave the LOW rail at 0.94 V instead of 0.69 V), see F14, F15 and D-019. |
| D-017 | Iteration-2 design (alpha 1.4); retry variants for TB3_trip and TB3_hmc; plot window; hash audit in `run_full.sh` | **Accept the bench and tool changes**; the design is superseded by D-018 | The retry variants change solver options only, as already accepted for TB3_off (D-013); circuit and stimulus are untouched and the record keeps the first status. |
| D-018 | Alpha 1.5 (4, 6), Rs 5 um wide, load fingers 1.85 um, 1/W end resistance, `magic_drc` fix | **Accept** | No limit changed. The regression's hysteresis Monte Carlo passes: TB3_hmc 600 / 600, V_H 7.30-24.20 mV inside 6-35 mV (iteration 1: 17 below 6 mV); TB3_trip 270 / 270. |
| D-019 | TB8: off-state of cases 0-1 from 100 ns; completed swings only; new cases 6 / 7 and case 5 early_high_v gated; TBL judges the wake-up pulse (cases 3, 5) worst against worst over 45 corners | **Accept** | Chosen by the owner after the alternatives were laid out (design change; leave failing).  Each relaxation has a matching tightening or a precedent: the setup ramp is not a spec ramp (D-011 excluded it for the pulse check on the same ground), and the spec ramps are now covered with EN = 0, which the bench never did (F15); the pulse rule now does what its own docstring says (F14); the wake-up pulse widths do not pair corner by corner (extracted longer in 62 of 90 pairs, shorter in 25), so a per-pair 30 % rule measures the race, while worst against worst over 45 corners with full coverage required measures the layout.  No limit changed.  Conditions: the package lists the low-supply behaviour (outputs float to about a third of the supply below about 1.2 V with EN = 0; 0.316 V extracted on the 1 us spec ramp at ss/-40C, 14 mV under the limit) and the integration rule (logic reading RXn_O in reset, EN = 0, until VDD >= 2.0 V; D-008): met, `package/KNOWN_LIMITS.json` low_supply_off_state and en_and_supply. |
| D-020 | TB7 / TB7_mc: the idle window's VDD/2 crossings counted from 145 ns (a 5 ns guard before the 150 ns start) | **Accept** | Chosen by the owner after the alternatives were laid out (leave TB7_mc failing with the explanation; start the window later, which would move the same edge problem to a new place).  The flagged waveform is one clean transition to a rail, the event D-010 already classifies as a settling flip, at 149.2 ns, well inside D-010's 500 ns limit.  The relaxation is a 5 ns sliver and is matched by a tightening in the same sliver: a crossing there now also counts toward the two-crossing oscillation rule, where it was invisible before.  Offline and in the re-run exactly one of 2475 runs changes; no limit changed, `gates.yaml` untouched.  Condition: none beyond what v0 already lists (failsafe not guaranteed, the idle state undefined). |
| D-012 | Conditions of AUDIT_1: (1) gain, delay and one eye run at ff/125C/3.6 V, VIC 0.05 V re-checked after extraction; (2) the constant-gm bias (R6) if gain there falls below 4 or a timing check fails; (3) the limitation listed in the package notes | **Accept, (1), (2) and (3) met** | Extracted at ff/125C/3.6 V, VIC 0.05 V: A1 4.78 (limit 4), tPD 2.48 / 3.10 ns, every TB4 timing limit and the TB5 eye limits met, so R6 is not taken.  (3) `package/KNOWN_LIMITS.json` saturation_margin (T12). |

## Carried forward

- Chip integration (PLAN_V2 P7/P8, owner-gated): handoff items 15-18.
- Secondary ESD cell UNQUALIFIED.
- Failsafe is off in v0: the idle output state is undefined.
- With EN = 0 and the supply below about 1.2 V the outputs float to about a third of the supply (D-019); the integrator
  holds the reading logic in reset and EN low until VDD >= 2.0 V.
- F2, F8 and F13 above.
- The branch's local commits are not pushed (the owner's yes is needed).
