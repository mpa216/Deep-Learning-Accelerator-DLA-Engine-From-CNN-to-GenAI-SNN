# Plan review, lens "automation" (2026-11-11)

Scope: handoff 0, 2, 3, 6, 9, 10, 15, 16 and GUIDE_FOR_YOU.md, read against the evidence already in log/ and docs/.
Scratch: `.scratch/review_automation/` (run_tp.sh, run_tp_noenv.sh, tchk.sh). Everything marked MEASURED was run in the container.

## Measured today

1. ngspice threading (MEASURED, `tp_eye.spice`: 120 FETs = 3 lanes x 20 inverters, 1.5 us, tmax 0.1 ns, 57,470 iterations):
   - plain `tools/cx` (no OMP variables): 7.34 s wall, 639 % CPU.
   - `OMP_NUM_THREADS=1 OMP_THREAD_LIMIT=1 OMP_WAIT_POLICY=PASSIVE`: 3.97 s wall, 1 core.
   So `tools/cx` as it stands makes every direct ngspice call about 1.8x slower AND 11x more CPU-hungry; six at once thrash
   (the harness measured 0.1 s -> 11 s). The harness sets the variables itself, `tools/cx` does not. Fix: export them in `cx`.
2. Tools present: make, openroad, sta, yosys, xvfb-run, pyyaml 6.0.3 (so spec files can be YAML and a Makefile can drive everything).
3. `.git` in this worktree is a FILE (common dir = the main checkout's .git). The handoff's `echo ... >> .git/info/exclude` would write
   into the MAIN checkout's exclude file. The in-tree `analog/lvds_rx/.gitignore` already does the job (verified with git check-ignore).
   It also ignores `*.log`: result logs must be .json/.csv/.md to survive a commit.
4. `layout_announcement/caravel-gf180mcu-main/` is gitignored, so it is NOT in the worktree, but it IS readable at
   `/foss/designs/layout_announcement/caravel-gf180mcu-main/macros/simple_por` (main checkout mount). Read-only use is fine.
5. Disk: 14 GB free of 163 GB (91 % used). LUTs already use 709 MB.

## Human touchpoints in the plan and what to do with each

| Where | Touchpoint | Verdict |
|---|---|---|
| GUIDE 5.1-5.6, 6 | clone repo, copy guide files, CLAUDE.md, book folder, docker, first message | obsolete: all done on this machine |
| G0 | environment OK | automated (`make check`) |
| G1 | ambition, shuttle | default: macro only (P0-P6); P7/P8 stay owner-gated |
| G2 | spec | default from the handoff, PLUS pre-authorised fallback ladder (below) |
| G3 | architecture | default baseline; option A first but time-boxed |
| G4 / G5 | proceed to layout / sign-off | frozen machine-checked criteria + independent audit run |
| G6, GUIDE 8 email, info.yaml, padframe | organizers | stays human |
| GUIDE 9.8, 14 | hand-draw matched pair, review layout | remove; scripted ABBA + dummies + guard rings already proven (log/layout_magic.md); owner views PNGs, non-blocking |
| HANDOFF 3.3 / 14.9 Q4 | ask organizers for package/bondwire | replace by a bounded sweep (L 1-5 nH, C 0.5-1.5 pF) |
| HANDOFF 7.9 | organizer ESD cell | own series-R + diodes, flagged UNQUALIFIED in a machine-readable file |
| HANDOFF 15 P6 | `macros/lvds_rx_x3/`, `rtl/lvds_rx_x3.v` | outside the allowed directory: build under `analog/lvds_rx/package/`, orchestrator copies later |
| GUIDE 7 G4 "ask for the corner table" | owner reads tables | generated REPORT.md replaces asking |

Truly human: see the structured output (organizer answers, merge/push/tag, integration go/no-go, real ESD cell and package data, silicon/board, optional visual review).

## Paths and assumptions that must change

| Plan says | Here |
|---|---|
| `external/Book-on-gm-ID-design-main`, `$GMID_BOOK` | `/foss/designs/Analog` (read-only); `lut_regen` and the wrapper already use `luts/` then the kit |
| venv `~/venv-gmid`, `pip install` | none; pygmid 1.2.12, numpy, scipy, matplotlib, pyyaml system-wide in the container |
| `docker run ... -v $HOME/APIC:/foss/designs` | container `apic_headless` already runs; worktree = `/foss/designs/.claude/worktrees/lvds-rx` |
| branch `analog/lvds-rx-macro` | worktree branch `worktree-lvds-rx`; orchestrator commits, no checkout/branch commands |
| `.git/info/exclude` | in-tree `.gitignore` (see above) |
| clone `origin`, expect commit 6f2310f | HEAD is 9be761d (newer); nothing to clone |
| `DESIGN_LOG.md`, `sim/plots/`, `sim/corners/summary.md` | generated `results/REPORT.md`; plots next to each spec's results (harness layout) |
| `macros/`, `rtl/` at repo root | `analog/lvds_rx/package/` only |
| `.include ../sizing/sizes.spice` (relative) | harness `{deck_dir}`/absolute container paths |
| `.log` result files | gitignored; use .json/.csv |
| `$GF180_LUT_DIR` pointing at the kit | wrapper default order (env, luts/, kit) |
| `origin/main:` file references | `git show main:<path>` or read the main checkout under /foss/designs |
| venv python `python -` heredocs | the command harness refuses heredocs: always script files |

## Proposed layout and entry point

```
analog/lvds_rx/
  Makefile                 make check | smoke | full | layout | report | audit | clean
  flow/run_all.py          stage driver (argparse --stage ... --tier smoke|full); thin layer over sim/harness
  flow/gates.py            reads results/*/results.json + spec/gates.yaml -> results/gates.json (PASS/FAIL per criterion)
  flow/report.py           gates.json + results -> results/REPORT.md (every number templated, never typed)
  flow/iterate.py          bounded loop: failing metric -> knob (HANDOFF 10 table) -> re-size -> re-run, log iterations.jsonl
  spec/spec.yaml           the G2 numbers; spec/gates.yaml pass criteria + expected run counts; spec/decisions.yaml (fallback ladder, waivers)
  sizing/lvds_rx_sizing.py -> sizing/sizes.spice (header: sha256 of script + LUTs + spec) ; sizing_report.md (generated)
  netlist/                 hand-written topology, parameters only from sizes.spice; netlist/gen_lvs_ref.py -> numeric flat reference
  sim/tbN_*/               <tb>.spice + <tb>.json (harness specs), hooks.py
  layout/gen_lvds_rx.tcl   reads the device table from sizing (W/L/nf), labels EVERY net segment, writes GDS
  validate/                drc.sh (Magic + KLayout deck), lvs.sh (checks the "property errors" line too), pex.sh
  package/                 gds/lef/lib/spice/verilog + KNOWN_LIMITS.json
  results/                 committed: manifest.json, gates.json, REPORT.md, per-tb results.json/csv, small PNGs
```
`manifest.json` records: git commit and dirty flag, ngspice/magic/klayout versions, sha256 of sizes.spice, netlists, specs, LUT files, harness
version, the expected and actual run counts, wall times. `make full` = check -> sizing -> netlist lint -> all TB specs (harness, `--jobs 6`) -> MC -> gates -> report.
Guards: report.py prints PASS only if every run status is ok AND actual count equals the expected count in gates.yaml; sizes.spice with a stale hash
makes the netlist build refuse (mechanical enforcement of "never tune W by hand").

## Quality control instead of G4 / G5

1. Self-tests first (`make check`): harness 41 unit tests, `selftest_gmid` 296 checks, layout `run_all.sh` (proves the LVS gate fails on a wrong W).
2. Gate mutation tests: for each gate keep one deliberately broken variant that must FAIL it (input pair area /4 -> offset gate; swapped failsafe polarity ->
   TB7; one W x2 -> LVS property gate; unconnected guard ring -> DRC/LVS). A gate that cannot fail is not a gate.
3. LUT-versus-SPICE cross-check generated from TB1: per device gm/ID, ID, VDS-VDsat against the sizing script (limits from handoff 9.1), every VIC, every corner.
4. Sanity limits: Idd inside the budget band, no node outside -0.3..VDD+0.3, no model warning in the ngspice log, output toggle count = input toggle count,
   functional BER = 0 over the 127-bit PRBS sampled at mid-UI before the eye number is trusted.
5. Independent audit run (`make audit`, different agent, fresh work dir): clean rebuild from sizing, compare results.json to the builder's within tolerance
   (MC is seeded and was proven bit-identical in the harness), re-run DRC/LVS from the GDS alone, and check the commit/hash chain in manifest.json.
6. Criteria frozen BEFORE results exist: spec/gates.yaml is committed first; any later change needs a dated entry in decisions.yaml (waiver) which the
   report prints at the top.

## Schedule (counts) -- proxies, to be re-measured on the real netlist

Cost anchors (MEASURED): small DC/op run 0.13 s per job (2400 runs / 53 s on 6 jobs, harness log); 120-FET 1.5 us transient 4 s single-threaded;
one layout DRC+LVS round ~15 s. The handoff's "weeks" is human iteration time, not machine time.

| Item | Runs | s/run (assumed) | CPU min |
|---|---|---|---|
| TB1 op: full45 x 7 VIC x 3 VID | 945 | 0.2 | 3 |
| TB2 ac: full45 x 7 VIC | 315 | 0.5 | 3 |
| TB3 hysteresis (2 us triangle): full45 x 3 VIC | 135 | 4 | 9 |
| TB4 prop delay: full45 x 7 VIC x 2 VID | 630 | 0.4 | 4 |
| TB5 eye: 15 corners x 3 VIC x 2 VID x 2 rates | 180 | 8 | 24 |
| TB6-TB10 (cm step, supply noise, failsafe, power-down, input current, 3 lanes) | ~150 | 8 | 20 |
| MC offset by DC sweep (hysteresis off): N=1000 x 3 VIC x 5 corners | 15000 | 0.3 | 75 |
| MC full transient hysteresis: N=100 x 3 VIC x 2 corners | 600 | 4 | 40 |
| Total | ~18000 | | ~180 CPU min = ~30-40 min on 6 jobs |

Post-layout re-run (TB1,3,4,5,7,10 at tt + worst, extracted netlist 2-5x slower): ~100 runs, ~25 CPU min. Smoke tier (tt + worst5, no MC, MC N=30): about 3-5 min.
Dominant cost: Monte Carlo transients, not corners. Do not run hysteresis MC at N=200 x many corners: use the DC offset MC for sigma and the corner sweep for hysteresis.
