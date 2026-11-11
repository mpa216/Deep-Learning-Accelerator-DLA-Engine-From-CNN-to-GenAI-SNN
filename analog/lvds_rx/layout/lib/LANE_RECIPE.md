# LANE_RECIPE -- one lane of lvds_rx_x3, built from the T8 leaves (2026-11-11)

For the agent who builds the lane (T9).  Everything below is derived from the MEASURED leaf boxes in `layout/leaf_tests/results/summary.md`
(sizes at the device table of 2026-11-11; `run_all.py` re-measures them after a sizing change) and from the circuit in `netlist/lvds_rx_lvs_ref.spice`
(`lvds_pre`, `lvds_hyst`, `lvds_out`, `lvds_esd2`).  Numbers are um unless stated.  The routing factor and the channel heights are ASSUMPTIONS until the first
real lane exists.

## 1. Leaf inventory with measured sizes (width x height of the outer box incl. ring and well)

| leaf (test cell) | what | size |
|---|---|---|
| `t_pmos_tail_dump` | mpt tail + PMOS quad: mp1 x2 + dump twins mpd x2 (88 fingers, L 0.4), pair n-well = TP | 131.7 x 10.3 |
| `t_tail_dump` | mnt tail + NMOS quad mn1 x2 + mnd x2 (L 0.5) | 72.0 x 10.0 |
| `t_sinks` | m3 x2 fold sinks ABBA, 12 fingers each | 44.5 x 7.7 |
| `t_cascodes` | m5 x2 (two identical rows, sources FA / FB differ) | 31.3 x 8.6 |
| `t_mirror` (mt2 share) | mbn : mnt : mt2 = 5 : 10 : 6, the mt2 part alone is about 17 x 6.6 (estimate: 6 + 2 dummy fingers) | 39.9 x 6.6 (whole) |
| `t_res_rl` | RLa / RLb, ABBA of 2 series segments of 9.75 um, dummies | 20.0 x 16.6 |
| `t_res_stage2` | RS1 / RS2 (single segments 9.3 um) | 14.0 x 14.8 |
| `t_stage2_pair` | ms x2 (two rows, sources SA / SB differ) | 23.1 x 8.0 |
| `t_loads2` | mld x2 + mlc x2 interdigitated (4 + 4 + 5 + 5 fingers) | 24.1 x 6.2 |
| `t_stage3p` | mp3 x2 ABBA, 8 fingers each | 22.2 x 6.2 |
| `t_stage3n` | mn3 diode + copy (two single fingers, L 0.28) | 8.2 x 6.7 |
| `t_singles_p` (mpu2 x2 share) | the two stage-2 parking PMOS (Wf 2, L 0.5) are about 2 x 12 each; the cell holds 4 devices | 50.8 x 9.2 (whole) |
| `t_out_chain` | NAND2 + INV1 + INV2 + INV3 (two rows, N below P) | 60.7 x 22.3 |
| `t_esd` x2 | one per input: ppolyf_u 5 x 1.8, pd2nw + nd2ps 8 x 5 | 32.6 x 10.1 each |

## 2. Floorplan proposal (rows from the bottom; VSS side down, VDD side up)

```
y (um, row bottom)  row                                              content (left -> right)                                    height
 ~77     R5 top   ESD + pin row                           [ESD INN 33] ...... [ESD INP 33]  (centred under the pad slots)       10
  ~62    R4 PMOS  (VDD)                                   [mpt tail 40][ quad: mp1 A/B + mpd twins ~86]  = 132 x 10.3          10
  ~42    R3 stage 2                                       [ms 23][loads2 24][mp3 22][mn3 8][rs 14][mpu2 ~25]                  15
  ~15    R2 folds                                         [m5 31][RL 20][out chain 61]                                        22
   ~0    R1 NMOS  (VSS)                                   [mnt + quad 72][m3 sinks 44.5][mt2 ~17]                              10
```

Row widths: R1 134 + 2 gaps of 3 = 140; R2 112 + gaps; R3 about 116 + gaps; R4 132; all <= 150 (budget).  Heights: 10 + 22 + 15 + 10 + 10 = 67 of leaf boxes, plus four channels
of about 5 = 87, plus 10 for the pin row: about **100 um** against the 130 budget.

**Area estimate.** (Row packing: 140 x 100 = 14000 um2 bounding box, 72 % of the budget.)  Sum of leaf boxes per lane = 6150 um2 (summary.md, section "Estimated lane area"), times 1.35 for channels, straps and pin rows = 8300 um2, against
19500 (150 x 130): about 43 %.  Shape is the constraint, not area (PLAN_V2 L5): the widest leaf is the PMOS quad row.

**Mirror symmetry of the P and N input paths.**  `pair_dump` puts gate A (INP) on the top strap exiting EAST and gate B (INN) on the bottom strap exiting WEST, for both the
NMOS and the PMOS quad, so INP always lands at the east end of both pair rows and INN at the west end.  Put the INP pad slot on the east side of the lane axis, INN on the west
(`spec/pins.yaml`: x positions come from one list; swap them there if the pad order is the other way round).  The two ESD cells sit above the PMOS row left (INN) and right (INP)
of the lane axis; each B port (Metal3, exits east) is followed by a Metal3 run of the same length (about 55-60 um) to the pair row end, and then ONE Metal2 column per input runs
down to the NMOS pair gate (INP east, INN west).  Equal length by construction: the pair rows are symmetric about the lane axis and the ESD cells sit at mirror positions.  `esd_cell` has no mirror option (its resistor is on the left,
the B port on the right): for the INN side place the same leaf flipped about x at assembly (Magic `flip` / GDS mirror) or accept that the A and B stubs differ by the cell width (about
33 um) on one side and equalise with the Metal3 run; PEX of the two input nets decides (T9 criterion: C within 2 %).

**Where rings and taps go.**  Every leaf already carries its own ring: NMOS rows and the resistors p+ to VSS (substrate), PMOS rows n+ in n-well (VDD for mpt / mp3 / loads2, the tail node TP for the
PMOS quad), the ESD resistor n+ in n-well to VDD.  Rings stay between leaves (3 um clear gap, the ring and well margin of 2.2 um is inside the box).  A lane-level tap row is
not needed for DF.14_LV (every device is inside a ring within 20 um); the T9 agent may merge adjacent same-net rings later to save the 3 um gaps.  The n-well of the PMOS quad is on
TP (not VDD): its ring port must be routed to the TP bar (see `t_pmos_tail_dump`).

## 3. Metal2 columns and Metal3 channels the allocator will need

Metal2 columns (vertical, one per net, `Alloc.route`); gaps of 8 um between leaves in a row leave room for 8-10 columns:

| net | spans | notes |
|---|---|---|
| INP, INN | R5 -> R4 pair gate (east / west end) -> R1 pair gate | 90 um each, one column + two Metal3 stubs; keep the two equal (symmetry) |
| FA, FB | R4 quad drains -> R2 m5 sources -> R1 m3 sinks | 75 um; the folds carry the signal current, wide Metal3 stubs |
| OA, OB | R1 NMOS quad drains + R2 m5 drains + RL + R3 ms gates | 45 um |
| VBN | R1 mnt, m3, mt2 gates (one Metal3 channel along R1) | from the bias block |
| VBP | R4 mpt gate | from the bias block |
| VB2 | R2 m5 gates | |
| VREF | R1 mnd gates (2 flanks) and R4 mpd gates (2 flanks) | four ports on two rows: one Metal3 channel per row + one column |
| D2A, D2B, n3a, d3, i1, i2, nd | inside R3 / R2 (short) | |
| EN | nand, mpu2 x2 | |

Metal3 channels (horizontal) at the row boundaries, 0.7 um pitch (alloc `TRACK`): R1/R2: VBN, VREF, OA, OB, FA, FB (6 tracks); R2/R3: OA, OB, n3a, d3, VB2 (5); R3/R4: FA, FB, D2A?, INP, INN (5);
R4/R5: INP, INN, VBP, VREF (4).  Budget 5 um per channel is enough for 6 tracks at 0.7 pitch (4.2 um) plus spacing.  Power: VSS / VDD Metal3 straps at the row boundaries over the ring
gaps, at a pitch that crosses at least two M4 stripes of the block PDN (L4, read `pdn_cfg.tcl` on `main`, read only); rails are ordinary nets for `Alloc` (stage by stage, see pitfalls).

## 4. Macro strip

Strip 600 x 150 + margin, lane centres 200 um apart (x = 100, 300, 500 for a strip starting at 0): lane width 140-150 leaves 50-60 um between lanes and 15-25 um at the ends.
The bias block (about 5700 um2 estimate from summary.md, section "Estimated bias block"; the cap + resistor array are its bulk: `t_res_bias` 50 x 36, `t_cap` 31 x 24) does
not fit a 50-60 um gap in the widest arrangement of `t_res_bias`; plan it as a 2 x 2 block of about 75 x 60 at one strip end, or rotate `res_array` (leaf option, not built) -- decide in T9/T10.
Pin row on the top edge; positions from `spec/pins.yaml`.

## 5. Pitfalls met (all fixed or recorded in `layout/lib/README.md`)

1. Netgen compares only the SUM of series resistor lengths (cutoff 1 %); a series middle node as a pin stops the merge; shorted dummy resistors must be listed in the schematic.
2. cap_nmos_03v3 cannot come from `nmoscap_3p3` (varactor; vanishes in GDS extraction; PL.5a fail): use the nfet-with-S=D cap and change the LVS reference line for XCVREF to `nfet_03v3 w=20u l=25.13u` (SIMULATION model stays).
3. L = 0.28 gencells need the contact-bar trim and the 0.48 pad clear in `mos_row` (M1.2a diagonal 0.209 um); Magic's CO.6 over-reports on them (allow-listed, KLayout stays the check).
4. Wf < 1.2 um (men_n 1.0): `m1_ring_regions=True`, `dummies=0`.
5. ABBA needs a common source: pairs with source degeneration (ms) or cascodes (m5) are two identical rows; the dump-twin quad has only (abba) flanks.
6. Odd finger counts: at most two odd devices per mirror row (one single finger at each end); ABBA needs even nf (ms has nf 3: not used as ABBA).
7. One Metal2 column cannot serve a net spanning a whole row of leaves (window 12 um): chain the ports pairwise (rails in `t_out_chain`).
8. Ports of one net on both sides of a column at heights differing by 0 < dy < 0.56 um make stubs 0.15 um apart: align the leaves in y (`t_en_inv` builds the P row on a scratch block to read the bar height first).
9. A pin on a Metal2 column whose ports sit at one height must be placed at that height (fixed in `alloc.route`).
10. `select top cell` / unique labels: every segment label is `NET.k`; only pins carry the plain name (T8 part 1).
11. The PMOS quad row is 80+ um of Metal3 bars: thin wires pass MSLOT.1 (erosion rule), the 29 um cap is bookkeeping only.
12. The secondary ESD cell is **UNQUALIFIED**; antenna sees its diodes (see `ant_esd_comparison.json`).
13. Run times: leaf KLayout deck about 20-45 s per cell; the whole `run_all.py` (29 cells + antenna pair) about 12 min in one process.

## 6. Build order for T9

1. Read `device_table.json` through `lib.device_table` (no literals).  2. Place R1 (`tail_dump`, `pair_abba` m3 sinks, mirror part mt2), R2 (m5 rows, `res_array` RL, `t_out_chain` builder),
R3, R4 (`tail_dump` with `rail_pair="TP"`), R5 (`esd_cell` x2).  3. Route nets with `Alloc` in the order: short local nets first, then FA / FB / OA / OB, then INP / INN, then bias nets, then rails.
4. `check.run_cell` on the lane (strict LVS against the hierarchical reference flattened; negative controls; finger read-back for each row).
