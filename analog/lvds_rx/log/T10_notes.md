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
| B | macro cell: lane x 3 + bias instances, gap fills, EN and output routes, pin stubs, FIXED_BBOX; DRC | next |
| C | macro LVS (hierarchical), negative controls, via arrays, antenna with / without ESD | open |
| D | PEX: C on all nets, RC on the input pair, bias and output nets | open |
| E | report, DESIGN_LOG, make layout, make check; report to the owner and wait | open |

## Bias block result (piece A2, `layout/bias/results/lvds_bias.json`, about 30 s)

53.2 x 142.1 um. KLayout main 0, antenna 0; Magic GDS read-back 0 (`.mag` 44, all allow-listed CO.6). Strict LVS clean,
28 devices and 11 nets; the flat schematic without dummies matches `lvds_bias` of the frozen reference file (17 devices,
11 nets, sha256 = FROZEN.md). Self-check 60 MOS fingers, 18 resistors; finger read-back 11 rows. Negative controls: wrong
W, cut wire (VBN), Metal3 bridge (EN-VB2 across 0.42 um), sliver: all detected. check_via_arrays.py 0. Routing 11 nets,
757 um Metal2, 467 um Metal3, 88 vias.

## Rules found

* A diode-connected mirror (MBN : MBS, MBP : MB2P) has its gate-to-drain jog at the gate strap's exit end: the other bars
  cannot leave past it. `mirror_interdig(gate_exit=)` (default W, unchanged for the lane's mn3) puts the strap and the jog
  on the east side (the cell edge), the bars leave west into the channel.

* `PowerPlan.ring_tie` next to a leaf drawn with `m1_ring_regions` (men_n): the tie's via1 pad 0.045 um from the leaf's
  Metal1 ring stub is a same-net Metal1 notch (M1.2a) that the shape database cannot see. `ring_tie` now skips such
  positions (and raises if none is left).
