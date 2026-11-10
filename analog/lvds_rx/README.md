# LVDS receiver macro (`lvds_rx_x3`) for GF180MCU

A learning project: a three-lane LVDS receiver hard macro in gf180mcuD 3.3 V devices, designed with the
gm/ID lookup-table method (Jespers & Murmann, reference folder `Analog/` in the main checkout).
Scope is the macro only. Nothing here touches `main`, `info.yaml`, the padframe or the signed-off A56 chip.

## Where to start reading

| File | What it is |
|---|---|
| `DESIGN_LOG.md` | Dated, plain-language log of what was done and what the numbers mean. Read this first. |
| `PLAN_V2.md` | The plan being executed (spec, architecture, verification, layout, task list T0-T13). |
| `HANDOFF_FOR_CLAUDE.md`, `GUIDE_FOR_YOU.md` | The original plan (2026-10-06). PLAN_V2 supersedes it where they differ. |
| `docs/ENV_REPORT.md` | Verified PDK and tool facts, with a ready-to-paste simulation header. |
| `docs/GMID_METHOD_NOTES.md` | Working notes on the gm/ID method with book section and page citations. |
| `log/` | One note per agent task (builders, independent verifiers, plan reviews) and their structured results. |

## Directory layout

```
Makefile        single entry point: check | smoke | full | report | mutants | lint | layout (stub) | audit (stub) | clean
spec/           FROZEN criteria: spec.yaml, gates.yaml, pins.yaml, paths.yaml, FREEZE.json; decisions.yaml = fallback-ladder + waiver log
flow/           run_all.py (stage driver), gates.py (results -> results/gates.json), report.py (-> results/REPORT.md),
                lint.py, mutants.py (gate mutation tests), envcheck.py (-> results/env.json), iterate.py (iteration cap logger)
results/        generated: env.json, gates.json, REPORT.md, manifest.json, mutants.json
tools/cx        run any command inside the apic_headless container with the full EDA environment
sizing/         gm/ID wrapper (gmid_gf180.py) and, later, the sizing script: the single source of truth for every W/L
luts/           gm/ID lookup tables (git-ignored, regenerate with lut_regen/regen_all.sh)
lut_regen/      scripts that regenerate and validate the lookup tables
netlist/        SPICE subcircuits (pad model, input network; later the receiver itself)
sim/harness/    corner / Monte Carlo / eye-diagram automation; sim/tb*/ one directory per testbench
layout/         scripted Magic layout flow (magic_flow/ is the proven pathfinder)
xschem/         schematic export experiments
```

## Running things

All EDA tools live in the docker container `apic_headless`. From the host:

```
docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx <command> [args]
```

Everything is driven by `make`: `... tools/cx make check` (about 1.5 min, must be green), `make smoke`, `make full`, `make mutants`.
The wrapper starts in `analog/lvds_rx`, so paths are relative to it, for example
`... tools/cx python3 sizing/selftest_gmid.py` or `... tools/cx bash layout/magic_flow/scripts/run_all.sh`.
If the container is stopped: `docker start apic_headless`.
