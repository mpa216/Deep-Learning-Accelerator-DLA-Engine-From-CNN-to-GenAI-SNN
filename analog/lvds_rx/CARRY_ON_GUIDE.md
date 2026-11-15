# LVDS RX macro: how to carry on (T11 to T13)

Written 2026-11-15. Complements `LVDS/GUIDE_FOR_YOU.md` (the 2026-11-07 background guide).
This file lives in the project folder `~/Desktop/APIC_Return/.claude/worktrees/lvds-rx/analog/lvds_rx`
(the same folder as `LVDS/lvds_rx_work/`). All paths below are relative to it unless they start with `~` or `/`.

---

## 1. Short answer: is it just machine simulation?

Mostly yes: about 15 to 20 hours of machine time remain, but every stage ends in a pass/fail result you must
read, and a failure sends you back into a design loop.

What is left, in order:

1. Read the iteration-1 pre-layout regression (it was running on 2026-11-15, about 4 to 8 hours).
2. Run the post-layout suite on the iteration-1 layout and evaluate gate TBL (about 5 to 6 hours).
3. Write the final audit, `results/AUDIT_2.md` (mostly scripted checks plus your judgement).
4. Build and check the package with `make package` (minutes).
5. T13: a last full regression, `make layout`, the report, a closing design-log entry, then push.

Not machine work: deciding what to do when a gate fails, the audit's judgement, and the log entries.
Chip integration (PLAN_V2 tasks P7/P8) is out of scope: nothing in the DLA chip was touched.

The expected outcome is a pass, but it is not measured yet. With the layout estimate the slow-corner delay is
4.50 ns against the 5 ns limit, and the new layout's extracted wiring (2836 fF) matches the layout the estimate
was calibrated on (2843 fF).

---

## 2. Where everything lives

| What | Where |
|---|---|
| GitHub | `mpa216/Deep-Learning-Accelerator-DLA-Engine-From-CNN-to-GenAI-SNN`, branch `lvds-rx` (pushed at `66d34d0`; later commits are local until you push) |
| Working copy | `~/Desktop/APIC_Return/.claude/worktrees/lvds-rx` (a git worktree of the main repo, branch `lvds-rx`) |
| Project folder | `analog/lvds_rx/` inside that worktree (= `LVDS/lvds_rx_work/`) |
| Container | Docker `apic_headless`; the worktree is at `/foss/designs/.claude/worktrees/lvds-rx` inside it |
| Tool wrapper | `tools/cx` (sets the PDK variables and the single-thread limits); run every EDA command through it |
| The plan | `PLAN_V2.md`: tasks T0-T13 (section 8), gates (3.2), audit (5.2 item 6), layout checks (6.4), package (7) |
| Where to resume | `log/T11_notes.md`: the piece table at the top, then the dated findings |
| Decisions | `spec/decisions.yaml` (D-001 ... D-016) and `sizing/FROZEN.md` (the frozen-file hash tables) |
| Gates | `spec/gates.yaml`; results in `results/gates.json`, `results/REPORT.md`, `results/gates_layout.json` |
| Sizing | `sizing/lvds_rx_sizing.py` (design variables in the `D` dict), outputs `sizing/sizes.spice`, `layout/device_table.json` |
| Netlists | `netlist/lvds_circuit.py` (the circuit, written once) -> `gen_core.py` (simulation), `gen_lvs_ref.py` (LVS reference) |
| Layout | generators in `layout/` (lib, leaf_tests, lane, bias, macro); deliverables in `results/layout/` (GDS, PNG, PEX) |
| Post-layout | benches `sim/tbl_*`; `sim/tbl/` holds the cores, the estimate maker, the evaluator and the runner; results in `results/post_layout/` |
| Package | `package/` (generators, `checks/`); everything in it is generated |
| Reports | `log/T9_report.md`, `log/T10_report.md`, `DESIGN_LOG.md`, `results/AUDIT_1.md` |

Read first: PLAN_V2 sections 3.2, 5.2, 6.4, 7 and 8, then the top of `log/T11_notes.md`.

---

## 3. Ground rules that keep the design consistent

- Never change `main`, `info.yaml`, `lvs_config.json`, `gds/`, `verilog/`, `librelane/`, `rtl/dla_*` or
  `signoff/A56/`. `Analog/` and `/foss/pdks` are read-only; `layout/magic_flow/` is not modified.
- Frozen files (the newest table in `sizing/FROZEN.md`: `sizes.spice`, `device_table.json`, `lvds_rx_core.spice`,
  the LVS references, `parasitic_estimate.json`; plus `spec/*.yaml`) change only together with a new
  `spec/decisions.yaml` entry and a new `FROZEN.md` table. `flow/lint.py` fails `make check` when a spec file
  changes without its entry (`python3 flow/lint.py --show-hashes` prints the hashes to record).
- Never relax a limit by hand. The fallback ladder in `spec/decisions.yaml` allows the next rung only when its
  trigger fired twice in a row, measured. Sizing iterations are capped at 5 per block and 8 per phase, logged
  with `flow/iterate.py log`.
- At most 4 simulations at once (8 cores, the machine stays usable). `make full` alone uses 6 jobs: use
  `tools/run_full.sh 4` instead.
- `make check` overwrites `results/REPORT.md`, `env.json`, `gates.json` and `manifest.json`. Commit those only
  after a full run; otherwise restore them with `git checkout -- results/`.
- Commit in small pieces as `mpa216`. Push the branch when you want it on GitHub (`git push origin lvds-rx`).

---

## 4. Current state (2026-11-15)

T11 found that the frozen sizing missed its timing once the layout's real loads were included. Iteration 1
re-sized stage 2 and was being re-verified when the work paused.

| Step | Result | Commit |
|---|---|---|
| Post-layout benches + gate TBL defined (decision D-015) | `sim/tbl/evaluate.py`: every metric within 30 % of its pre-layout margin | `8893ac1` |
| RC extraction bug | Magic 8.3.636 `extresist` counted every coupling twice; repaired by `check.rc_repair` | `ccff3ff` |
| Iteration 0 (the T10 layout) | TBL FAIL: tPD 6.76 ns against 5 ns at ss/125C/3.0 V (VID 350 mV), 8.22 ns against 8 ns (VID 100 mV); stage bandwidth 0.44 against 0.8 x data rate | `c9190a5` |
| D-012 freeze condition | met at ff/125C/3.6 V (gain 4.78, timing ok), so ladder R6 was not taken | (same) |
| Iteration 1 design (D-016) | layout parasitic estimate in the simulation netlist (calibrated on 36 extracted points, within about 1 %) + stage 2 re-sized (`n_t2` 10, `gmid_s2` 8, `L_ld` 0.28): tPD 4.50 ns with the estimate; I_lane 757 uA at tt (limit 1.5 mA) | `96c5c2e` |
| Iteration 1 layout | `make layout` all green, same 650 x 192.1 um; PEX regenerated | `9a957e2` |
| T12 package generators | written; LEF, OpenROAD and model checks pass in a dry run | `66d34d0` |
| Running at the pause | full pre-layout regression (log `results/full_run.log`) and the extracted three-lane TB10 run (`sim/tbl_lanes/results/tbl_lanes_pex/`) | committed after they end |

Root cause of iteration 0, in one line: the pre-layout netlist had no wiring capacitance and about a third of the
real junction area, so the frozen design had 9.5 % delay margin for none of the layout's load.

---

## 5. Finish T11, step by step

Define this once per terminal (it runs a command inside the container, in the project folder):

```bash
cd ~/Desktop/APIC_Return/.claude/worktrees/lvds-rx/analog/lvds_rx
CX="docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx"
```

1. **Check the regression finished.** `tail -3 results/full_run.log` ends with `EXIT 0` (all gates pass) or `EXIT 1`
   (a gate failed). `results/REPORT.md` has the table; `python3 flow/gates.py --tier full` prints it again.
   If the log has no `EXIT` line, it is still running (`docker exec apic_headless pgrep -fa run_all`).
2. **Review and commit.** Every gate PASS with `runs N/N` (the expected count). Commit `results/`,
   `sim/*/results/` and `layout/` changes. A failed gate: go to section 7 first.
3. **Run the post-layout suite** (about 5 to 6 hours; finished runs are reused from the harness cache):
   `$CX python3 sim/tbl/run_tbl.py --jobs 4` (detach it with `nohup ... &` or a second terminal).
   Progress: `results/post_layout/run.log`. It ends by running the evaluator.
4. **Evaluate gate TBL.** `python3 flow/gates.py --tier full --phases postlayout --out results/gates_postlayout.json`.
   Read `results/post_layout/TBL.md`: the failed checks, any "gain of margin over 30 %" (explain each one),
   and the D-012 section. Compare with `results/post_layout/iter0/TBL.md`.
5. **Audit**, written to `results/AUDIT_2.md` (PLAN_V2 5.2 item 6; the plan wants someone other than the builder,
   which you are):
    1. Rebuild from `sizing/`: `$CX python3 sizing/lvds_rx_sizing.py`, `python3 netlist/gen_core.py`,
       `python3 netlist/gen_lvs_ref.py`; `git diff` must show nothing.
    2. Results tied to the current inputs: `$CX python3 tools/audit_hashes.py --tier full`.
    3. Layout from the GDS alone: KLayout deck, Magic extraction and Netgen LVS on `results/layout/lvds_rx_x3.gds`
       against `netlist/lvds_rx_lvs_ref.spice` (the functions are in `layout/lib/check.py`: `klayout_drc`,
       `extract`, `netgen_lvs`).
    4. Mutation tests: `results/mutants.json` (from the regression), every mutant detected.
    5. Hash chain: `results/manifest.json` against the files.
    6. The handoff's UNVERIFIED items: each closed or listed in `package/KNOWN_LIMITS.json`.
    7. Look at `results/layout/lvds_rx_x3.png` and the lane PNGs.
6. **Close T11.** Write `log/T11_report.md` and a `DESIGN_LOG.md` entry, tick the piece table in
   `log/T11_notes.md`, commit.

---

## 6. T12 packaging and T13 close

T12 (minutes):

1. `$CX make package`: pin capacitance of the extracted macro, then gds / lef / lib / spice / verilog / tb /
   KNOWN_LIMITS, the PLAN_V2 section 7 checks, and the README.
2. `package/checks/report.json` must say `"all_ok": true`. Read `package/README.md` and `KNOWN_LIMITS.json`.
3. The optional generated xschem view (PLAN_V2 1.2 A9) can stay skipped; say so in the T12 log entry.
4. Commit `package/`.

T13 (about 6 to 9 hours of machine time):

1. `$CX bash tools/run_full.sh 4`, then `$CX make layout`, then `python3 flow/report.py`.
2. All gates PASS with the expected counts: `results/gates.json` green, `results/gates_layout.json` PASS,
   gate TBL PASS.
3. A closing `DESIGN_LOG.md` entry with the open items (integration P7/P8, ESD qualification, failsafe v1, ...).
4. `git push origin lvds-rx`; open a pull request only if you want one (never merge into `main` by accident).

---

## 7. If something fails

- **Find the failing run.** `results/gates.json` names the check and the worst run id. The run folder is
  `sim/<bench>/results/<spec>/work/<run id>/` with `deck.spice`, `ngspice.log` and `result.json`.
- **Status `timeout` or `sim_error`** (convergence stall, not a design fault): TB7 and TB8 have retry variants
  (49 ps step, reltol 0.05). Re-run only that gate: `$CX bash tools/run_only.sh TB8 4 rerun_tb8`.
- **A limit fails (design).** Try knobs without touching frozen files:
  `$CX python3 sizing/lvds_rx_sizing.py --set n_t2=12 --out .scratch/try1` (any key of the `D` dict), simulate
  the candidate with the estimate core (scripts in `.scratch/t11/`: `iter_explore2.py`, `est_probe.py`). When one
  works: set it in `D` with a comment, regenerate (sizing, `gen_core.py`, `gen_lvs_ref.py`), log it with
  `python3 flow/iterate.py log ...`, add a `decisions.yaml` note and a `FROZEN.md` table, run the full regression.
- **After any device change:** `$CX make layout` (leaf tests, lane, bias, macro with PEX), then
  `$CX python3 sim/tbl/make_cores.py` and `python3 sim/tbl/make_benches.py`, then the post-layout suite.
- **TBL fails but the absolute limits pass:** compare pre-layout and extracted per check in `TBL.md`. If the
  estimate no longer matches the layout, recalibrate it (`python3 sim/tbl/make_estimate.py 1.2` reads the current
  extraction; choose the scale the way `.scratch/t11/calib.py` does). That changes a frozen file: decision entry.
- **The ladder** (`spec/decisions.yaml`): for example R6 (constant-gm bias) when the tPD spread over the corners
  exceeds 1.5 ns at VID 350 mV twice in a row. Rungs are taken in order, never skipped.

---

## 8. Command cheat sheet

```bash
cd ~/Desktop/APIC_Return/.claude/worktrees/lvds-rx/analog/lvds_rx
CX="docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx"

$CX make check                              # environment + lint (restore results/*.json afterwards)
$CX bash tools/run_full.sh 4                # full pre-layout regression -> results/full_run.log
$CX bash tools/run_only.sh TB4,TB8 4 retry  # selected gates only -> results/retry_run.log
python3 flow/gates.py --tier full           # the gate table of the stored results
$CX make layout                             # leaf tests, lane, bias block, macro, PEX (about 20 min)
$CX python3 sim/tbl/make_cores.py           # post-layout netlists from a new PEX
$CX python3 sim/tbl/run_tbl.py --jobs 4     # post-layout suite + evaluator -> results/post_layout/
python3 flow/gates.py --tier full --phases postlayout --out results/gates_postlayout.json
$CX make package                            # T12 package + checks + README
python3 flow/lint.py --show-hashes          # hashes for a decisions.yaml entry
python3 flow/iterate.py status              # sizing iterations used so far
git push origin lvds-rx                     # publish the branch
```

---

## 9. Gotchas and run times

| Job | Typical wall time |
|---|---|
| Full pre-layout regression, 4 jobs | 4 to 8 hours (the 15 000-run offset Monte Carlo is the biggest part) |
| `make layout` | about 20 minutes (leaf tests 13) |
| Post-layout suite, 4 jobs | 5 to 6 hours; the extracted three-lane TB10 run alone takes 5.3 hours on one job |
| One extracted run | 15 to 80 x its pre-layout time (TB4 about 4 min, TB12 about 15 min) |
| `make package` | about 3 minutes |

- A killed ngspice can stay behind as a zombie (`<defunct>`): harmless, but `pgrep -c ngspice` counts it.
- Magic's RC extraction double-counts couplings in this version; `run_macro.py` repairs it with `check.rc_repair`.
  Never use a raw `pex_rc` netlist.
- The harness caches every run by the hash of its inputs: change an input and it re-runs; `--force` re-runs anyway.
- TB8 can stall on long supply ramps at fast corners; its retry variants usually recover.
- Leaf tests: L = 0.28 um devices need the Magic CO.6 allow-list (Magic is stricter than the foundry deck there).
- `layout/lane/run_lane.py` checks the reference netlist against the NEWEST table in `sizing/FROZEN.md`.
- Scratch work lives in `.scratch/` (git-ignored). Keep anything worth keeping in `log/` or `results/`.
