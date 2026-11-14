# T9 report: one lane in layout (2026-11-14)

Everything below was observed in one run of `layout/lane/run_lane.py` (cell `lvds_lane`, about 45 s, verdict PASS,
`layout/lane/results/lvds_lane.json`) and one full leaf regression (`layout/leaf_tests/run_all.py`), run after the last
library change of T9: last line `ALL GREEN` (allocator self-test, 28 leaf cells, the 2 fault cells that must fail LVS and be
located, the antenna pair with and without ESD: 32 cells; the cell checks add up to about 12 min; table
`layout/leaf_tests/results/summary.md`, generated 2026-11-14 10:39). `make check` afterwards: green (LUT self-test
296/296, 49 harness tests without failure, lint 0, toy layout ok, gates ENV and SELFTEST 14/14 pass); the four full-tier
files it overwrites in `results/` were restored from git.

Run: `docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx make layout`
(leaf regression, then the lane), or the lane alone with `... tools/cx python3 layout/lane/run_lane.py [--stage place|rails|route] [--nok]`.

## What exists

* `layout/lane/lane.py`: the lane generator. Seven rows of leaves (ESD and PMOS tail, PMOS input quad, sinks and
  cascodes, NMOS input quad with its tail and the stage-2 tail, RL + stage-2 pair + RS, stage-2 loads + EN pull-ups +
  stage 3, the digital chain), seven Metal3 power straps edge to edge, two Metal2 spines, five bias / enable trunks edge to edge, the
  router's wiring, pins. The INN-side ESD cell is the INP-side code mirrored (`MirrorX`). `schematic()` writes the flat
  LVS schematic (the reference's `lvds_lane` flattened by name, plus the layout's dummies; `dummies=False` without them).
* `layout/lane/run_lane.py`: build and check. `layout/lane/results/`: `lvds_lane.gds`, `.png`, `.spice`, `.json`, and
  `lane_place.*` from the placement stage.
* `layout/lib/` new modules: `xform.py` (mirrored generation), `power.py` (strap planner), `route.py` (grid router).
  Changed: `block.py` (one database shape per rectangle), `leaves.py` (one-finger inv1_p at Wf 3.7 and L 0.28;
  `pair_dump(odd_unit=)`), `check.py` (via arrays, bridge control, diode removal, antenna-only run, net capacitance).
  `layout/lib/README.md` lists the modules and the rules found in T9.
* `layout/leaf_tests/cells4.py`: `t_esd_mirror`, `t_power`, `t_route`, run by `run_all.py` with the other leaves.
* `Makefile`: `make layout` runs the leaf regression and the lane check (the macro joins in T10).
* **Location of `check_via_arrays.py`** (PLAN_V2 6.4 step 4): `scripts/check_via_arrays.py` on `main`, container path
  `/foss/designs/scripts/check_via_arrays.py`; the worktree has a byte-identical copy at the same relative path.
  Usage `python3 check_via_arrays.py <gds> <topcell>`, exit code 1 on any violation. `check.via_arrays` runs it.

## Result against the exit criteria (PLAN_V2 6.4 steps 1 to 5, and the input-net symmetry)

Size 142.8 x 125.3 um (budget 150 x 130).

| Step | Check | Observed |
|---|---|---|
| 1 | generator self-check | 305 MOS fingers, 12 resistors, 4 diodes extracted, equal to the request |
| 2 | Magic DRC | GDS read-back 0; `.mag` 352, all of them CO.6 on the L 0.28 contact bars (allow-listed: Magic is stricter than the foundry deck there) |
| 3 | KLayout foundry deck, variant D, DBU 0.001 | main 0, antenna 0 |
| 3 | antenna without the ESD diodes | 0 (copy with the 4 diode plates of 160 um2 in total, their 640 contacts and the diode marker removed; a Magic extraction of the copy finds no diode) |
| 4 | `check_via_arrays.py` (Vn.2b) | 0 violations: Via1 472 cuts, Via2 753 cuts, every cut its own cluster (no two closer than 0.36 um); a planted dense 4 x 4 Via2 array is flagged |
| 5 | strict LVS, layout | against the flat schematic with dummies: `Netlists match uniquely.`, 74 devices and 29 nets on both sides, no property or port errors |
| 5 | strict LVS, reference file | the flat schematic without dummies against `lvds_lane` of the frozen `netlist/lvds_rx_lvs_ref.spice` (its sha256 equals `sizing/FROZEN.md`): match uniquely, 47 devices, 29 nets; Netgen flattened lvds_esd2 x 2, lvds_pre, lvds_hyst, lvds_out |
| 5 | finger read-back | 23 rows, 305 fingers, all in the generator's order |
| 5 | negative controls | wrong W, cut wire (net oa), Metal3 bridge (d2a to d2b across a 0.42 um gap between two routed tracks; LVS 28 vs 29 nets), DRC sliver (Magic and KLayout): all detected |
| PEX | input nets, `pex_c` | INP / INN 4.399 / 4.405 fF (0.16 %); gp / gn 42.24 / 42.50 fF (0.60 %). Limit 2 % |

The PEX numbers are wiring capacitance (coupling and to substrate). Device capacitances (gates, diode junctions) are
equal on both sides by construction: strict LVS compares W, L, nf and diode area and perimeter.

## How the input symmetry was reached

The first measurement was gp 41.66 fF, gn 43.08 fF (3.4 %, over the limit). gn was the heavier net although gp has
6.77 um more Metal2, so the routing was not the cause. Both input quads have an odd number of 4-finger dump units (11 in
the PMOS quad, 5 in the NMOS quad). `pair_dump` put the extra unit on the right flank, and the gate strap that runs over
that flank to its exit is gn's in both quads: 4 fingers longer each time. The leaf tests show the size of the effect on
their own (+0.85 fF PMOS quad, +0.88 fF NMOS quad). The NMOS quad now takes its odd unit on the left
(`odd_unit="left"`), so the extra strap length is on gn in one quad and on gp in the other. Ports and routing did not
change; the result is 0.60 %.

## Other numbers (not T9 criteria; inputs for T10 and T11)

Extracted capacitance (`pex_c`, wiring only) of the other matched pairs:

| Pair | fF | Mismatch | Why |
|---|---|---|---|
| oa / ob | 27.56 / 27.64 | 0.26 % | |
| fa / fb | 48.05 / 47.29 | 1.6 % | |
| d2a / d2b (stage-2 outputs) | 24.04 / 22.36 | 7.2 % | different Metal3 lengths (60.7 / 64.0 um) and neighbours |
| sa / sb (stage-2 degeneration) | 8.00 / 4.68 | 52 % | RS sits east of the lane axis: sa has 57.3 um of Metal3, sb 18.1 um |
| rla_m1 / rlb_m1 (RL series midpoints) | 2.19 / 1.51 | 37 % | small absolute values |

Routed lengths (Metal2 / Metal3, um): INP 12.87 / 22.92 and INN the same; gp 53.63 / 37.84, gn 46.86 / 37.84;
oa 47.29 / 38.16, ob 47.17 / 37.65; fa 21.89 / 42.28, fb 19.33 / 42.46; d2a 20.77 / 60.74, d2b 21.85 / 64.00;
sa 7.07 / 57.34, sb 8.47 / 18.12. In total 28 routed nets, 728 um Metal2, 1009 um Metal3, 201 vias.

Power planner: 7 straps, each crossed by 7 of the chip's Metal4 stripes at the macro length (542.8 um); highest booked
DC current 0.42 mA on S4 (VSS), 0.17 mA per um against an **assumed** limit of 1 mA per um; both rails tied by spines.

## Decisions (owner not asked)

1. NMOS quad with its odd dump unit on the left (above). The PMOS quad keeps the default.
2. The VDD bar of the stage-2 loads is not hooked on Metal3: diode jogs of d2a and d2b enclose it. It reaches its ring
   through the two Metal1 dummy ties of the row (63 uA in total), and the ring reaches strap S1 through its ties.
3. RS stays east of the lane axis (sa / sb asymmetric, above). Flagged for the post-layout simulation instead of moved.
4. The bridge control picks its site automatically: the narrowest gap between two routed Metal3 wires of two signal
   nets that touches no third net.
5. `make layout` now runs the leaf regression and the lane check (the Makefile stub said T8 to T10 fill it).

## Open

* d2a / d2b (7.2 %) and sa / sb (52 %) capacitance asymmetries: check them in the post-layout simulation (T11:
  hysteresis symmetry, delay and duty cycle). If they matter, the fixes are placement (RS on the axis) or matching
  stubs, decided with the owner.
* RL: the extracted series length is 18.22 um against the schematic's 18.395 um, 0.95 % against Netgen's 1 % limit.
  It passes with a thin margin (known since T8).
* Magic prints 10 extraction warnings ("device missing 1 terminal; connecting remainder to node VSS / VDD"). They are
  exactly the 10 dummies whose two terminals are one rail (6 MOS, 4 resistor columns), one warning per dummy: expected.
* The secondary ESD cell stays **UNQUALIFIED** (no HBM, CDM or latch-up data, no ESD claim).
* The current-density limit of 1 mA per um in `power.py` is an assumption, not a foundry number.
* Next task: T10, macro assembly (three lanes, bias, Vref divider, EN, pin row), after the owner's go-ahead.
