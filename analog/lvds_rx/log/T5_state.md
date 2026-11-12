# T5 state at the 2026-11-12 crash (written by the orchestrator, not by the T5 agent)

The T5 agent (full regression and Monte Carlo) ran from 04:32 to about 17:40 on 2026-11-12 and was killed by a PC crash
before it could report. This note reconstructs its state from the files it left. Nothing below was re-verified after the crash
except where it says "checked".

## What T5 completed
- **First full regression** (`results/first_full_run/gates.json`, 7.8 h wall): 13 gates PASS, 6 FAIL
  (TB1, TB3_off, TB3_hmc, TB7, TB7_mc, TB8), TB11 not applicable.
- **Sizing iteration 1** (`results/iterations.jsonl`, block `stage1_headroom`): `vr_tt` 1.25 -> 1.17 so the NMOS input pair keeps
  >= 56 mV saturation margin at VIC = 2.35 V on fast corners at 3.0 V. Cost: stage-1 gain minimum 5.10 -> 4.78 (limit 4).
  Fold-pole assert relaxed from 3x to 2.5x f1 at the two resistor cross corners only.
- **Lookup tables** for all 15 process x temperature combinations (30 `.mat` files in `luts/`, about 4.3 GB, git-ignored;
  `lut_regen/regen_all.sh tttemps | procgrid`). TB1's LUT cross-check now uses the table of each run's corner
  (reported worst gm/ID error 2.2 %, VGS error 8.6 mV).
- **Harness 1.3**: solver-option retry for stalled or non-converged runs (retried runs are listed in the report), Monte Carlo seeds
  derived from the run key, timeouts lowered to 240-300 s.
- **Gate mutation tests** extended (`flow/mutants_t5.py`). The input-pair-area/4 mutant survived the offset gate, so the gate
  was tightened from the 8 mV hard limit to the 5 mV design target (D-014).
- **Decisions D-009 to D-014** in `spec/decisions.yaml` (read them: each has trigger, measurement and what changed).

## Decisions that change a limit (need independent review in the audit)
| ID | Kind | Change | Inside the pre-authorised ladder? |
|---|---|---|---|
| D-009 | rung R3-1 | hysteresis window 8-25 mV -> 6-35 mV (Monte Carlo minimum 6.7 mV at ff/-40C/3.6 V) | yes |
| D-010 | waiver | idle test: one power-up settling flip per lane is allowed if it is over by 500 ns; two or more crossings still count as oscillation | no (bench definition) |
| D-011 | waiver | enable test: minimum-pulse check starts at 100 ns in the three cases that use a non-spec 50 ns supply ramp | no (bench definition) |
| D-012 | waiver | **saturation-margin gate**: 50 mV margin enforced only at the seven design corners; at all 47 corners a device may be up to 100 mV into triode (worst measured -85 mV: steered PMOS input device, VIC 0.05 V, ff/125C/3.6 V). Cause: resistor-diode bias current rises 60 % there. The constant-gm bias (ladder R6) would fix it but its trigger did not fire | **no: outside the ladder** |
| D-014 | tightening | offset sigma limit 8 mV -> 5 mV | n/a (stricter) |

## What was NOT finished
- The **second (final) full regression** was started at about 14:46 with `tools/cx tools/run_full.sh` and was about 3 hours in.
  `results/gates.json` and `results/REPORT.md` on disk are from the short `make check` that precedes it, not from a full run.
  Per-run results of benches that had already finished may be reusable (the harness skips up-to-date runs by content hash); unknown.
- No T5 report, no DESIGN_LOG entry, no commit by the agent. The orchestrator committed the tree as a checkpoint.
- T6 (independent audit) has not started.

## How to continue
1. `tools/cx make check` (about 1.5 min) to confirm the tree is consistent after the crash.
2. Run the final full regression as a detached machine job, with no agent waiting on it:
   `tools/cx tools/run_full.sh`; it ends by appending `EXIT <code>` to `results/full_run.log`. Expect several hours.
3. Triage any remaining failing gate one at a time, then `make mutants`, then the audit (T6), which must judge D-009 to D-012.
4. Disk: about 9 GB free at the crash. `sim/*/results/*/work` directories from the interrupted run can be deleted.
