# AUDIT_1: pre-layout audit (task T6), 2026-11-14

**Verdict: PASS with findings.** The pre-layout design may be frozen. Two limits were relaxed outside what the plan
pre-authorised (D-012 and, by test definition, D-007/D-010/D-011); they are accepted here with conditions. The owner can
overrule any of them: the cost of overruling D-012 is the constant-gm bias (ladder R6) and a new regression.

## How this audit differs from the plan

PLAN_V2 5.2 item 6 asks for a different agent in a clean work directory that re-runs `make full` (about 8 hours). The
owner asked for less machine time and no further agents, so this audit was done by the orchestrating session, in place,
with these substitutes:

| Plan step | What was done instead |
|---|---|
| (a) rebuild from `sizing/` and rerun `make full` | Rebuilt sizing, netlist and LVS reference from the scripts and compared hashes. The full tier was not re-run as a whole; see (b). |
| (b) compare results with the builder's | Every stored run was checked against the current inputs without simulating (`tools/audit_hashes.py`). One Monte Carlo bench (TB3_hmc, 600 runs) was re-simulated and compared run by run. Three independent decks written for this audit were compared with the regression. |
| (c) DRC/LVS/PEX from the GDS | Not applicable before layout. |
| (d) rerun mutation tests | Done. |
| (e) hash chain in `manifest.json` | Done. |
| (f) open UNVERIFIED items | Not re-walked item by item; the open list is in "Carried forward" below. |
| (g) look at the plots | Done for eye, offset and hysteresis plots. |

Independence: the auditor reviewed the plan and supervised the tasks but did not write the sizing script, the netlist
generator, the benches or the harness. That is weaker than a clean-room agent and is stated here so nobody reads more
into the verdict.

## What was checked and what came out

1. **Full-tier gates on the current sizing: 17 PASS, 1 not applicable** (TB11 exists only with the constant-gm bias),
   expected run counts everywhere, 0 runs not ok. Record: `results/full_2026-11-14/` (gates, manifest, report, mutants,
   hash audit). 21,017 gated runs plus 2,221 helper runs.
2. **Rebuild.** `sizing/lvds_rx_sizing.py` (127 asserts, 0 failed), `netlist/gen_core.py`, `netlist/gen_lvs_ref.py`:
   `sizes.spice`, `lvds_rx_core.spice` and `layout/device_table.json` came out byte-identical to the committed files.
   The two LVS reference netlists did **not** (finding F1).
3. **Results tied to current inputs.** All 17 benches: every planned run has a stored result with status ok. 12 benches
   match by content hash; for TB4, TB5, TB7, TB7_mc the stored hash differs for a harness reason (finding F2) and the
   runs were confirmed by ingredients (deck text, generated stimulus, per-run result hash, simulated after the sizing
   reached its current content). `results/audit_hashes.json`.
4. **Reproducibility.** TB3_hmc re-run on 2026-11-14 (185 runs simulated fresh, 415 taken from the run the 2026-11-12
   crash interrupted): all 600 runs have metrics identical to the results of 2026-11-12 (`tools/audit_compare.py`,
   largest relative difference 0).
5. **Independent decks** (`docs/figures/make_waveforms.py`: ideal sources, no input network, typical corner):

   | Quantity (VIC 0.05 / 1.2 / 2.35 V) | Audit deck | Regression |
   |---|---|---|
   | Stage-1 gain | 7.19 / 7.25 / 7.43 | 7.19 / 7.25 / 7.43 (TB2) |
   | Hysteresis, mV | 13.4 / 13.2 / 13.0 (0.1 mV grid) | 13.3 / 13.1 / 12.9 (TB3_trip) |
   | Stage-1 bandwidth | about 200 MHz (20 points per decade) | 188 MHz (TB2) |
   | Delay at VIC 1.2 V, VID 100 mV | 3.5 ns | 3.3 ns rise / 3.7 ns fall (TB4, through the input network) |

6. **Mutation tests: 11 run, 11 detected, 0 survived**, after repairing one broken test (finding F3).
7. **Hash chain.** `manifest.json` carries the sha256 of `sizes.spice` (904ffecb...) and of the netlists; they equal the
   files on disk and the rebuilt files. `spec/spec.yaml` and `spec/gates.yaml` hashes equal the latest `files_after`
   in `spec/decisions.yaml` (D-009 and D-014); the frozen-file lint passes.

## Findings

| # | Finding | Severity | State |
|---|---|---|---|
| F1 | `netlist/lvds_rx_lvs_ref.spice` and `_flat.spice` were not regenerated after the T5 sizing change: RL 19.664 um (now 18.395), Rs 9.315 um (now 8.862). Layout would have been compared against old resistor lengths. | Medium | Fixed: regenerated. The resistor leaf cells of the layout library were built at the old lengths and must be regenerated in T9. |
| F2 | Harness 1.3 run hash: for a bench whose prep hook writes an include file into the run directory, the hash takes that file's content from the copy left by the previous execution. The hash also contains the new content, so a changed input always changes the hash: the flaw cannot make the cache reuse an outdated result. It causes one unnecessary re-simulation after any change of a generated file, and it makes "stored hash equals planned hash" unusable as a staleness test for those benches. | Low | Open. Not fixed now because a fix changes every hash of those benches. Fix with the next harness version (hash the prep content only). Until then use `tools/audit_hashes.py`. |
| F3 | Mutant `frozen_edit` reported a false survivor: its "legitimate change" step replaced all decision entries by one test entry, which removed the real entry that legitimises the D-009 change of `spec/spec.yaml`. The gate itself was working. | Low | Fixed in `flow/mutants.py` (append instead of replace). |
| F4 | `flow/run_all.py --stage gates` evaluates whatever results are on disk and prints PASS for results simulated from an older sizing. Seen on 2026-11-13: seven benches showed PASS from the pre-iteration sizing. | Medium | Open. Mitigation: `tools/audit_hashes.py` before trusting a gate table. Recommended: call it from `make full` and `make report`. |
| F5 | The T5 agent ended without a report, a design-log entry or a commit (PC crash). Its decisions D-009 to D-014 were reconstructed from files. | Info | Closed by this audit and the DESIGN_LOG entry of 2026-11-14. |
| F6 | The hysteresis histograms still draw the original 8 to 25 mV window, not the 6 to 35 mV window in force. | Cosmetic | Open. |
| F7 | TB3_off deletes its 15,000 run directories after the run, so those runs can be checked by hash only (they match). A later full regression re-simulates them (about 2 h). | Info | Accepted. |

## Rulings on decisions that changed a limit or a test

| ID | Change | Ruling | Reason and condition |
|---|---|---|---|
| D-007 | TB6 common-mode step: jitter gated only on edges at least 1 UI away from a step | **Accept** | The stimulus is a 2.3 V common-mode step in 2 ns placed exactly on a data edge; no false toggle occurs. Limitation to state in the datasheet: a data edge that coincides with a full-range common-mode step can move by up to 1.7 ns. |
| D-008 | No under-voltage lockout; "LOW below 2.0 V" holds only with EN = 0 | **Accept** | A lockout needs an absolute reference the macro does not have. Integration rule: hold EN low until VDD is at least 2.0 V. |
| D-009 | Hysteresis window 8 to 25 mV widened to 6 to 35 mV | **Accept** | Inside the pre-authorised ladder (R3 rung 1). Measured over 600 Monte Carlo runs: 6.7 to 22.4 mV. The offset budget still closes (about 40 mV used of 95 mV). |
| D-010 | Idle: one power-up settling flip per lane allowed if over by 500 ns | **Accept** | With failsafe off the idle state is undefined by design. Re-run on current sizing: 945 corner runs with no flip, 1,500 Monte Carlo runs with 2 single flips finished by 199 ns, no second crossing anywhere. |
| D-011 | Enable: minimum-pulse check starts at 100 ns in the three cases with a 50 ns supply ramp | **Accept** | The only short pulse (2.0 ns) occurs while VDD is below about 0.6 V on a ramp that is not a specified one. With the supply up the shortest pulse is 9.9 ns (limit 2 ns). Integration rule: do not sample the outputs during supply ramp-up. |
| D-012 | Saturation margin 50 mV enforced at the seven design corners only; -100 mV allowed elsewhere | **Accept with conditions** | Outside the ladder, so this is the weakest ruling. Measured on current sizing: 17 of 987 runs below 50 mV, 7 below zero, worst -84.5 mV, all the PMOS input pair at VIC 0.05 V at hot or fast corners. Function at the worst corner (ff/125C/3.6 V) is verified on the current sizing by the benches that include it: stage-1 gain at least 4.78 in all 315 runs (limit 4), trip point (270 runs) and delay (630 runs, at most 5.55 ns) pass at all 45 corners. The offset Monte Carlo (worst-5 corners) and the eye bench (15 corners; hot-fast only at 3.0 V) do not contain ff/125C/3.6 V, so the eye there is not simulated. Conditions: (1) TB1, TB2 and TB4 at ff/125C/3.6 V, VIC 0.05 V are re-checked after layout extraction (T11), plus one eye run at that corner; (2) if post-layout gain there falls below 4 or a delay or eye check fails, take the constant-gm bias (R6) instead of a further waiver; (3) the limitation is listed in the package notes. |
| D-014 | Offset sigma limit tightened from 8 mV to 5 mV | **Accept** | Stricter; measured 3.1 to 3.3 mV; makes the area mutant fail as intended. |

## Carried forward

- Layout library: regenerate the RL and Rs resistor leaves at the frozen lengths; one output inverter was laid out with
  nf 2 where the sizing has nf 1 (T8 note); the power-strap planner is missing.
- Secondary ESD cell remains UNQUALIFIED.
- Failsafe is off in v0: the idle output state is undefined.
- F2, F4 and F6 above.
- Disk: 19 GB free on 2026-11-14.
