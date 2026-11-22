# T13 report: closing regression, layout re-run and project close (2026-11-22)

Status: **closed.**  Every gate passes with the expected counts: `results/gates.json` green (19 PASS, TB11 not
applicable), `results/gates_layout.json` PASS, gate TBL PASS (`results/gates_postlayout.json`), package all_ok.  No limit
and no test definition changed in T13.

## 1. Closing regression

`docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx bash tools/run_full.sh 4`,
2026-11-22 10:02-10:15 (767 s): environment check, full tier, hash audit, mutants, report; EXIT 0 (commit `40bbfa7`).

* 19 PASS, TB11 not applicable (it needs ladder rung R6, not taken), every gate at its expected run count: SELFTEST 94,
  TB1 987, TB2 315, TB3_trip 270, TB3_off 15000, TB3_hmc 600, TB4 630, TB4b 70, TB5 180, TB6 20, TB7 945, TB7_mc 1500,
  TB8 360, TB9 180, TB10 10, TB12 40: 21,201 gated runs.
* `tools/audit_hashes.py --tier full`: 17 benches, 0 not current.  Mutants: 11 run, 0 survived.
* Every stored metric and run status equals the T11 record: the nine results files the run rewrote differ only in run
  bookkeeping (per-run comparison against the previous commit).  Most runs came from the harness cache.
* `results/manifest.json` now matches every input, `spec/decisions.yaml` with D-020 included.

## 2. Layout re-run

`$CX make layout`: every leaf test PASS (`ALL GREEN`, the antenna pair as designed: the bare input shows its one
violation, the protected one none), lane PASS (45.9 s), bias block PASS (29.9 s), macro with its PEX PASS (87.3 s);
gate LAYOUT PASS (`python3 flow/gates.py --tier full --phases layout --out results/gates_layout.json`).

The re-run was compared with the delivered files (scripts in `tools/`: `compare_layout_rerun.py`, `gds_same.py`,
`check_pex_rerun.py`, `same_netlist.py`; the leaf summary by a one-off column check):

| Output | Re-run against the delivered file |
|---|---|
| every GDS (leaf tests, lane, bias block, macro) | the same layout record for record; only the BGNLIB / BGNSTR dates differ (Magic's `gds write` stamps the time), so the sha256 changes |
| C-only extraction (macro, lane, bias block) | identical element sets (X 1047, D 12, C 475 for the macro); only the element order differs |
| RC extraction | the same element counts (macro X 1047, D 12, R 10601, C 5813); the macro's internal RC node numbers differ from run to run; in the lane and the bias block 34 and 9 small capacitors differ in the 5th to 6th significant digit (largest 0.0340447 -> 0.0340474 fF) |
| JSON reports, leaf summary | timings and the generation date only |

So the delivered files were restored (`git restore layout/ results/layout/ results/layout.json`): the GDS audited in
AUDIT_2, extracted for gate TBL and packaged (sha256 `892add3b...`) stays the one on record.  The same check on the
history: the GDS of commits `e4923f7` and `2607466` (two runs of the macro flow on one design) differ in 4 date records of
104,102.

## 3. Documentation brought up to date

* `DESIGN_GUIDE.md` section 6: the final status and worst values of every gate.
* `CARRY_ON_GUIDE.md` section 4: the final state, the commits, what is open.
* Gallery (`docs/figures/`): schematics redrawn from the final sizes (stage 2 and stage 3 changed; the resistor labels
  are body-only approximations, Rs reads "~0.3 k" for 0.37 kohm with its contacts); the three illustration waveforms
  re-run on the final netlist came out byte-identical (the re-sizes kept the typical hysteresis and stage 1); the eye
  diagrams and Monte Carlo histograms replaced by the closing regression's (typical eye 0.98 UI, slow-hot 0.95 UI;
  offset sigma 3.0 mV at tt; hysteresis 9.8 +- 0.88 mV at ff/-40C/3.6 V); status table and subtitle of 2026-11-22.
* Correction: the briefing page (version 5) quoted the full regression as about 19,000 runs; it is 21,201 gated runs.

## 4. Open (each needs the owner)

* Push branch `lvds-rx`: the commits since `66d34d0` are local.
* Chip integration (PLAN_V2 P7/P8, owner-gated): placing the macro, chip-level DRC / LVS, the handoff's items 15-18
  (clocks and input delays on macro output pins in OpenSTA / OpenROAD, RSZ_DONT_TOUCH_RX, the analog template geometry
  and slot, the LVS key semantics).
* ESD: the secondary cell has no HBM / CDM / latch-up qualification.  Failsafe (v1): the idle output state is undefined
  in v0.  Latch-up beyond the foundry DRC unverified.
* AUDIT_2 findings F2 (harness cache key), F8 and F13 (sizing asserts and report text, at the next sizing change).
