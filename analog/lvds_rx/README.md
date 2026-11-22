# LVDS receiver macro (`lvds_rx_x3`) for GF180MCU

A learning project: a three-lane LVDS receiver hard macro in gf180mcuD 3.3 V devices, designed with the
gm/ID lookup-table method (Jespers & Murmann, reference folder `Analog/` in the main checkout).
Scope is the macro only. Nothing here touches `main`, `info.yaml`, the padframe or the signed-off A56 chip.

## Where to start reading

| File | What it is |
|---|---|
| `LVDS_RX_DESIGN_RECORD.md` | The complete design record (2026-11-22): what the macro is, requirements against results, how it was made, the sizing iterations, every bug and error, decisions, limits, lessons. Read this first. |
| `DESIGN_LOG.md` | Dated, plain-language log of what was done and what the numbers mean, task by task. |
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
sizing/         gm/ID wrapper (gmid_gf180.py); lvds_rx_sizing.py = the single source of truth for every W/L/nf/R -> sizes.spice,
                sizing_report.md (tables, corner evaluation, offset budget, current tally, asserts), ../layout/device_table.json, ../results/sizing.json
luts/           gm/ID lookup tables (git-ignored, regenerate with lut_regen/regen_all.sh)
lut_regen/      scripts that regenerate and validate the lookup tables
netlist/        SPICE: pad model, input network; the receiver = lvds_circuit.py (connectivity, written once) -> gen_core.py -> lvds_rx_core.spice
                (simulation, parameters from sizes.spice) and gen_lvs_ref.py -> lvds_rx_lvs_ref{,_flat}.spice (LVS reference, gf180mcuD names)
sim/harness/    corner / Monte Carlo / eye-diagram automation; sim/tb*/ one directory per testbench; sim/t2_op/ = first .op of the sized lane; sim/tb1_op (operating point + LUT-vs-SPICE) and sim/tb2_ac (AC) are the first gated benches (make smoke runs them, make shakedown the PMOS-only S1 run)
                (supply-ramp DC, build-flag run; read its results/op_table.md)
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
