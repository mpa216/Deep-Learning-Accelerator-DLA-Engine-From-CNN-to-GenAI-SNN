# T10 report: macro assembly and PEX (2026-11-14)

Everything below was observed in the runs of `layout/bias/run_bias.py` (cell `lvds_bias`) and `layout/macro/run_macro.py`
(cell `lvds_rx_x3`, with its PEX), and in one `make layout` that re-ran every leaf, the lane, the bias block and the macro
after the last library change of T10: every step passed (leaf regression `ALL GREEN`, summary generated 2026-11-14
12:00; lane PASS in 49 s; bias block PASS in 30 s; macro with its PEX PASS in 88 s).

`make check` afterwards: green (LUT self-test 296/296, 49 harness tests without failure, lint 0, toy layout ok, gates ENV
and SELFTEST 14/14); the four full-tier files it overwrites in `results/` were restored from git.

Run: `docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx make layout`
(about 16 min), or one cell with `... tools/cx python3 layout/<lane|bias|macro>/run_<lane|bias|macro>.py`.
Working notes with the piece-by-piece history: `log/T10_notes.md`.

## Floorplan (decided without the owner, inside every frozen spec)

`spec/spec.yaml` limits the core to 600 x 150 um plus a 15-25 um margin; `spec/pins.yaml` fixes the pin x positions from
the FIXED_BBOX lower-left (lanes centred at 100 / 300 / 500). The lanes are 142.8 um wide, so the two 57.2 um gaps between
them carry the lanes' straps and trunks, and a 600 um strip starting at x = 0 leaves 28.6 um at each end. PLAN_V2's "bias
in the gaps at the strip ends" does not fit (the bias resistors alone were a 53.7 um array).

Chosen: a 25 um margin, so the core spans x 25-625, and the bias block is the 53.2 um column east of lane 2 (x 571.4-624.6),
abutting it. FIXED_BBOX 650 x 192.1 um, core 600 x 142.1 um. The lanes sit at the top of the core (short RX pin stubs); the
bias block reaches 15 um below them.

```
 y 192.1 +------------------------------------------------------------------------------------------+  FIXED_BBOX
         |      RX0_P      RX0_N      RX1_P      RX1_N      RX2_P      RX2_N   (Metal3, top edge)   |
 y 167.1 |   +-----------+ fills +-----------+ fills +-----------+---------+                        |
         |   |  lane 0   |=======|  lane 1   |=======|  lane 2   |  bias   |                        |
         |   | (x 100)   |=======| (x 300)   |=======| (x 500)   |  block  |                        |
 y  42.2 |   +-----------+       +-----------+       +-----------+         |                        |
         |      outputs and EN in a channel under the lanes      +---------+  y 25 (core bottom)    |
         |      EN (x 100)  RX0_O (200)  RX1_O (300)  RX2_O (400)   (Metal2, bottom edge)           |
 y 0     +------------------------------------------------------------------------------------------+
         x 0        28.6                                        571.4    624.6                      650
```

## What exists

* `layout/bias/bias.py` + `run_bias.py`: the bias block. Its straps S2, S4, S6 (VSS), S7 and a short S1v (VDD) sit at the
  lane's strap rows and join lane 2 by abutment; its outputs VBN, VB2, VREF, VBP and the input EN leave at the lane's trunk
  rows on its west edge. The bias resistors are split into two arrays: RRB x 4 + RRF x 2 (27.7 um) and the Vref divider
  RRDT / RRDB interleaved (34.2 um, its ratio pattern kept). The PMOS mirror is MBP : MB2P only (the leaf test also held
  the lane's tail, which each lane has itself).
* `layout/macro/macro.py` + `run_macro.py`: the macro. Three instances of `lvds_lane`, one of `lvds_bias` (they stay
  subcells), Metal3 fills of the seven straps and five trunks across the two gaps, the RX pin stubs, the EN and output
  routes, FIXED_BBOX. Every top-level shape is checked against the subcells' own shapes before it is painted.
* `layout/lib/`: `Block.instance` / `Block.ghost` / `Block.paths` (hierarchy), `check.build(clean=)`,
  `check.magic_drc(flat=)`, `check.extract(flat=)`, `check.flat_base`, `strip_diodes` over every cell,
  `mirror_interdig(gate_exit=)`, `PowerPlan.ring_tie` skips positions next to Metal1 ring stubs.
* `results/layout/` (the plan's T10 output folder): `lvds_rx_x3.gds`, `.png`, `.lvs.out`, and the PEX netlists
  `{lvds_rx_x3, lvds_lane, lvds_bias}.{pex_c, pex_rc}.spice`.
* `Makefile`: `make layout` = every leaf, the lane, the bias block, the macro with its PEX.

## Result: PLAN_V2 6.4 steps 1 to 6 on the macro

| Step | Check | Observed |
|---|---|---|
| 1 | self-check | from the macro's own extraction: lane 305 MOS fingers, 12 resistors, 4 diodes; bias 60 fingers, 18 resistors (as requested) |
| 2 | Magic DRC | flattened `.mag`: 1100, all CO.6 on the L 0.28 contact bars (3 x 352 + 44, allow-listed); GDS read-back 0 |
| 3 | KLayout foundry deck, variant D, DBU 0.001 | main 0, antenna 0; antenna without the ESD diodes 0 (the 4 plates removed from the lane cell, i.e. in all three lanes) |
| 4 | `check_via_arrays.py` (Vn.2b) | 0 (Via1 1564, Via2 2535 cuts); planted dense array flagged |
| 5 | strict LVS, hierarchical | lvds_lane 74 devices / 29 nets, lvds_bias 28 / 11, lvds_rx_x3 4 instances / 16 nets: match uniquely, no property or port errors |
| 5 | against the frozen reference file | the same netlist without dummies against `lvds_rx_x3` of `netlist/lvds_rx_lvs_ref.spice` (sha256 = FROZEN.md): match uniquely |
| 5 | finger read-back | lane 23 rows / 305 fingers, bias 11 rows / 60 fingers, all in order |
| 5 | negative controls | wrong W (property errors), cut vbn fill between lanes 0 and 1 (17 vs 16 nets), Metal3 bridge EN-RX0_O across 0.42 um (15 vs 16 nets), DRC sliver (Magic and KLayout): all detected |
| 6 | PEX | C on all nets and RC on all nets, flat; see below |

The bias block alone (`layout/bias/results/lvds_bias.json`): 53.2 x 142.1 um, KLayout 0 / 0, Magic GDS 0, strict LVS 28
devices / 11 nets, matches `lvds_bias` of the reference file, finger read-back 11 rows, negative controls including a
Metal3 bridge (EN-VB2) detected, via arrays 0; 11 routed nets, 757 um Metal2, 467 um Metal3, 88 vias.

## PEX (`results/layout/`)

| Netlist | Devices | C | R | Extraction |
|---|---|---|---|---|
| `lvds_rx_x3.pex_c.spice` (flat) | 1029 + 12 diodes | 472 | 0 | 1.7 s |
| `lvds_rx_x3.pex_rc.spice` (flat) | 1029 + 12 diodes | 5711 | 10429 | 8.7 s |
| `lvds_lane.pex_c` / `.pex_rc` | 317 + 4 diodes | 145 / 1760 | 0 / 3125 | 0.9 / 1.7 s |
| `lvds_bias.pex_c` / `.pex_rc` | 78 | 79 / 449 | 0 / 967 | 0.6 / 0.7 s |

Every netlist has its subckt ports rewritten to the order of the reference (`VDD VSS INP INN EN VBN VBP VB2 VREF OUT` for
the lane, and so on): Magic writes its own order, and the testbenches connect by position. The macro is extracted from a
flattened copy because a hierarchical netlist cannot hold coupling capacitors between nodes of different subcells.

**Smoke test** (ngspice operating point, typical corner, 27 C, 3.3 V, harness header; lanes 0 and 2 at VID +100 mV, lane 1
at -100 mV, VIC 1.2 V, EN high):

| Netlist | RX0_O | RX1_O | RX2_O | IDD |
|---|---|---|---|---|
| pre-layout (`netlist/lvds_rx_core.spice`) | 3.3 V | 0 V | 3.3 V | 1.539 mA |
| `pex_c` | 3.3 V | 0 V | 3.3 V | -0.02 % |
| `pex_rc` | 3.3 V | 0 V | 3.3 V | -0.09 % |

**Extracted wiring capacitance in the macro:** RXk_P / RXk_N 6.09 / 6.09 fF in every lane (<= 0.12 %, the 26 um pin stubs
included); gp / gn 42.24 / 42.50 fF (0.60 %) in every lane, as in the lane alone; RX0_O / RX1_O / RX2_O 17.6 / 16.3 /
23.4 fF; EN 120 fF.

## Decisions (owner not asked)

1. Floorplan and the 25 um margin, above. The pin x positions of `spec/pins.yaml` are unchanged; the RX pins sit on the
   lane's 0.7 um grid, 0.3 um from the nominal x (RX0_P at 50.3, RX0_N at 149.7, ...).
2. The bias resistor array split in two (the divider keeps its interleaved pattern).
3. RC extraction on all nets instead of the plan's "input pair, bias and output nets only": the full RC netlist costs
   8.7 s to extract and 5.3 s for an operating point, so T11 can choose C or RC per bench.
4. The macro's deliverables go to `results/layout/` (as PLAN_V2 lists for T10); the check records stay next to the
   generators.
5. Outputs follow the pin order of `pins.yaml`: lane 2's output runs 150 um west under the lane to x = 400.

## Open (for the owner / T11)

* Post-layout re-simulation (T11) has not started: it needs the owner's go-ahead. The smoke test above only shows that
  the extracted netlists simulate and give the pre-layout DC levels.
* From T9: the stage-2 nets are less symmetric (d2a / d2b 7.2 %, sa / sb 52 % extracted wiring C); T11 shows whether it
  matters. Audit condition D-012: re-check the fast-hot-3.6 V corner after extraction.
* The RX pin positions are inferred (UNVERIFIED pad slots); a different pad pitch re-spins only the pin stubs.
* Extraction warnings: 10 in the lane cell and 10 in the bias block, all devices whose two terminals are one rail (the
  dummies, and the Vref capacitor, an nfet with source = drain = VSS by design).
* The secondary ESD cell stays UNQUALIFIED; the current-density limit of `power.py` (1 mA per um) is an assumption.
* Next task: T11, post-layout re-simulation and the second audit, after the owner's go-ahead.
