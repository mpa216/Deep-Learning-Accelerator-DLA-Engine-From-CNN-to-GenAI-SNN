# Hand-over for the layout phase (T9 onward), written 2026-11-14

Read this first if you are a new session continuing the LVDS receiver. It replaces `log/T5_state.md` (kept for history).

## Where everything is

- Git worktree: `/home/mpa216/Desktop/APIC_Return/.claude/worktrees/lvds-rx`, branch `lvds-rx` (named `worktree-lvds-rx` until 2026-11-14), 19 commits ahead
  of `main`, **local only (never pushed)**. Enter it with the EnterWorktree tool (`path`), do not create a new one.
- All work is under `analog/lvds_rx/`. Nothing outside it is touched, except a picture gallery the owner asked for in
  `Analog/lvds_rx_gallery/` of the main checkout (a copy of `docs/figures/`).
- The owner opens the files through a visible link in the main checkout: `LVDS/lvds_rx_work` points to this
  `analog/lvds_rx` folder (a symlink made on 2026-11-14 at the owner's request; untracked; do not remove it).
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

## Progress on 2026-11-14, second session (paused at the owner's request to save usage)

**Done and checked: steps 1 to 3.** Steps 4 and 5 are NOT started: no power-strap planner, no router and no
`layout/lane/` code exist yet. What follows under "Decided, not built" is a plan, not a result.

1. `make check` green (71 s). It rewrote `results/{gates.json,REPORT.md,manifest.json,env.json}` with the
   environment-only table; restored with `git checkout --` so the tracked full-tier record stays. Do the same next time.
2. Resistor leaves rebuilt at the frozen lengths, full checks pass: `t_res_rl` (2 series pieces of 9.113 um per
   resistor), `t_res_stage2` (8.862 um), `t_res` (18.395 um). Note for RL: the extraction rounds each piece to 9.11 um,
   so the layout sum is 18.22 um against 18.395 um in the schematic, 0.95 % short. Netgen's limit is 1 %. It passes,
   with little room.
3. Inverter `inv1_p` (W 3.7, L 0.28) is now drawn with one finger as in the sizing. Fix in `layout/lib/leaves.py`
   (`mos_row`, the `L < 0.36` block): when the contact margin is too small for the plain Metal1 trim, the contact tile
   is shortened by 0.14 um per end, so Magic places 7 contacts per bar instead of 8 (0.125 um of Metal1 past the end
   contact, bar end 0.37 um from the gate pad). `t_out_chain`: foundry deck 0 / 0, strict LVS clean (20 devices,
   9 nets), all negative controls detected. The re-fingering in `layout/leaf_tests/cells3.py` is removed.
   Full leaf regression after the change: see the last line of this section.

**Measured facts needed for the lane (probe scripts in `.scratch/t9/`, not in git).**
- `.scratch/t9/leaf_dims.py` prints the size and every port of each lane leaf without running Magic. Sizes (um):
  mpt 42.06 x 9.12, PMOS quad 86.54 x 8.92, mnt 23.20 x 6.62, NMOS quad 45.76 x 8.87, m3 sinks 44.48 x 6.62,
  m5 14.14 x 8.64 each, mt2 17.12 x 6.62, ms 10.06 x 7.98 each, loads2 23.98 x 6.12, mpu2 8.64 x 6.12 each,
  mp3 22.14 x 6.12, mn3 8.16 x 6.71, RL 21.21 x 16.00, RS 14.71 x 14.35, ESD cell 32.89 x 10.90, digital leaves
  7.4 to 10.4 wide and 5.6 to 9.1 tall.
- Gencell geometry at L 0.28: gate pad Metal1 0.34 x 0.23, S/D bar 0.23 wide, contact tile from Wf/2 - 0.065 inward,
  Metal1 bar 0.055 longer at each end, cuts 0.22 at 0.47 pitch (tech file `squares-grid 5 220 250`).
- The three ESD gencells are exactly mirror-symmetric about a vertical line (checked layer by layer with XOR):
  `ppolyf_u` 5 x 1.8 about x = 2.5 from its origin, `diode_pd2nw_03v3` 8 x 5 about x = 4.49 (box -1.12 to 10.10),
  `diode_nd2ps_03v3` 8 x 5 about x = 4.49 (box -0.31 to 9.29). So a mirrored ESD cell needs no Magic flip, only
  mirrored coordinates.
- Block power grid (`librelane/config_acv.yaml`, `pdn_cfg.tcl`, read only): Metal4 vertical stripes 5 um wide, VDD/VSS
  pair 1 um apart, pitch 75 um; macros connect Metal3 to Metal4. One lane (about 140 um) is sure of only one crossing
  per net, so the straps must run edge to edge and join across the lanes; the 600 um macro then gets 7.
- `check_via_arrays.py` is at `scripts/check_via_arrays.py` in the worktree root (tracked on `main`); in the container
  `/foss/designs/.claude/worktrees/lvds-rx/scripts/check_via_arrays.py <gds> <topcell>`. Run it as it is.

**Decided, not built (steps 4 and 5).**
- Floorplan, lane axis at x = 0, INP side (gp, fa, oa, sa, d2a) west, INN side east, signal flow top to bottom so the
  digital output sits farthest from the inputs. Rows from the top: ESD_P | mpt | ESD_N (mirrored); PMOS quad; m5a |
  m3 sinks | m5b; mnt | NMOS quad | mt2; ms1 | RL (terminals up) | ms2 | RS; mpu2a | loads2 | mpu2b | mp3 + mn3;
  digital chain in one row. Estimate 142 x 118 um against the 150 x 130 budget.
  `pair_dump` puts gate A at the east end: pass the INN side as A so that INP leaves west, as `spec/pins.yaml` has it.
- Power: eight Metal3 straps 2.5 um wide, alternating from VDD at the top to VSS at the bottom, each centred between
  two rows of a 0.7 um routing grid (it then uses exactly four grid rows). Metal2 spines at the two lane edges tie the
  straps of one rail together; without them the lane has four separate VDD pieces and LVS fails.
- Shared nets as edge-to-edge Metal3 trunks on grid rows: VBP near the top, VREF and VB2 between the PMOS quad and the
  sinks, VBN between the sinks and the NMOS quad, EN above the digital row.
- Routing: `Alloc` (one column per net, 12 um window) is not enough for a lane. Plan: a two-layer grid router in
  `layout/lib/`, Metal2 vertical and Metal3 horizontal at 0.7 um pitch, leaf boxes closed to routing, each port leaving
  on Metal3 at its own height, every shape still painted through `Block.rect` so shorts are refused before painting.
  The second net of each matched pair is routed along the mirror image of the first. On one column two via pads must
  be at least 0.68 um apart or overlap (same rule as `alloc.pad_ys`).
- LVS: a flat schematic built from `netlist/lvds_circuit.py` (`SUBCKTS`, `_line_lvs`) with the layout labelled by the
  reference's own net names (they are unique across the three sub-blocks), plus the dummy devices; and a second Netgen
  run of that flat netlist against `lvds_lane` in the frozen reference file.
- Extra checks beyond `check.run_cell`: via-array script, a bridge between two nets as a third negative control,
  antenna with the ESD diodes removed, and the wiring capacitance of INP against INN and of the two gate-side nets
  from a `pex_c` extraction.

Full leaf regression after the row-engine change: **ALL GREEN** (`run_all.py`, exit 0, 27 cells plus the allocator
self-test and the antenna pair, no failure line; log `.scratch/t9/run_all_full.log`, table
`layout/leaf_tests/results/summary.md`). The regenerated results are committed. Next session starts at step 4.

## Progress, third session (2026-11-14): work is cut into pieces, one local commit each

| Piece | What | State |
|---|---|---|
| A | `layout/lib/xform.py` (`MirrorX`: mirrored generation) + test `t_esd_mirror` | done, all checks pass, mirror XOR empty on 17 layers |
| B | `layout/lib/power.py` (step 4: straps, spines, ring ties, report) + test `t_power` | done, all checks pass |
| C | `layout/lib/route.py` (grid router) + test `t_route` (output chain in one row, wired only by the router) | done, all checks pass |
| D | `layout/lane/lane.py` placement (rows, straps, spines, ties, bias trunks) + `run_lane.py --stage place` | done, foundry deck 0 / 0 |
| E | lane routing, pins, flat LVS schematic; `run_lane.py` (full check of cell `lvds_lane`) | done, see below |
| F | lane-only checks (list below) | **next, not started** |
| G | leaf regression, design-log entry, T9 report, `make check`, then report to the owner and wait | open |

The three new tests are in `layout/leaf_tests/cells4.py` and are part of `run_all.py`. Quick loops without Magic, on the
host: `python3 .scratch/t9/try_cell.py <cell>` and `python3 .scratch/t9/try_lane.py place|rails|route` (floorplan and route
table, or the router's refusal). Key numbers of the last lane run: `python3 .scratch/t9/lane_numbers.py`.

### State of the lane after piece E (handed over on 2026-11-14)

`tools/cx python3 layout/lane/run_lane.py` builds cell `lvds_lane` and runs `check.run_cell`: about 30 s, verdict PASS.
Results in `layout/lane/results/` (`lvds_lane.gds`, `.png`, `.json`, `.spice`).

| Check | Result |
|---|---|
| Size | 142.8 x 125.3 um (budget 150 x 130) |
| KLayout foundry deck, variant D, DBU 0.001 | main 0, antenna 0 |
| Magic DRC | GDS read-back 0; `.mag` 352, all the allow-listed CO.6 on the L 0.28 contact bars |
| Strict Netgen LVS | clean, 74 devices and 29 nets on both sides; schematic = 47 reference devices + 46 dummies |
| Self-check | 305 MOS fingers, 12 resistors, 4 diodes, as requested |
| Finger read-back | 23 rows, 305 fingers, all in the generator's order |
| Negative controls | wrong W, cut wire (net oa), sliver in Magic and KLayout: all detected |
| Power planner | 7 straps, 7 Metal4 crossings each at macro length, highest 0.17 mA per um (S4), both rails tied by spines |
| Routing | 28 nets, 728 um Metal2, 1009 um Metal3, 201 vias |

Routed lengths of the matched pairs (Metal2 / Metal3, um): INP 12.87 / 22.92 and INN the same; gp 53.63 / 37.84,
gn 46.86 / 37.84; oa 47.29 / 38.16, ob 47.17 / 37.65; fa 21.89 / 42.28, fb 19.33 / 42.46; d2a 20.77 / 60.74,
d2b 21.85 / 64.00; sa 7.07 / 57.34, sb 8.47 / 18.12 (RS sits east of the axis, known and accepted).

**Not yet shown, do not claim it (piece F and G):**
1. The LVS above compares against the flat schematic that `lane.schematic()` builds from `netlist/lvds_circuit.py`
   and the device table. The second Netgen run of that flat netlist (without dummies) against `lvds_lane` in the frozen
   file `netlist/lvds_rx_lvs_ref.spice` is still to do; it closes "strict LVS against the reference file".
2. `scripts/check_via_arrays.py` (Vn.2b) has not been run on the lane.
3. Third negative control: a Metal3 bridge between two nets must make LVS fail.
4. Antenna with the ESD diodes removed (PLAN_V2 6.4 step 3).
5. Exit criterion "capacitance of the two input nets within 2 %": no extraction with capacitance has been run. INP and
   INN have identical wire lengths. gp has 6.77 um more Metal2 than gn: in both quads the INP gate strap is the bottom
   one and the INN strap the top one, so gp's column runs further down at each quad. If the `pex_c` sum differs by more
   than about 1 %, extend gn's column by an unconnected Metal2 stub of the same length (or move the difference into a
   Metal3 jog) rather than accepting it.
6. `Block.rect` now stores one database shape per wire instead of one per painted piece (piece D), and `route.py`,
   `power.py`, `xform.py` are new. **The full leaf regression has not been re-run since the `Block` change.** Run
   `layout/leaf_tests/run_all.py` (about 13 min, now 32 cells) and commit the results before closing T9.
7. `make check` (then restore the four `results/` files), DESIGN_LOG entry, `log/T9_report.md`, and the README of
   `layout/lib` (new modules) are not written.

Three things the router taught, worth keeping when the macro is assembled (T10):
- Two mos rows aligned to the same band edge have their gate straps at the same height (1.18 um from the edge). Gate
  ports of different nets that face each other across a gap then collide head-on: give one of them the other exit
  (`gate_exit="E"`), as done for mt2, m5b, ms2, mpu2b.
- Bars of neighbouring leaves less than 0.56 um apart in height cannot pass each other in the gap. The cascodes are
  therefore one grid pitch higher than the sink pair.
- A source bar enclosed by diode jogs on both sides (the VDD bar of `loads`) cannot be reached on Metal3; it reaches its
  ring through the Metal1 dummy ties of the row.

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
