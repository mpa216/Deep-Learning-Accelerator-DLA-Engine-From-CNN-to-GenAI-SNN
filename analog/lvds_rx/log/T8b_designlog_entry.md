## 2026-11-11 T8 part 2: poly resistors, ESD cell, the rest of the transistors, and a floorplan for one lane

**What was done.** Part 1 gave us generators for transistor rows. Part 2 adds the passives (resistor arrays, the secondary-ESD sub-cell, the Vref capacitor), a leaf for every
remaining device group in `layout/device_table.json` (35 transistors, 7 resistors, 2 diodes, 1 cap: all covered) and the recipe for placing them as one lane. One command,
`python3 layout/leaf_tests/run_all.py` inside the container, rebuilds and re-checks all 29 leaves in about 12 minutes; the last line is `ALL GREEN` and the table is
`layout/leaf_tests/results/summary.md`. After the sizing freeze just run it again.

**Why each leaf is checked so hard.** A layout can be DRC-clean and still be the wrong circuit. Each leaf is built from the device table, extracted back from the GDS and compared with
what was asked for (W, L, fingers, resistor length, diode area), run through the foundry DRC deck and the antenna deck (KLayout, 0 / 0 everywhere), compared with the schematic by
Netgen (unique match, no property or port errors) and finally attacked: wrong width, a cut wire, a sliver. Every attack is caught.

**New things learned (the useful part).**

* *Resistors are drawn as snakes.* A long resistor (rb is 90 um) is built from several equal series pieces. Netgen adds series pieces up and compares the total length with the schematic's single
  resistor (1 % tolerance), so the unmodified reference netlist still matches. We choose the piece length so that the RESISTANCE is right (every piece has 85 ohm of end contacts), which
  makes the summed length 0.4 - 0.9 % short: harmless, but RL (0.85 %) is close to the limit. Dummy resistors at both ends are real devices to Netgen, so they are listed in the schematic.
  The divider rdt / rdb is interleaved (`rdt rdb rdb rdt rdt rdb rdb rdt`) and read back from the extraction in that order.
* *The antenna rule sees the ESD diodes.* A 1 um2 gate on a 700 um Metal3 run fails ANT.16_i_ANT.4 by itself and is clean when the nd2ps / pd2nw diodes of the ESD cell hang on the same net.
  Nothing about ESD robustness follows from that: the cell is **UNQUALIFIED**.
* *The PDK's MOS capacitor gencell is a trap.* `nmoscap_3p3` draws a varactor (`cap_nmos_03v3_b`), vanishes when Magic reads the GDS back (the marker layer is not mapped) and fails
  two KLayout rules. The Vref cap is drawn as what it is in silicon, an NMOS with source = drain = VSS (20 x 25.13 um, 2 pF). Consequence: the LVS reference line for XCVREF has to
  become an `nfet_03v3`; the simulation can stay as it is.
* *The 0.28 um digital devices are tight.* The generator's gate-pad corner sits 0.209 um from the next contact bar (rule: 0.23). We trim 0.04 um off the contact-bar ends, which works when the
  contacts leave at least 0.105 um of margin (Wf 3.7 does not, so inv1_p is laid out as two fingers). Magic's own CO.6 over-complains about the trimmed bars; the foundry deck does not.
* *Pairs with different sources cannot be ABBA.* The stage-2 pair (source degeneration) and the fold cascodes are two identical rows side by side instead.
* *The router (alloc) got three fixes:* stubs of one net 0.15 um apart are now rejected before painting, a pin on a short column sits at the port height, and rails are routed stage by stage.

**Numbers.** PMOS input quad row 131.7 x 10.3 um (112 fingers), NMOS quad + tail 72.0 x 10.0, resistor array of the bias block 53.7 x 35.6 (16 resistors), ESD cell 32.6 x 10.1, output
inverter chain 61.5 x 22.3. Estimated lane: leaf boxes 6 150 um2, 8 300 um2 with routing, 140 x 100 um after row packing against the 150 x 130 budget.

**Pictures.** `layout/leaf_tests/results/`: `t_res_bias.png` (the resistor row), `t_esd.png` (ESD cell: resistor in its n-well, then the two diodes), `t_out_chain.png`, `t_pmos_tail_dump.png`,
`t_ant_bare.png` / `t_ant_esd.png` (antenna with and without ESD), `t_cap.png`.

**Open.** Ring merging between leaves, the bias block position in the strip, `check_via_arrays.py`, PEX. The floorplan and the pitfalls are in `layout/lib/LANE_RECIPE.md`.
