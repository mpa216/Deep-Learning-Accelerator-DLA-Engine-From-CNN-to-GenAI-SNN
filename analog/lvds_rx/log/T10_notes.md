# T10 working notes: macro assembly (started 2026-11-14, owner's go-ahead "go ahead with T10")

Solo, in small pieces with one local commit each (as in T9). Report and wait for the owner after the macro passes.

## Floorplan decision (owner not asked; inside every frozen spec)

* `spec/spec.yaml` layout: core at most 600 x 150 um plus a 15-25 um margin (FIXED_BBOX). `spec/pins.yaml`: pin x from
  the FIXED_BBOX lower-left; lanes centred at 100 / 300 / 500 (RXk_P / RXk_N at 50 + 200k / 150 + 200k on the top
  edge, EN at 100 and RX0_O / RX1_O / RX2_O at 200 / 300 / 400 on the core side, Metal2).
* Lanes are 142.8 um wide: they span 28.6-171.4, 228.6-371.4, 428.6-571.4. The two 57.2 um gaps carry the lanes'
  straps and trunks (power and bias continuity, and the planner's >= 2 Metal4 crossings per strap). The bias block
  (resistor array 53.7 um wide, Vref cap 30.6 x 24.1 um, two mirrors) cannot sit in a gap, and the strip ends of a
  600 um strip starting at 0 are 28.6 um. PLAN_V2's "bias in the gaps at the strip ends" does not fit.
* Chosen: margin 25 um, FIXED_BBOX 650 x (core + 50); core x 25-625. The bias block is the column x 571.4-624.6
  (53.2 um), abutting lane 2. Its straps S2, S4, S6 (VSS), S7 and a short S1v (VDD) sit at the lane's strap rows and
  join lane 2 by abutment; its outputs leave at the lane's trunk rows on its west edge. B0 (VSS) lies 15 um below the
  lane's bottom, so the core is about 142 um tall (lanes at the top of the core, short RX pin stubs).
* The single 18-column bias resistor array of the leaf tests (53.7 um) is split: RRB x4 + RRF x2 (27.7 x 30.7) and the
  Vref divider RRDT / RRDB interleaved (34.2 x 30.7). The divider keeps its common-centroid pattern; RRB and RRF only
  set absolute currents.
* The PMOS bias mirror of the leaf test `t_mirror_p` also held the lane's tail `mpt`; in the macro each lane has its
  own `mpt`, so the bias block's mirror is MBP : MB2P only (31.4 um).

## Pieces

| Piece | What | State |
|---|---|---|
| A1 | `layout/bias/bias.py` placement (leaves, straps, VSS spine, ring ties, trunk pins) + `run_bias.py --stage place` | done: Magic 0 (GDS), KLayout 0 / 0 |
| A2 | bias routing, pins, flat schematic, full check (LVS against lvds_bias + reference file, negative controls, via arrays) | done: PASS, see below |
| B | macro cell: lane x 3 + bias instances, gap fills, EN and output routes, pin stubs, FIXED_BBOX; DRC | done, see below |
| C | macro LVS (hierarchical), negative controls, antenna without ESD | done, see below |
| D | PEX: C on all nets, RC on the input pair, bias and output nets | next |
| E | report, DESIGN_LOG, make layout, make check; report to the owner and wait | open |

## Bias block result (piece A2, `layout/bias/results/lvds_bias.json`, about 30 s)

53.2 x 142.1 um. KLayout main 0, antenna 0; Magic GDS read-back 0 (`.mag` 44, all allow-listed CO.6). Strict LVS clean,
28 devices and 11 nets; the flat schematic without dummies matches `lvds_bias` of the frozen reference file (17 devices,
11 nets, sha256 = FROZEN.md). Self-check 60 MOS fingers, 18 resistors; finger read-back 11 rows. Negative controls: wrong
W, cut wire (VBN), Metal3 bridge (EN-VB2 across 0.42 um), sliver: all detected. check_via_arrays.py 0. Routing 11 nets,
757 um Metal2, 467 um Metal3, 88 vias.

## Macro after piece B (`layout/macro/run_macro.py --stage drc`, about 40 s)

Cell `lvds_rx_x3`: instances lvds_lane at (100, 42.15), (300, 42.15), (500, 42.15) and lvds_bias at (571.4, 42.15);
FIXED_BBOX (0, 0)-(650, 192.1), written by Magic into the GDS as the boundary on layer 0/0; core (25, 25)-(625, 167.1) =
600 x 142.1 um. KLayout main 0, antenna 0; Magic DRC on the flattened .mag 1100 (all CO.6 = 3 x 352 + 44, allow-listed),
GDS read-back 0; check_via_arrays.py 0 (Via1 1564, Via2 2535 cuts). Pins: RXk_P / RXk_N Metal3 at x 50.3 + 200k / 149.7 +
200k on the top edge (0.3 um from pins.yaml: the lane grid), EN and RXk_O Metal2 at x 100 / 200 / 300 / 400 on the bottom
edge. Lane 2's output runs 150 um west under the lane to x = 400 (pins.yaml order).

## Macro after piece C (`layout/macro/run_macro.py`, about 65 s, verdict PASS)

| Step | Result |
|---|---|
| strict LVS, hierarchical | Netgen matched lvds_lane (74 devices, 29 nets), lvds_bias (28, 11), lvds_rx_x3 (4 instances, 16 nets) uniquely, no property or port errors |
| reference file | the same netlist without dummies against lvds_rx_x3 of netlist/lvds_rx_lvs_ref.spice (sha256 = FROZEN.md): match uniquely; Netgen flattened the lane's four sub-blocks |
| subcells in the macro's extraction | lane 305 fingers / 12 resistors / 4 diodes, 23 rows read back; bias 60 fingers / 18 resistors, 11 rows read back |
| negative controls | wrong W (property errors), cut vbn fill between lanes 0 and 1 (17 vs 16 nets), Metal3 bridge EN-RX0_O across 0.42 um (15 vs 16 nets), sliver (Magic 1, KLayout M1.1): all detected |
| antenna without ESD | the 4 plates (160 um2, 640 contacts, diode_mk) removed from the lane cell (all three instances): no diode extracted, antenna 0 |

The extraction warns 10 times in lvds_lane and 10 times in lvds_bias ("device missing 1 terminal": dummies with both
terminals on one rail, explained for the lane in log/T9_report.md).

## Rules found

* Magic DRC of a hierarchical cell: `drc listall count` counts a subcell's errors in the subcell and again per instance in
  the parent, `drc listall why` lists boxes on yet another basis; `check.magic_drc(flat=True)` checks a flattened copy,
  where every error is counted once with its rule.
* `getcell CELL child 0 0 parent Xum Yum` puts the child's origin at (X, Y); a plain `getcell` aligns bounding boxes.
* FIXED_BBOX in lambda (0.05 um) is written to the GDS as a boundary shape on layer 0/0 (the top bbox then starts at 0, 0).

* A diode-connected mirror (MBN : MBS, MBP : MB2P) has its gate-to-drain jog at the gate strap's exit end: the other bars
  cannot leave past it. `mirror_interdig(gate_exit=)` (default W, unchanged for the lane's mn3) puts the strap and the jog
  on the east side (the cell edge), the bars leave west into the channel.

* `PowerPlan.ring_tie` next to a leaf drawn with `m1_ring_regions` (men_n): the tie's via1 pad 0.045 um from the leaf's
  Metal1 ring stub is a same-net Metal1 notch (M1.2a) that the shape database cannot see. `ring_tie` now skips such
  positions (and raises if none is left).
