# T8 part 1 report: leaf-generator library and routing infrastructure (2026-11-11)

Library: `layout/lib/` (README there). Tests: `layout/leaf_tests/` (`run_leaf_tests.py`, `summarize.py`, `results/`).
Run all (about 8 min, one process): `docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx python3 layout/leaf_tests/run_leaf_tests.py`
(`<cell>` names select cells, `--nok` skips the KLayout deck for a 5 s loop). Then `python3 layout/leaf_tests/summarize.py` prints one line per result.

## Result (all observed in the last full run, results/*.json)

| cell | what | fingers / devices after Netgen merge / nets | Magic DRC .mag / GDS | KLayout main / antenna (DBU 0.001) | strict LVS | finger read-back | negative controls |
|---|---|---|---|---|---|---|---|
| t_nmos_pair | mn1 (W 47.5, L 0.5, nf 10) ABBA x5 + 1 dummy per end, own p+ ring | 22 / 3 / 6 | 0 / 0 | 0 / 0 | clean | VSS INP INN INN INP ... INP VSS (22 of 22) | wrong W, cut wire, sliver (Magic and KLayout): all detected |
| t_pmos_pair | mp1 (W 105.6, L 0.4, nf 22) ABBA + dummies, n-well ring tied to the common source | 46 / 3 / 5 | 0 / 0 | 0 / 0 | clean | 46 of 46 | all detected |
| t_mirror | mbn : mnt : mt2 = 5 : 10 : 6 fingers (Wf 2.5, L 1), interdigitated, star source, diode jog | 23 / 5 / 4 | 0 / 0 | 0 / 0 | clean | `(dL)RTTRRUUTTTTUUTTUURRTT(dR)` matches the generator | all detected |
| t_tail_dump | tail mnt + pair mn1 with dump twins mnd beside it, TAIL routed, VREF by two columns + M3 channel | 52 / 6 / 8 | 0 / 0 | 0 / 0 | clean | 52 of 52 | all detected |
| t_stacked | cascode stack in one diffusion (m5 geometry twice) | 16 / 4 / 5 | 0 / 0 | 0 / 0 | clean | ok | all detected |
| t_res | rl (ppolyf_u_1k, r_width 2, r_length 19.664) with p+ ring | 1 resistor / 1 / 3 | 0 / 0 | 0 / 0 | clean | n/a | all detected |
| t_block | two rows: [tail mnt \| pair mn1] and PMOS mirror load mld : mp3 = 1 : 2, routed by `alloc` (TAIL, VSS, OA, OB columns), 6 pins | 48 / 8 / 8 | 0 / 0 | 0 / 0 | clean | 3 rows ok | all detected |
| t_block_short | same block, deliberate unregistered Metal3 bridge OB-TAIL | | | | LVS FAILS (as required) | | locator: `SHORT OB <-> TAIL`, unintended metal at 0.0 um from the injected bridge |
| t_block_open | same block, via2 of one OB column end omitted | | | | LVS FAILS (as required) | | locator: `OPEN OB in 2 pieces`, 0.78 um from the fault, fragment with the pin and the cut-off fragment (8 device terminals) listed |
| alloc_selftest | overlap with another net, spacing 0.10 um, same-net gap, 30 x 30 um plate, 70 um wire split to 23.3 um pieces, no legal column | | | | | | all rejected before painting |

Selfcheck (extract, then assert count / W / L / r_width / r_length equal the request) passed on every cell and gencell boxes equal the analytic boxes
(`GENBBOX`); the check is wired into `run_cell`, a mismatch sets `selfcheck ok = false` and the verdict to FAIL.
Strict LVS = exact line `Netlists match uniquely.`, no `property errors`, no `port errors`, no pin mismatch, equal device and net counts (the closing line "Circuits match uniquely" is ignored on purpose).
Observed: the dummy wrong-W control gives "match uniquely with property errors"; the open and short variants give net-count mismatches with real net names (`Net: OB.6`).

## Findings worth keeping (also in `layout/lib/README.md`)

1. **Same-text labels hide opens.** Magic joins disconnected nodes that carry the same label text: with every segment labelled `NET` the first "cut wire" control passed LVS. Segment labels are now `NET.k` (unique), only pins carry the plain name; the locator maps `NET.k` back to coordinates. This also gives the real net names the plan asked for (L2).
2. `port make` needs exactly one label under the point (generator drops other labels at pin positions).
3. A via cut is metal of both planes for Magic's connectivity: cutting only the M2 pad of a stack does not open it (negative control clears via1/via2 too).
4. Two via pads 0.40-0.68 um apart violate M2/M3 spacing even inside one net; a column pad within 0.28 um of the port's own end pad likewise. The allocator merges/shifts pads and keeps columns >= 0.5 um from port ends; the database also checks same-net gaps on M2/M3.
5. **MSLOT.1 is an erosion rule** (30 x 30 um square). Thin wires up to 48.8 um merged length (t_tail_dump Metal3) pass the foundry deck. The 29 um cap is enforced as bookkeeping (pieces and plates, `metal_cap` step reports the longest merged polygon) because Magic re-merges abutting pieces; it is not a split-with-jumper.
6. A finger whose two neighbours are other symbols cannot exist (source on both sides), so twins are laid out as (a b b a) flanks, not interleaved; an odd mirror device is placed single at one end (only one odd device allowed).
7. Row engine: one M3 bar per S/D net across the row (via1+via2 on every region) replaces the Metal2-track scheme of the toy, which cannot serve three mutually interleaved nets (S, D_A, D_B of a repeated ABBA).
8. Netgen output parsing: "Number of devices: N | Number of devices: N" lines give the counts; with parallel merge a 22-finger pair is 3 devices (A, B, dummies).
9. Resistor gencell size observed: w x (l + 1.22) um; its `l` is rounded in the extraction (19.664 -> 19.66), tolerance 0.0105 um in the selfcheck.

## What exists vs the task list

1. `device_table.py` done. 2. Generators: `pair_abba`, `mirror_interdig`, `pair_dump` + `tail_dump` (see decision below), `single`, `stacked`, `grouped_row`, `resistor`, `tap`, `guard_ring`, `via_stack`, `pin`. 3. `selfcheck.py` done. 4. `alloc.py`: columns, channel track, rejection before painting, cap, fault injection. 5. Labels + `label.py` locator (short, open, floating terminal) done. 6. `check.py` unified runner done.

Decisions (owner not asked): `tail_dump` = tail leaf + input pair with its dump twins in one row, TAIL routed (the dump twins in the circuit are parallel to the input devices, not to the tail); twins flank the pair as (abba) units and `pair_dump` has no extra dummies (all four strap/exit slots are taken, the twins are the edge fingers). `t_stacked` uses the m5 geometry twice (no sink shares Wf/L with m5). The two-row block uses table sizes: tail mnt, pair mn1, load mld : mp3.

## Open / not done

* Not in this part: `res_array` with dummies/snake, ESD cell, large diodes, nmoscap (T8 part 2). `resistor` is a single gencell with ring.
* Allocator has no power-strap planner (M3 straps at row boundaries / crossing >= 2 M4 stripes, L4) and no auto channel between rows other than the top channel; rails are routed as ordinary nets. Vn.2b via-array check not run (script location is a T9 item).
* Rows need Wf >= about 2.5 um for four S/D nets (bar pitch 0.64 um inside the contact bar); for tiny digital-size devices (Wf 1-2 um, nf 1-2) a stub-style single is not implemented, `mos_row` raises with the required height.
* At most one dummy per end; at most one odd-finger device per mirror; at most two distinct gate nets in a mirror row.
* PEX, post-layout simulation and LEF/abstract generation are later tasks. Layout was checked at the sizes in `layout/device_table.json` as of this run; a size change needs only a re-run.
* A stand-alone PMOS leaf has no p-substrate tap; DF.14_LV is satisfied by the n+ ring in this test but a lane needs the NMOS rings (they exist in every NMOS leaf).
