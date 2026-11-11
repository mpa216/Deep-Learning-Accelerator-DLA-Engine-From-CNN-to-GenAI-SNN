# T8 part 2 report: resistor arrays, secondary ESD cell, remaining leaves, lane recipe (2026-11-11)

Everything below was observed in ONE full run of `run_all.py` (29 cells + antenna pair, about 12 min, last line `ALL GREEN`, log `.scratch/t8/full_run5.log`, table `layout/leaf_tests/results/summary.md`).

## What exists

* `layout/lib/passives.py` (new): `plan_series`, `seg_len`, `res_array`, `res_schem` (matched poly-resistor columns), `esd_cell` (**UNQUALIFIED**), `nfet_cap`.
* `layout/lib/leaves.py` (extended): mirrors with two odd devices, `tail_dump(rail_pair=)`, `single(gate_exit=)`, `mos_row(m1_ring_regions=)`, L < 0.36 fixes. `block.py` (`expect_dio`, `expect_cap`), `selfcheck.py` (diode area / perimeter, caps), `check.py` (extract from .mag, allow-listed Magic rules, resistor read-back, cut position / kind), `alloc.py` (pairwise spacing in `_legal`, pin height) extended. Part 1 code was extended, not rewritten.
* `layout/leaf_tests/`: `run_all.py` (one command, all leaves + antenna pair + `summarize2.py` -> `results/summary.md`), `cells2.py` (resistors, ESD, cap), `cells3.py` (13 transistor / digital cells), `ant_tests.py`, `results/` (GDS, PNG, JSON, summary.md, `ant_esd_comparison.json`).
* `layout/lib/LANE_RECIPE.md` (floorplan proposal), `layout/lib/README.md` (new rules, ESD UNQUALIFIED section).

Run: `docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx python3 layout/leaf_tests/run_all.py [cell ...] [--nok]`.

## Result (all cells: KLayout deck variant D main 0 / antenna 0 at DBU 0.001, strict Netgen LVS clean, self-check, read-back, negative controls detected)

| item | cell | observed |
|---|---|---|
| 1 res_array | `t_res_rl` | RLa / RLb ABBA, 2 series segments of 9.748 um each (R = 10 045 ohm as in the table), dummy at both ends: 6 resistors extracted, bbox 21.2 x 16.6; read-back `d, rla0, rlb0, rlb1, rla1, d` ok |
| | `t_res_stage2` | RS1 / RS2 (single 9.315 um segments), bbox 14.7 x 14.8, read-back ok |
| | `t_res_bias` | rb (4 x 22.265), rf (2 x 23.072), divider rdt / rdb interleaved (4 x 21.007 / 4 x 19.261), 16 resistors in one row, bbox 53.7 x 35.6; read-back of all 16 columns ok |
| 2 esd_cell | `t_esd` | ppolyf_u 5 x 1.8 in n-well + diode_pd2nw 8 x 5 + diode_nd2ps 8 x 5 (own p+ ring): LVS clean against `lvds_esd2` (1 resistor, 2 diodes, area 40p pj 26u read back), bbox 32.6 x 10.1 |
| | antenna | `ant_esd_comparison.json`: 700 um Metal3 run on a 1 um2 gate: **without ESD antenna 1 (ANT.16_i_ANT.4), with ESD 0**, main DRC 0 / 0 |
| 3 nmoscap | `t_cap` | cap_vref as `nfet_03v3` w 20 l 25.13 with S = D = VSS (see Decision 1), bbox 30.7 x 24.1, KLayout 0 / 0, LVS clean |
| | `t_en_inv`, `t_out_chain` | ENB inverter (men_n Wf 1.0) and NAND2 + INV1..3 (19 devices, 61.5 x 22.3), KLayout 0 / 0, LVS clean (19 dev, 19 nets) |
| 4 groups | `t_pmos_tail_dump` | mpt tail + PMOS quad, 112 fingers, read-back `abba x5 \| ABBA x11 \| abba x6`, 131.7 x 10.3 |
| | `t_sinks`, `t_cascodes`, `t_stage2_pair`, `t_bias_n`, `t_mirror_p`, `t_loads2`, `t_stage3p`, `t_stage3n`, `t_singles_n`, `t_singles_p` | all PASS; e.g. `t_loads2` row `(dL)caabbccddddccbbaad(dR)` (mld a b, mlc c d), `t_bias_n` `(dL)RRRSSSSRRS(dR)`, `t_stage3n` `(dL)DC(dR)` |
| coverage | summary.md | every one of the 35 transistors, 7 resistors, 2 diodes and the cap has a leaf ("All stems covered") |
| 5 recipe | `LANE_RECIPE.md` | lane about 140 x 100 um (14 000 um2 of 19 500), leaf sum 6 150 um2 (x 1.35 = 8 300); five rows; M2 columns and M3 channels listed |

Negative controls on every cell: wrong W / r_length / c_length, cut Metal3 wire at a position that really separates the net, Metal1 sliver (Magic and KLayout) all detected. The two fault cells (`t_block_short`, `t_block_open`) still fail LVS and are located.

## Decisions (owner not asked)

1. **cap_nmos_03v3 is drawn as an nfet with source = drain = bulk**, not with `nmoscap_3p3`. The PDK gencell is the accumulation varactor: it extracts as `cap_nmos_03v3_b`, it DISAPPEARS from a Magic GDS extraction (166/5 marker not mapped; .mag extraction works) and its GDS fails KLayout PL.5a_LV / PL.5b_LV (2 + 2). The nfet cap is what the foundry note in the Magic tech file describes. **The LVS reference line for XCVREF must become `nfet_03v3 w=20u l=25.13u` (D = S = VSS, G = VREF) for layout LVS; the simulation model can stay cap_nmos_03v3.** (`_b` would be better at low bias: 3.2 fF/um2 at 0 V instead of 0.02; the sizing stream may want it, but then the layout needs a new generator that also extracts from GDS.)
2. **Series snake of resistors**: Netgen merges series resistors and compares the sum of r_length with the schematic's single device (cutoff 1 %), verified on a test. Segment length is chosen to keep the RESISTANCE equal to the table (each segment carries its own 85 ohm of ends), so the summed length is 0.85 % (RL), 0.56 % (rb), 0.36 % (rf), 0.6 % (rdt), 0.65 % (rdb) below the table length: LVS against the UNMODIFIED reference stays clean. RL is close to the cutoff: if RL gets shorter than 16.8 um, use k = 1.
3. **ms (nf 3) and m5 are not ABBA**: ABBA needs a common source; ms has source degeneration (SA / SB), m5 distinct fold nodes. Both are two identical rows side by side (own rings). The input quad (common tail) is ABBA with twins as (abba) flanks as in part 1.
4. **inv1_p (W 3.7, nf 1) is laid out with nf 2** (Wf 1.85, W unchanged, LVS unchanged): at L = 0.28 the contact margin of Wf 3.7 is 0.095 um, the pad-corner fix needs 0.105 (`mos_row` raises with that message). The sizing script's nf for the parasitic ad / as differs from the layout for this one device.
5. **Magic's CO.6 is allow-listed for the three L = 0.28 cells** (`t_stage3n`, `t_en_inv`, `t_out_chain`; 320 flags on the chain): KLayout CO.6a / CO.6b are 0 and the KLayout deck is the sign-off.
6. Digital cells are single rows with their own rings wired by alloc, not standard-cell rows with shared diffusion rails (the widths per device differ, no common finger width exists without changing W). Shared-rail rows need a netlist with common finger widths.

## Open

* No lane-level ring merging, no rotated resistor array, no mirrored ESD placement (recipe says how). Strip arrangement of the bias block (about 75 x 60) is a T9 / T10 decision.
* `check_via_arrays.py` (Vn.2b) not run (T9 item); PEX / post-layout simulation not started.
* The RL pair has only 2 segments per device (ABBA of 4 columns); a 2-D / 4-segment arrangement is possible if the sizing needs better matching. rdt : rdb is 1.09 (not an integer ratio): matching of the divider would improve with sizes that are multiples of one unit segment.
* ESD cell: UNQUALIFIED (no HBM / CDM, no latch-up deck, no rating claimed). Only DRC / LVS / antenna were verified.
* Magic's GDS read does not map the 166/5 MOSCAP marker (finding, matters if a varactor is ever used).
* Ask the organizers (bundled G6 questions): whether chip fill respects RES_MK (DPF.8 19.7 um, DCF.8a 3.5 um). The resistor arrays here keep 0.45 um between RES_MK markers (HRES.1 0.4).
