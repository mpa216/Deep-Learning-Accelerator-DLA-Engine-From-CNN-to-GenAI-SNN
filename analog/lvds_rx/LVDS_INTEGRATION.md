# LVDS receiver: integration into the A56 / ACV chip

Branch `lvds-integration` (cut from `lvds-rx` at 8145d91, which is `main` 9be761d plus the finished
macro). `main` and the signed-off chip are untouched; this branch is pushed as `origin/lvds-integration`
(2026-11-26).

**Status 2026-11-26: phases 1 and 2 of 3 done.** Phase 1 (2026-11-23): RTL, verification, frame template,
flow configuration, placement dry run. Phase 2 (2026-11-26): the full layout. The block with the receiver
hardens, its power pins weld, and it signs off clean: Magic DRC, the KLayout foundry deck, antenna (0), via
arrays, LVS, XOR, 9-corner timing and gate-level simulation over both links (section 5, phase 2; reports in
`signoff/A56_lvds_phase2/`). The layout of record is run `acv_lvds5b`, built from `config_acv_lvds.yaml` as
committed (antenna repair margin 80; the first complete run, `acv_lvds2`, at the signed-off 75, left two nets just
over the antenna limit, section 6). Its GDS is `gds/dla_engine_chip.gds` on this branch (SHA-256 `70e9a199...`).
Same day, at the owner's request, the branch was **prepared to replace `main`** (its
submission files are now the LVDS version, README and TEST_PLAN updated) and **pushed as
`origin/lvds-integration`**; `main` is untouched (section 7). Phase 3 waits for the organizers' official
template (section 8).

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
adds 9 pins: the three in_c terminals of N01, and one pin per analog pad.

**The analog pins are one rectangle each, not eight (changed in phase 2).** An `asig_5p0` pad hands its
ASIG5V terminal to the block as a comb of eight 2.54 um Metal2 fingers, so the organizers' rule gives eight
rectangles per analog pin; the first template did exactly that. LibreLane's pin copy (`Odb.ApplyDEFTemplate`)
turns every rectangle into a separate pin, and the detailed router stops on a signal terminal with more than
one pin: `[DRT-0302] Unsupported multiple pins on bterm LVDS_CSN_N` (run `acv_lvds1`, 2026-11-26; only power
pins may have several, which is why DVDD/DVSS with six fingers each never hit it). In the organizers' current
template every one of the 62 signal pins has exactly one rectangle, so this is new ground for them too. Each
analog pin is now ONE rectangle: the bounding box of its eight fingers, a 44.32 x 1 um bar along the block's
top edge under the whole comb (x 145.34-189.66 um for N02, +100 um per slot, y 1109-1110 um). Electrically it is
the same node (the fingers are one terminal, joined inside the pad), and it keeps every other wire of the block
off all eight fingers. It is safe at chip level: the pad's other Metal2 stops 1.61 um short of its core edge
(read from the pad LEF by the script; the Metal2 spacing rule is 0.28 um). When the official template arrives,
drop it in as `librelane/A56_ACV_lvds.def` and re-run phase 2; `check_integration.py` compares the pins (if the
organizers give eight fingers, see section 8, question 2).

## 4. Files

| File | What |
|---|---|
| `rtl/dla_engine_chip.sv` | +9 ports (LINK_SEL, its PU/PD, six LVDS pads), u_lvds, u_link_sel, the 3-input source mux; stale pin-map comments fixed |
| `rtl/dla_link_sel.v` | NEW: strap synchroniser, receiver EN, wake timer |
| `rtl/lvds_rx_x3.v`, `macros/lvds_rx_x3/` | copies of the delivered macro package (GDS sha 892add3b) |
| `info.yaml` | 7 pins appended (N01-N07) |
| `librelane/config_acv_lvds.yaml` | `config_acv.yaml` + the LVDS deltas (config_acv.yaml untouched) |
| `librelane/A56_ACV_lvds.def` | provisional template (section 3) |
| `librelane/lvds/` | make_template.py, check_integration.py, build_acv_lvds_connected.sh (phase 2), render_layout.tcl, pin report, pictures in `render/` |
| `signoff/A56_lvds_phase2/` | the phase-2 reports (DRC, LVS, XOR, antenna, timing, foundry deck, weld, integration checks, gate-level simulation) with a README |
| `tb/dla_engine_chip_lvds_tb.sv` | NEW: d3004n4 over CMOS, LVDS, CMOS again on one chip |
| `tb/dla_engine_chip_{,gan_,wave_}tb.sv` | LINK_SEL tied low (= the pad pull-down); race-free stimulus (section 6); GAN TB gains `+define+LVDS_LINK` |
| `formal/dla_link_sel{.sby,_props.sv}` | NEW proof of the link select |

## 5. Verification, expected against actual

### Phase 1 (RTL, template, placement dry run)

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
| Pins | 73, the 9 new ones identical to the template | 73; identical; 8 finger boxes per analog pin (the first template; the router rejects that, so phase 2 uses one bar per analog pin, section 3) |
| Analog nets | each `LVDS_*` net = its pad + one macro pin, no buffer or diode | all six clean, also after the resizer's repair pass |
| Macro power | VDD on DVDD, VSS on DVSS, grid vias landing on its Metal3 straps | 44 vias on the VDD straps, 64 on the VSS straps |
| The cut | no standard cell inside the macro + 10 um halo | 0 of 21,087 |
| Macro outputs (30 fF limit) | short net into one nearby load | each RXk_O drives one mux at 37 / 96 / 44 um; EN comes from a buffer 45 um away |
| Utilisation | below the 50 % placement target | 40.1 % |

`librelane/lvds/check_integration.py <odb>` repeats the last seven rows on any later run.

### Phase 2 (the full layout, run `acv_lvds5b`, 2026-11-26)

What phase 2 does, in plain words: the flow turns the design into the finished chip layout. It builds the
clock tree, draws every wire (including the six pad-to-receiver drops), joins the frame's power pins to the
block's power ring (the "weld"), and writes the GDS, the file a foundry manufactures from. Then every check runs
on that file. Built with `bash librelane/lvds/build_acv_lvds_connected.sh acv_lvds5b` (about 45 min) from
`config_acv_lvds.yaml` as committed, which now carries its two settings: antenna repair margin 80 and 4 routing
threads. Earlier runs: `acv_lvds1` stopped in routing on the multi-pin analog pins; `acv_lvds2` (margin 75) was
clean except two antenna nets (section 6). The reports are in
`signoff/A56_lvds_phase2/` (README there has the files and commands). "Signed-off" = the chip without the receiver.

| Check | Expected | Actual |
|---|---|---|
| Routing DRC (detailed router) | 0 | 0 |
| Magic DRC | 0 | 0 |
| KLayout foundry deck (660 rule categories) | 0 | 0 |
| Via arrays (rule Vn.2b, not in the open deck) | 0 | 0, the receiver included |
| Netgen LVS | "Circuits match uniquely" | match uniquely: 26,905 devices and 14,131 nets each side, 0 errors; the receiver is a black box with its 12 pins (like the SRAMs; its own transistor-level LVS was done standalone) |
| Magic vs KLayout GDS XOR | 0 | 0 |
| Antenna (OpenROAD and the foundry deck) | 0 (signed-off 0) | 0 and 0 (`acv_lvds2`, at margin 75: 2 nets, section 6) |
| Density (whole die, no fill in the block) | the signed-off findings | the same 6 |
| Timing, 9 corners with extracted wires (SPEF), 40 ns clock | no violation; signed-off +14.98 / +0.117 ns | setup +14.78 ns, hold +0.116 ns, no violation |
| Power | about 125 mW | 125.4 mW, plus about 8 mW for the receiver when it is on (2.4 mA typical; its timing model carries no power) |
| Power weld | every DVDD/DVSS finger joined, 0 refusals | 12 fingers, 89 via stacks, at least 1.575 um from other metal |
| Integration checks (`check_integration.py`, now 8) | 8 / 8 | 8 / 8; each pad-to-receiver drop is 39.9-43.4 um, one via, under its own pad; no foreign wire in the receiver's core, no switching net beside its inputs (the static enable `lvds_en` is listed, section 6) |
| Gate-level simulation, routed netlist: LVDS testbench | 12 / 12 rows bit-exact | 12 / 12 (CMOS, LVDS, CMOS on one chip) |
| Gate-level simulation, routed netlist: signed-off pad testbench | PASS at the same instant as RTL | PASS at 1,664,076 ns |
| Disconnected pins | 0 critical | 0 critical; 4 harmless (the output pads' unused feedback inputs, as signed-off) |

Pictures (`librelane/lvds/render/`): `acv_lvds5b_block.png` (whole block), `acv_lvds5b_lvds_strip.png` (the
receiver, its power straps and the cells around it), `acv_lvds5b_pads_to_pins.png` (two analog pin bars and their
straight drops into the receiver), `acv_lvds5b_weld_linksel.png` (the west power weld; the LINK_SEL wire comes down
from the top edge and turns east above it).

## 6. Things found on the way

### Phase 1

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

### Phase 2

**The router cannot take a pin made of eight fingers.** The first full run (`acv_lvds1`) stopped in detailed
routing with `[DRT-0302] Unsupported multiple pins on bterm LVDS_CSN_N`. LibreLane's pin copy makes one pin
per template rectangle, and the router accepts several pins on one terminal only for power nets. Fixed in the
template (one bar per analog pin, section 3); the same question goes to the organizers (section 8, question 2).
A check that would have caught it 40 minutes earlier: count the pins per signal terminal right after
`Odb.ApplyDEFTemplate` (every one must be 1).

**Two antenna violations, and why the usual knob does not reach them.** The first complete layout
(`acv_lvds2`) was clean in DRC, LVS and XOR, but the antenna check after detailed routing found two nets over
the Metal3 limit: `net792` at 1.24 times the limit and `_08355_` at 1.004 times. Both are digital nets that
run 370 and 570 um along Metal3 through the 73 um channel between the receiver and the SRAM row below it, the
area the cut made busier. (In plain words: a long wire collects charge during manufacturing, and if it is
connected only to a small transistor gate at that moment, the charge can damage the gate; the limit is a ratio of
wire area to gate area, and a small protection diode on the wire raises what is allowed.) The flow fixes
antennas in two places: early "heuristic" diodes on every long net, and a repair after global routing that
adds jumpers (a short hop to another metal layer) or diodes, with a 75 % safety margin because the final
wires come out longer than the global-route estimate. That repair leaves nets that already carry diodes
(`GRT-0243 Unable to repair antennas on net with diodes`), and the final route pushed these two over. The
foundry deck reports exactly the same two gates with the same ratios (494.2 and 401.48), and shows why a diode did
not help the worse one: at the Metal3 stage its diode is not yet connected (the router joined it through a higher
layer), so it protects nothing while Metal3 is etched.

Three ways to close them without touching the margin were tried, each against `acv_lvds2`; none worked:

| Attempt | Idea | Result |
|---|---|---|
| repair margin 100 (heuristic diodes on) | over-fix harder | the repair switched itself OFF: OpenROAD scales each limit by (1 - margin/100), a limit of 0 means "no rule", so it found 0 violations to fix; stopped |
| heuristic diodes off, margin 75, 5 repair passes | let the margin-protected repair handle every net | the repair cleared all 421 violations it saw before routing, but after detailed routing 6 nets were over, up to 2.39 x: worse. The final wires differ from the estimate by more than any margin; the early diodes do help (as the 2026-06 notes say) |
| the detailed router's own antenna repair (`DRT_ANTENNA_REPAIR_ITERS 2`, jumpers only), restarted from `acv_lvds2`'s state just before routing | fix exactly the nets that fail after routing | the first routing pass reproduced `acv_lvds2` exactly (0 routing errors, the same 2 antenna nets); the repair then put in its jumpers, and the re-route crashed: `DRT-0073 No access point` for clock buffers and diodes, the dead end recorded in 2026-06, still there in OpenROAD 26Q1 |

Then the lever that closed the signed-off chip, the repair-margin sweep (25 -> 50 -> 75 there), run as two
full builds side by side with the heuristic diodes on:

| Margin | Antenna after detailed routing |
|---|---|
| 50 (`acv_lvds5a`) | 1 net, `dla_wr_addr[4]` at 1.15 x (stopped) |
| 75 (`acv_lvds2`) | 2 nets, 1.24 x and 1.004 x |
| **80 (`acv_lvds5b`)** | **0**, and clean in every other check (section 5, phase 2) |

80 is now in `config_acv_lvds.yaml`, with `ROUTING_CORES: 4` (the router's result can depend on the thread count),
so the committed config reproduces the layout of record. Antenna is a property of one particular route: the
phase-3 run on the official template re-rolls the routing, so check it again there. Evidence kept in
`.scratch/integ/` (`acv_lvds3b_margin100_repair.log`, `acv_lvds3a_heuristic_off_antenna.rpt`,
`acv_lvds4_drt_repair_DRT0073.log`, `acv_lvds5a_margin50_antenna.rpt`); the variant runs are deleted.

**`final/odb/` holds two databases; the welded one is `_connected.odb`.** The build writes the power weld into
`_connected.odb` and resumes the flow from it; LibreLane's "save views" copies the state's file under its own
name, so `final/odb/dla_engine_chip.odb` is a stale copy from before the weld (the same is true of the signed-off
`acv_ring6`). Every sign-off step read `_connected.odb` (checked in each step's `state_in.json`), so the GDS,
DRC, LVS and timing are of the welded design; only a tool pointed at `final/odb/dla_engine_chip.odb` by hand sees
the unwelded one (the first render did). `render_layout.tcl` reads `_connected.odb`.

**Digital wires cross the receiver's margin, not its circuit.** The macro's LEF blocks Metal1-Metal3 over its
600 x 144 um core only; the 25 um margin around it is a standard-cell-free margin (handoff sections 12 and 14.2) and open to
routing. After routing (`acv_lvds5b`) nothing lies inside the blocked core, and no switching net runs on
Metal1-Metal3 in the top margin where the six input strips go up to the pads. Wires do use the bottom margin (the
digital side, where EN and the outputs are: about 1,380 um of Metal3 from 6 nets) and the side margins. One net
does cross the top: `lvds_en`, the receiver's own enable before its buffer, with 22 um of Metal3 in the top margin
(more than 5 um from every input strip), 169 um of Metal4 over the core and a 628 um Metal5 run two layers above
all six input strips (in `acv_lvds2` it crossed one). It only changes when the host flips LINK_SEL, and the bridge
ignores the LVDS lanes for 64 clocks after every switch, so it cannot put noise on a received bit; each Metal5
crossing adds well under 1 fF to a pad that already carries about 0.2 pF. `check_integration.py` check 8 grades
the two things that matter (nothing inside the blocked core; no switching net beside the inputs), lists the
static link-select nets by name and length instead of grading them, and reports the rest. If the owner wants the receiver's surroundings quieter, a Metal4/Metal5 routing obstruction over it (the
handoff's optional item) can go into the phase-3 run.

## 7. Open items

- **Official template** (the owner asks the organizers, section 8): put it in as `librelane/A56_ACV_lvds.def`,
  re-run, and compare with `check_integration.py`; if their pins differ from ours, only the template changes
  (the macro's x position is tuned to the finger positions and may move with it). If their analog pins come as
  eight fingers, the router stops (section 6); then either they change it or our flow has to merge the fingers.
- **Phase 2: done 2026-11-26** (section 5, phase 2), clean in every check, antenna included (margin 80).
- **Antenna in the phase-3 run:** the official template re-rolls the routing, so check antenna again. If it is not
  0 at margin 80, sweep around it (`build_acv_lvds_connected.sh <tag> -c GRT_ANTENNA_REPAIR_MARGIN=<m>`, one run each;
  two runs side by side with `-c ROUTING_CORES=4` fit this machine). Not to retry: margin 100 (switches the repair
  off), heuristic diodes off (worse), `DRT_ANTENNA_REPAIR_ITERS` > 0 (`DRT-0073` crash).
- **Optional, the owner's choice:** a Metal4/Metal5 routing obstruction over the receiver (the handoff's optional
  item) to keep digital wires off it entirely. Today only the static `lvds_en` crosses the receiver (Metal4
  over the core; Metal3 and Metal5 in the top margin, two layers above the input strips) and the bottom margin
  carries digital wires; no switching net runs beside the inputs (section 6). Costs routing room; decide before the
  phase-3 run.
- **Branch prepared to replace `main` (2026-11-26, the owner's request), pushed as `origin/lvds-integration`;
  `main` untouched.** The submission files on this branch are the LVDS version: `gds/` and `verilog/` (run
  `acv_lvds5b`; the first push carried `acv_lvds2` with `drc_ready: false`), `info.yaml` (18 pins, the
  description; `drc_ready` and `lvs_ready` true), `lvs_config.json` (+ the receiver's SPICE `macros/lvds_rx_x3/spice/lvds_rx_x3.spice`,
  following the SRAM's pattern: no flatten keys; the organizers' semantics are still question 4 of section 8),
  README (sections I, II.E, V, VII, VIII) and TEST_PLAN (the 7 pads, the LVDS driver and termination, bring-up
  T14-T18). Merging the branch replaces the all-digital submission; leaving `LINK_SEL` unbonded keeps the
  all-digital behaviour on the new chip.
- **Phase 3** (after the official template): drop it in, re-run phase 2 with it (check antenna again), copy
  the new `gds/` and `verilog/` if the layout changes, learning notes. Disk: about 9 GB free; one full run is
  1.4 GB (delete `runs/acv_lvds2` and `runs/lvds_fp2` when no longer needed).
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
> analog pads, and hardened the block on a provisional template we derived from the current frame (Magic and
> KLayout DRC, LVS and XOR clean; timing met at all 9 corners). Our updated `info.yaml` appends 7 pins after
> DVSS, so W12-W22 are unchanged:
> `LINK_SEL` (input_cmos), then `LVDS_SCLK_P`, `LVDS_SCLK_N`, `LVDS_MOSI_P`, `LVDS_MOSI_N`, `LVDS_CSN_P`,
> `LVDS_CSN_N` (all `analog`). We expect them on N01-N07 (pin count 11 -> 18 of the block's 27 slots).
> Could you regenerate our block DEF template and pad map from it? Questions:
>
> 1. Do appended pins land on N01, N02, ... in order, and is 18 pins acceptable for the shuttle?
> 2. Analog pin geometry. Each `asig_5p0` pad presents ASIG5V as eight Metal2 fingers on its core edge, so
>    your rule (pad-terminal Metal2 at the core edge, projected 1 um into the block) would give eight
>    rectangles per analog pin. In LibreLane 3.0.2 that does not route: `Odb.ApplyDEFTemplate` makes each
>    rectangle a separate pin and the detailed router then stops with `[DRT-0302] Unsupported multiple pins on
>    bterm` (power pins are exempt, which is why DVDD/DVSS work). In our provisional template we therefore used
>    ONE rectangle per analog pin, the bounding box of the eight fingers (a 44.32 x 1 um bar, e.g.
>    x 145.34-189.66 um, y 1109-1110 um for N02); the pad's other Metal2 stays 1.61 um away from it. With that
>    the block hardens and signs off (DRC, LVS, XOR clean). Could the official template use the same single
>    rectangle (or tell us which shape you want)?
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

### Short version for a GitHub issue (2026-11-26)

The first three questions above, ready to paste. Title: **A56 / ACV: request for an updated block DEF template
(7 extra pins for an LVDS receiver)**

```markdown
Hi organizers,

For project **A56** (block **ACV**, top `dla_engine_chip`, team FindingSRAM) we have added a small LVDS receiver to the chip. Could you regenerate our block DEF template (and pad map) with the extra pins?

**What changed**
- New hard macro `lvds_rx_x3`: a 3-lane LVDS receiver (gf180mcuD, 3.3 V, 650 x 194 um, Metal1-Metal3 only), placed in a strip of the core that held only standard cells. No other macro moved.
- Its three lanes carry the existing serial link's SCLK, MOSI and CS_N as LVDS pairs into the unchanged serial bridge. A strap pin, `LINK_SEL`, picks CMOS or LVDS; its pad pull-down keeps the original CMOS link when it is left unbonded.
- The 11 existing pins (W12-W22) are unchanged. 7 pins are appended after DVSS in `info.yaml` (11 -> 18 pins), expected on N01-N07:
  - `LINK_SEL` (`input_cmos`)
  - `LVDS_SCLK_P`, `LVDS_SCLK_N`, `LVDS_MOSI_P`, `LVDS_MOSI_N`, `LVDS_CSN_P`, `LVDS_CSN_N` (`analog`)
- On a provisional template we derived from the current ACV frame, the block hardens with Magic/KLayout DRC and LVS clean and timing met at all 9 corners (two antenna nets left to close in the final run).

**Questions**
1. Can you regenerate the A56/ACV template with these 18 pins, and do appended pins land on N01, N02, ... in order?
2. Analog pin shape: the `asig_5p0` ASIG5V terminal has 8 Metal2 fingers. If the template gives an analog pin 8 rectangles, LibreLane's `Odb.ApplyDEFTemplate` makes 8 pins and detailed routing stops with `[DRT-0302] Unsupported multiple pins on bterm`. We used one rectangle per analog pin (the bounding box of the 8 fingers, 44.32 x 1 um), which routes cleanly. Could the official template do the same?
3. Our main branch still holds the signed-off 11-pin GDS. Should we put the updated `info.yaml` on main now, or share it another way until the new GDS is ready?

Thank you!
```
