# LVDS receiver: integration into the A56 / ACV chip

Branch `lvds-integration` (cut from `lvds-rx` at 8145d91, which is `main` 9be761d plus the finished
macro). `main` and the signed-off chip are untouched; nothing is pushed.

**Status 2026-11-23: phase 1 of 3 done** (RTL, verification, frame template, flow configuration,
placement dry run). Phase 2 (full harden + power weld + sign-off) waits for the owner's go-ahead.
Phase 3 (submission files) waits for the organizers' official template.

## 1. What the integration does, in plain words

The chip talks to its host over a 4-wire serial link (SCLK, MOSI, CS_N in; MISO out) on ordinary
3.3 V CMOS pads. The integration gives the three *input* wires a second path: each can now arrive as an
LVDS pair on two analog pads, go through one lane of the receiver macro, and reach the same serial
bridge. A new strap pin, LINK_SEL, picks the path:

```
 CMOS pads  SCLK_IN, MOSI_IN, CS_N_IN ───────────────────────────────┐
                                                                     ├─ mux ─► dla_serial_bridge ─► DLA core
 N02/N03 LVDS_SCLK_P/N ─┐                                            │  (bridge and core unchanged)
 N04/N05 LVDS_MOSI_P/N ─┼─► lvds_rx_x3 (u_lvds) ─ RX0_O/RX1_O/RX2_O ─┘
 N06/N07 LVDS_CSN_P/N  ─┘        ▲ EN
 N01 LINK_SEL ─► dla_link_sel ───┘ (2-FF sync, EN, 64-clock wake time, then switch)
```

- **LINK_SEL = 0** (the pad's weak pull-down makes an unconnected pin 0): the chip behaves exactly like
  the signed-off one; the receiver is switched off (EN = 0).
- **LINK_SEL = 1**: the receiver is switched on; 64 clocks (2.56 us at 25 MHz) later, after it has
  woken up (its spec allows 1 us), the bridge reads the LVDS lanes instead of the CMOS pins.
- Going back to 0 switches the bridge back on the same clock edge that switches the receiver off.
- The receiver stays off while `rst_n` is low, which satisfies the macro's power-up rule "EN low until
  VDD >= 2.0 V" (decision D-008) as long as the board holds reset during the supply ramp.
- Host rule: change LINK_SEL only between frames (CS_N high on both links). The bridge aborts any frame
  whose CS_N reads high, so a switch between frames is safe (shown in simulation below).

This is the handoff's **Mode A** (de-risking: same speed as today, the full Mode B burst link is a later,
separate step), with all three receiver lanes used, so no lane input is left floating.

## 2. Where the macro went: "the cut"

The macro (650 x 194.2 um) sits in the north-west of the core, top edge on the core top:
x 121.05-771.05 um, y 875.80-1070.00 um. That strip held only standard cells before (the eight SRAMs end at
y 802.4), so no other macro moved and the logic is unchanged: the placer simply puts those standard cells
elsewhere. Its x position puts each of the six receiver pins directly under finger 5 of its pad's comb,
so each pad-to-receiver connection is a straight ~39 um drop under the core power ring.

What the cut costs (dry run, after detailed placement): the macro takes 126,230 um2, 7.7 % of the core
area and 11.6 % of the area the standard cells had before. The standard-cell utilisation is 40.1 %
(386,461 um2 of cells in the 962,779 um2 the nine macros leave free); the same cells without the cut would
sit at about 35.5 %. The placement target is 50 %, so there is room for the clock tree and timing buffers
the full harden adds. Pictures: `librelane/lvds/render/dryrun_block.png` (whole block),
`dryrun_lvds_strip.png` (the cut), `dryrun_pads_to_pins.png` (pads N02 / N03 above the macro pins).

## 3. Pads and the provisional frame template

The existing ACV frame already has `asig_5p0` analog pads on all 16 north slots (N01-N16, unused fillers).
The seven new pins are appended to `info.yaml` after DVSS, so W12-W22 keep their slots, and land on
N01-N07 in order (the organizers' rule as far as we can tell; to be confirmed):

| Slot | Pin | Pad cell | Connects to |
|---|---|---|---|
| N01 | LINK_SEL (+ LINK_SEL_PU, LINK_SEL_PD) | in_c (input_cmos) | dla_link_sel; PD = 1 (pull-down on) |
| N02 / N03 | LVDS_SCLK_P / _N | asig_5p0 (analog) | u_lvds RX0_P / RX0_N |
| N04 / N05 | LVDS_MOSI_P / _N | asig_5p0 | u_lvds RX1_P / RX1_N |
| N06 / N07 | LVDS_CSN_P / _N | asig_5p0 | u_lvds RX2_P / RX2_N |

The block's floorplan template normally comes from the organizers. Until they regenerate it from the new
`info.yaml`, `librelane/A56_ACV_lvds.def` is derived from the existing frame by
`librelane/lvds/make_template.py`, which reproduces their rule (each pin = the Metal2 shapes of its pad
terminal at the pad's core edge, projected 1 um into the block). **Self-check: the script regenerates all
64 pins of the organizers' current A56_ACV.def exactly** (order, names, directions, every rectangle), then
adds 9 pins: the in_c terminals of N01 and the eight ASIG5V Metal2 fingers of each analog pad
(x 145.34-189.66 um for N02, +100 um per slot, y 1109-1110 um). When the official template arrives, drop it
in as `librelane/A56_ACV_lvds.def` and re-run phase 2; `check_integration.py` compares the pins.

## 4. Files

| File | What |
|---|---|
| `rtl/dla_engine_chip.sv` | +9 ports (LINK_SEL, its PU/PD, six LVDS pads), u_lvds, u_link_sel, the 3-input source mux; stale pin-map comments fixed |
| `rtl/dla_link_sel.v` | NEW: strap synchroniser, receiver EN, wake timer |
| `rtl/lvds_rx_x3.v`, `macros/lvds_rx_x3/` | copies of the delivered macro package (GDS sha 892add3b) |
| `info.yaml` | 7 pins appended (N01-N07) |
| `librelane/config_acv_lvds.yaml` | `config_acv.yaml` + the LVDS deltas (config_acv.yaml untouched) |
| `librelane/A56_ACV_lvds.def` | provisional template (section 3) |
| `librelane/lvds/` | make_template.py, check_integration.py, build_acv_lvds_connected.sh (phase 2), pin report |
| `tb/dla_engine_chip_lvds_tb.sv` | NEW: d3004n4 over CMOS, LVDS, CMOS again on one chip |
| `tb/dla_engine_chip_{,gan_,wave_}tb.sv` | LINK_SEL tied low (= the pad pull-down); race-free stimulus (section 6); GAN TB gains `+define+LVDS_LINK` |
| `formal/dla_link_sel{.sby,_props.sv}` | NEW proof of the link select |

## 5. Verification, expected against actual

| Check | Expected | Actual |
|---|---|---|
| RTL compiles (Icarus, with and without `SYNTHESIS`); Verilator `-Wall` | new code clean | both builds OK; `dla_link_sel.v` and the chip glue raise no warning; the 20 that remain are in unchanged core and SRAM files (16) and the macro's blackbox stub (4: unused EN, undriven outputs, the same pattern as the SRAM blackbox) |
| Signed-off pad-level test `dla_engine_chip_tb` (CMOS, LINK_SEL low) | d3004n4 goldens -34139, 59877, -36996, -23021 | PASS; finishes at 1,664,076 ns, the same instant as `main`'s RTL under the same test: the CMOS path is cycle-identical |
| New `dla_engine_chip_lvds_tb`: CMOS, then LVDS, then CMOS on one chip, the unused link carrying garbage or floating | 3 x 4 rows bit-exact (row order rotated per phase) | PASS, 12 / 12 |
| Link switch | EN 2 clocks after LINK_SEL (synchroniser); bridge on the receiver exactly 64 clocks after EN; back on the clock EN falls; no core command during a switch | 2 clocks / 64 clocks / same clock / none |
| Full GAN image (784 pixels) through the CMOS link | 784 / 784 bit-exact | PASS (840 s) |
| Full GAN image through the LVDS link, CMOS serial pins carrying garbage | 784 / 784 bit-exact | PASS (908 s) |
| Formal proof of `dla_link_sel` (k-induction, depth 70) | proof passes and is not vacuous | PASS with 6 assertions + 1 assumption elaborated; covers reached at step 67 (LVDS on) and 68 (off again); three deliberately broken copies (switch one clock early, select not gated by EN, one-flop synchroniser) are all rejected |
| Template self-check | the 64 pins of the organizers' A56_ACV.def regenerated exactly | EXACT MATCH |
| Dry run, synthesis to detailed placement (no routing), `runs/lvds_fp2` | runs clean, warnings as in the signed-off run | exit 0 in 92 s; the same warnings as `acv_ring6` (core-origin snap, SRAM antenna info, 12 PDN-0110 at SRAM edges, LibreLane's template-area units message) |
| Macro placement | (121.05, 875.80) um, R0, fixed | as expected, FIRM |
| Pins | 73, the 9 new ones identical to the template | 73; identical; 8 finger boxes per analog pin |
| Analog nets | each `LVDS_*` net = its pad + one macro pin, no buffer or diode | all six clean, also after the resizer's repair pass |
| Macro power | VDD on DVDD, VSS on DVSS, grid vias landing on its Metal3 straps | 44 vias on the VDD straps, 64 on the VSS straps |
| The cut | no standard cell inside the macro + 10 um halo | 0 of 21,087 |
| Macro outputs (30 fF limit) | short net into one nearby load | each RXk_O drives one mux at 37 / 96 / 44 um; EN comes from a buffer 45 um away |
| Utilisation | below the 50 % placement target | 40.1 % |

`librelane/lvds/check_integration.py <odb>` repeats the last seven rows on any later run.

## 6. Two things found on the way

**A race in the chip testbenches (testbench only, the design is fine).** The pad-level testbenches changed
the serial pins at the same instant as the clock edge. In a zero-delay simulation the order of events then
decides whether the bridge sees a change this clock or the next. On `main` it happened to resolve one way;
the integration's source mux adds one evaluation step, it resolved the other way, the READ_C read-back
sampled one bit late, and every result came back halved. The testbenches now act 1 ns after the edge (a
fixed, worst-case order); `main`'s own testbench with the same fix still passes on `main`'s RTL, at the same
instant as the branch. Lesson for the real host (TEST_PLAN): the bridge moves MISO to the next bit 2 to 3
clocks after an SCLK rising edge reaches it (depending on where the edge falls between clock edges), and any
delay before the bridge comes on top: the pad's input buffer, and in LVDS mode the receiver (3.5 ns typical,
up to 8 ns at the smallest input swing) plus the mux. A host that samples MISO exactly 3 clocks after its own
rising edge, TEST_PLAN's minimum "hold each SCLK level >= 3 clk", therefore has no margin for READ_C; at
TEST_PLAN's "SCLK <= clk/8" (4 clocks per level) it has one clock. Use clk/8.

**The serial bridge's formal proof on `main` proves nothing.** `formal/dla_serial_bridge.sby` attaches its
properties with a SystemVerilog `bind`; Yosys 0.64's open-source frontend parses `bind` and silently drops
it, so the proof model contains zero assertions and "successful proof by k-induction" is vacuous (checked:
0 property cells in the elaborated model; the controller proof, which uses a wrapper, has 6). This predates
the integration. The new `dla_link_sel` proof uses the wrapper style and a negative control (above). Fixing
the bridge proof means rewriting it as a wrapper; its two key properties read internal registers, so that
needs either an `ifdef FORMAL` block inside the signed-off `dla_serial_bridge.v` or weaker port-level
properties: a decision for the owner. The integration does not depend on it (the bridge is unchanged and
the simulations above exercise it).

## 7. Open items

- **Official template** (the owner asks the organizers, section 8): put it in as `librelane/A56_ACV_lvds.def`,
  re-run, and compare with `check_integration.py`; if their pins differ from ours, only the template changes
  (the macro's x position is tuned to the finger positions and may move with it).
- **Phase 2, needs the owner's go-ahead** (`bash librelane/lvds/build_acv_lvds_connected.sh <tag>` in the
  container): full harden (about 45 min) -> power-pin weld -> Magic DRC, Netgen LVS (the macro is a black box
  there, like the SRAMs; its own LVS was done standalone), XOR, antenna (the 2026-08 re-closure needed a
  repair-margin sweep; budget one), SPEF 9-corner STA, the KLayout foundry deck (about 16 min), the via-array
  check, gate-level simulation of the hardened netlist over both links, and the integration checks. Disk:
  13 GB free; a full run is a few GB, stripped to `final/` afterwards.
- **Phase 3** (after the official template): `gds/`, `verilog/`, `lvs_config.json` (add the macro's SPICE,
  `macros/lvds_rx_x3/spice/lvds_rx_x3.spice`), a TEST_PLAN section for the LVDS link, README and learning notes.
- **Export control:** the signed form describes a "fixed-function digital ASIC" with a "digital clock DC to
  25 MHz only". The link still runs at the bridge's rate, but the chip now contains an analog receiver; the
  wording may need revising and re-signing.
- **Receiver limits that carry into the chip** (`macros/lvds_rx_x3/KNOWN_LIMITS.json`): no failsafe (keep
  LINK_SEL low unless a host drives the LVDS lanes; an unconnected strap is low by the pad pull-down), EN low
  until VDD >= 2.0 V (met through `rst_n` if the board holds reset during power-up), secondary ESD and
  latch-up not qualified.
- **Mode B**, the actual speed-up (17-60x with a burst link and a 100-200 Mb/s DDR lane set), is a later step:
  it reuses this physical integration (same pads, same macro) and adds new digital logic (handoff 13.3).

## 8. Request to the organizers (for the official template)

Draft to edit and send (it reuses `GUIDE_FOR_YOU.md` section 8, now with concrete pins):

> **Subject:** A56 / ACV: request for a regenerated block template (7 appended pins, 6 of them analog)
>
> Hi [organizer],
>
> For project A56 (block ACV, top `dla_engine_chip`) we have integrated an LVDS receiver hard macro behind
> analog pads. Our updated `info.yaml` appends 7 pins after DVSS, so W12-W22 are unchanged:
> `LINK_SEL` (input_cmos), then `LVDS_SCLK_P`, `LVDS_SCLK_N`, `LVDS_MOSI_P`, `LVDS_MOSI_N`, `LVDS_CSN_P`,
> `LVDS_CSN_N` (all `analog`). We expect them on N01-N07 (pin count 11 -> 18 of the block's 27 slots).
> Could you regenerate our block DEF template and pad map from it? Questions:
>
> 1. Do appended pins land on N01, N02, ... in order, and is 18 pins acceptable for the shuttle?
> 2. For the `analog` pins we assumed the template shows the eight ASIG5V Metal2 fingers projected 1 um
>    into the block (as for our DVDD/DVSS today). Is that right?
> 3. The ring break `BRK_AFTER_ACV` is after W22 today. Will it move after our last pin, so the analog
>    pads' clamp diodes and the in_c pad sit on our DVDD/DVSS segment?
> 4. Integration LVS: should `lvs_config.json` list the macro's SPICE in `LVS_SPICE_FILES` (and the macro in
>    `LVS_NOFLATTEN`)? Its supply pins are VDD/VSS, tied to DVDD/DVSS in the layout, like the SRAM macros.
> 5. Secondary ESD: the macro has its own (151 ohm + diode clamps per input). Is your secondary-ESD cell still
>    required on analog pins that drive only MOS gates?
> 6. Fill and density around an analog macro: is fill inserted at chip level, and should we mark the macro
>    area (650 x 194 um) to exclude it?
> 7. Does a revised A56 need a new mentor review, and what are the deadlines for the pin list and final GDS?
>
> Thank you!
> [your name], team FindingSRAM (A56)
