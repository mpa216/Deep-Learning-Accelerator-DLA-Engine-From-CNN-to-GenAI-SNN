# Hand-over for the layout phase (T9 onward), written 2026-11-14

Read this first if you are a new session continuing the LVDS receiver. It replaces `log/T5_state.md` (kept for history).

## Where everything is

- Git worktree: `/home/mpa216/Desktop/APIC_Return/.claude/worktrees/lvds-rx`, branch `lvds-rx` (named `worktree-lvds-rx` until 2026-11-14), 19 commits ahead
  of `main`, **local only (never pushed)**. Enter it with the EnterWorktree tool (`path`), do not create a new one.
- All work is under `analog/lvds_rx/`. Nothing outside it is touched, except a picture gallery the owner asked for in
  `Analog/lvds_rx_gallery/` of the main checkout (a copy of `docs/figures/`).
- Not in git (lives only in this worktree's folder): `luts/` (4.3 GB, rebuild with `lut_regen/regen_all.sh`), simulation
  run directories under `sim/*/results/*/work`, `.scratch/`. Deleting the worktree loses these; committed work survives
  on the branch.
- Tools run in the docker container: `docker start apic_headless`, then
  `docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx <command>`.

## State

Pre-layout is finished and frozen. Read, in this order:
1. `DESIGN_LOG.md`, last entry (2026-11-14).
2. `results/AUDIT_1.md` (findings, accepted decisions, the condition on D-012).
3. `sizing/FROZEN.md` (hashes; rules for changing a frozen file).
4. `PLAN_V2.md` section 6 (layout method and checks) and rows T9 to T13 of section 8.
5. `layout/lib/LANE_RECIPE.md`, `log/T8a_report.md`, `log/T8b_report.md` (the layout library and its open points).

## First steps of T9 (one lane)

1. `tools/cx make check` (about 1.5 min) must be green.
2. Regenerate the leaves that are out of date against `layout/device_table.json`: load resistors RL (18.395 um, were
   19.664) and comparator resistors Rs (8.862 um, were 9.315). Then `layout/leaf_tests/run_all.py`: all 29 cells green.
3. Fix the output-inverter leaf drawn with nf 2 where the sizing has nf 1 (T8 note).
4. Add the power-strap planner that the library lacks.
5. Build the lane generator in `layout/lane/`. Exit criteria (PLAN_V2 T9): steps 1 to 5 of section 6.4 pass for the
   lane (KLayout foundry deck 0 violations, strict Netgen LVS against `netlist/lvds_rx_lvs_ref.spice`, finger-order
   read-back, negative controls fail), and the extracted capacitance of the two input nets matches within 2 %.

## Rules the owner set

- Report and wait for a go-ahead before each major phase (lane, macro, post-layout simulation, packaging).
- Low usage matters more than speed: one agent at a time at most (Sonnet 5.5, high), or none. Heavy machine jobs run
  detached (`tools/run_only.sh <gates> 4 <tag> [full|smoke]`, ends with `EXIT <code>` in `results/<tag>_run.log`).
- Simulations use 4 parallel jobs (chosen after the 2026-11-12 PC crash; the laptop has 4 physical cores).
- Commit as the owner only (mpa216), no Co-Authored-By line. Never push without an explicit yes.
- Never modify `main`, `info.yaml`, `lvs_config.json`, `gds/`, `verilog/`, `librelane/`, `rtl/dla_*`, `signoff/A56/`.
  `Analog/` (the gm/ID book kit) and `/foss/pdks` are read-only. `layout/magic_flow/` must not be modified.
- Chip integration (plan tasks P7/P8) stays owner-gated and is not part of this work.

## Things that bit earlier sessions

- The shell guard refuses complex one-liners (heredocs inside `docker exec`, several statements with `sed`/python):
  write a script file with the Write tool and run it.
- `flow/run_all.py --stage gates` prints PASS for results from an older sizing. Run `tools/audit_hashes.py --tier full`
  before trusting a gate table.
- `make check` overwrites `results/gates.json` with an environment-only table; the full-tier record is kept in
  `results/full_2026-11-14/`.
- A slow voltage ramp through the comparator's trip point makes ngspice stall in transient; use a DC sweep up and down.
- Disk: 19 GB free on 2026-11-14.
