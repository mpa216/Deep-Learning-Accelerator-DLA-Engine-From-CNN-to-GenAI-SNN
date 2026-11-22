# LVDS receiver macro `lvds_rx_x3`: the complete design record

Written 2026-11-22, at the close of the project (tasks T0 to T13). Branch `lvds-rx`, project folder `analog/lvds_rx/`
(in the main checkout the same folder is `LVDS/lvds_rx_work/`).

This is the whole story in one place: what the macro is, how it was designed, sized, drawn and checked, every bug and
error met on the way and what was done about it, and what is still open. It is written for a reader who is new to
analog design; section 15 explains the technical words. The detailed records it summarises are listed in section 14.
Every number here comes from a committed result file; where two sources differ, the result files win.

## Contents

1. The macro in one page
2. Requirements against results
3. How the circuit works
4. How the macro was made: method and tools
5. Timeline
6. The sizing story: from the first sizing to iteration 2
7. Verification: what was simulated and how it was judged
8. The layout
9. Bugs, errors and surprises
10. Decisions on record (D-001 to D-020)
11. Known limitations and open items
12. Lessons learned
13. By the numbers
14. Where everything lives and how to run it again
15. Glossary

---

## 1. The macro in one page

**What it is.** `lvds_rx_x3` is a *hard macro*: a finished, fixed block of chip layout. It holds three LVDS receivers,
one per lane (CLK, D0, D1), sharing one bias block. It is meant for the chip's fast input link: three differential pad
pairs come in from outside, and the macro turns each pair into an ordinary 3.3 V logic signal for the digital core. It
is drawn in the GF180MCU process (PDK gf180mcuD) with 3.3 V transistors on Metal1 to Metal3 only, so the chip's own
wiring can pass over it on Metal4 and Metal5.

**What a lane does.** `RXk_O = 1` when `RXk_P` is above `RXk_N`, else 0. An LVDS sender drives its two wires in
opposite directions by only about 100 to 450 mV in total, around a *common mode* that may sit anywhere from 0.05 V to
2.35 V. The receiver must tell which wire is higher, quickly (100 Mb/s: a new bit every 10 ns), wherever the pair sits,
and must not chatter on small noise (*hysteresis*). `EN = 0` switches all three lanes and the bias off and holds the
outputs LOW.

*Picture it like this:* two children on a see-saw. The receiver only cares which end is down (the *differential*), not
how high the see-saw's pivot is (the *common mode*). The pivot can move a lot; the tilt is small.

**Where it stands (2026-11-22).** Done and verified, not yet on the chip:

- every test before layout passes: 19 gates, 21,201 simulations over 45 corners and Monte Carlo mismatch;
- the same tests on the layout as drawn (extracted wiring included) pass: no measurement uses more than 23.6 % of its
  margin (the rule allows 30 %);
- the layout is clean (design rules, layout-versus-schematic, antenna, via arrays); the macro is 650 x 194.2 um;
- two audits pass with minor findings (done with scripts that anyone can run again);
- the integration package (GDS, LEF, Liberty, SPICE, Verilog model, known limits) passes 7 of 7 checks.

Placing it on the chip (*integration*, plan phases P7/P8) is a separate step that waits for the owner.

---

## 2. Requirements against results

Final design (iteration 2), worst case over every corner and Monte Carlo sample of each test. "Required" is the frozen
specification (`spec/spec.yaml`, `spec/gates.yaml`); "Achieved" is from `results/REPORT.md` and
`results/post_layout/TBL.md`.

| Requirement | Required | Achieved (worst case) | Test |
|---|---|---|---|
| Data rate | 100 Mb/s per lane; eye open at 200 Mb/s | eye >= 0.973 UI at 100 Mb/s (limit 0.6), >= 0.926 UI at 200 Mb/s (limit 0.5), no bit errors | TB5 |
| Package and board spread | eye >= 0.5 UI for L 1-5 nH, C 0.5-1.5 pF | >= 0.925 UI | TB12 |
| Input common mode | 0.05 to 2.35 V with >= 100 mV differential (TIA/EIA-644-A) | works across the range in every bench (VIC swept 0.05 / 1.2 / 2.35 V and more) | TB1-TB5 |
| Stage-1 gain | >= 4 at the common-mode extremes; spread over VIC <= 2.2x | 4.78; 1.59x | TB2 |
| Bandwidth | each stage >= 0.8 x data rate; chain >= 50 MHz | 0.92 x data rate; 60.7 MHz | TB2 |
| Hysteresis | 6 to 35 mV (the handoff asked 8-25 mV; widened by D-009) | 7.3 to 24.2 mV under mismatch (600 runs); >= 9.1 mV by DC sweep | TB3_hmc, TB3_trip |
| Offset | window (mean + 6 sigma + V_H/2 + 3 mV) <= 95 mV; sigma <= 5 mV | window 39.9 mV; sigma about 3.0 mV (typical) to 3.2 mV (slow, hot) | TB3_off (15,000 runs) |
| Propagation delay | <= 5 ns at 350 mV input, <= 8 ns at 100 mV | 4.54 ns / 5.26 ns; after layout 4.57 ns (ss, 125 C, 3.0 V, 350 mV) | TB4, TBL |
| Delay change | <= 1 ns over common mode; <= 1 ns over VID 200-450 mV | 0.58 ns; 0.30 ns | TB4, TB4b |
| Duty-cycle distortion | <= 5 % UI at 350 mV, <= 10 % UI at 100 mV | 1.0 %; 5.9 % | TB4 |
| Output edge | 10-90 % <= 1 ns into 30 fF | 0.15 ns | TB4 |
| Supply ripple and common-mode steps | added jitter <= 0.1 UI; no false toggles | 0.012 UI; 0 false toggles (D-007: edges that coincide with a 2 ns common-mode step are reported, not gated) | TB6 |
| Idle inputs (open, shorted, terminated) | no oscillation, no pulse < 2 ns | none in 945 + 1500 runs (one settling flip per lane allowed, D-010, D-020) | TB7, TB7_mc |
| Enable and power-up | EN = 0: output <= 0.33 V, supply current <= 1 uA (<= 5 uA at 125 C); EN rising: valid within 1 us; no pulse < 2 ns | 0.262 V; 133 nA (110 nA at 125 C); 28.8 ns; 3.0 ns (D-008, D-011, D-019) | TB8 |
| Input current | <= 20 uA per pin | 2.9 nA | TB9 |
| Three lanes together | skew <= 1 ns; lane-to-lane 3 sigma <= 0.5 ns; crosstalk <= 0.05 UI | 46 ps; 180 ps; 0.0013 UI | TB10 |
| Supply current | <= 1.5 mA per lane, <= 0.3 mA bias | 1.075 mA / 0.256 mA (typical 0.755 / 0.166 mA) | TB1 |
| Saturation margin | >= 50 mV at the seven design corners | 52.5 mV; at the fast, hot, common-mode extremes down to -84.5 mV (allowed to -100 mV, D-012) | TB1 |
| Area | core <= 600 x 150 um, Metal1-Metal3 | core 600 x 144.2 um; macro 650 x 194.2 um with its margin | layout |
| After layout | every metric within 30 % of its pre-layout margin | at most 23.6 % (178 matched pairs) | TBL |

---

## 3. How the circuit works

```
 one lane (x3)                                                                          shared bias block
 -----------------------------------------------------------------------------------    -----------------------
            secondary ESD          stage 1                stage 2           stage 3      Rb -> MBN diode = VBN
 RXk_P --[151 ohm]--+-- gp --+-> PMOS pair + dump --+                                     (NMOS tails, sinks)
                    |        |   (tail mpt, VBP)     |                                   MBS -> MBP diode = VBP
               clamp diodes  |                       +-> fold: m3 sinks,                  (PMOS tail, VB2 branch)
               to VDD / VSS  +-> NMOS pair + dump --+   m5 cascodes (VB2)                MB2P -> MB2 on Rf
                             |   (tail mnt, VBN)     |   loads RL to VDD                    = VB2 (cascode bias)
 RXk_N --[151 ohm]--+-- gn --+                       +-> oa / ob ---------+               Vref = 0.48 VDD divider
                                                                         |                + 2 pF decap
                     NMOS pair ms + Rs, tail mt2, diode + cross-coupled  |                EN: opens Rb branch and
                     PMOS loads (alpha = 6/4): hysteresis comparator  <--+                divider, parks VBN, VBP,
                                         |                                                VB2 and d2a / d2b
                                         d2a / d2b
                                         |
                     PMOS copies mp3 + NMOS mirror mn3: d3 swings rail to rail
                                         |
                     NAND2(d3, EN) -> INV -> INV -> INV (8 / 20 um) -> RXk_O (30 fF)
```

Block by block, in plain words:

- **Secondary ESD (per input).** A 151 ohm poly resistor in series, then two clamp diodes to the supply rails. It
  softens static-discharge spikes that get past the pad's own protection. It is *unqualified*: no discharge test data
  exists for it.
- **Stage 1, the input stage (`lvds_pre`).** No single transistor pair can follow a common mode from 0.05 V to 2.35 V
  on a 3.0 V supply. So there are two: a PMOS pair that works at low voltages and an NMOS pair that works at high
  voltages; in the middle both work. The trick that makes it smooth is the *dump twins*: next to each pair sits a twin
  whose gates are held at Vref = 0.48 VDD. When the input leaves a pair's range, its current flows through the twin
  instead of collapsing, so the gain stays nearly the same over the whole range (spread 1.59x, limit 2.2x). Without
  the twins the gain fell to 0.08 at one corner. The pairs drive resistor loads, so the gain is a ratio of two
  resistors made of the same material, which keeps it steady over temperature and process.
- **Stage 2, the decision with hysteresis (`lvds_hyst`).** A pair with two kinds of loads: plain diode loads and
  cross-coupled loads that push the decision further once it starts (positive feedback). The strength ratio alpha =
  6 fingers / 4 fingers = 1.5 sets how "sticky" the decision is: once the output has flipped, the input must move back
  by the hysteresis (about 13 mV typical, 7 to 24 mV over corners and mismatch) before it flips back, so noise cannot
  make it chatter. Small resistors Rs in the pair's
  sources make the hysteresis follow the stage-1 gain, so the input-referred value stays inside its window across
  corners.
- **Stage 3, to full logic levels (`lvds_out`).** A current-mirror converter turns stage 2's two outputs into one node
  (d3) that swings from rail to rail, then a NAND gate (which also applies EN) and three inverters of growing size
  drive the output pin (30 fF load) with clean 0.15 ns edges.
- **Shared bias (`lvds_bias`).** A resistor Rb from the supply into a diode-connected transistor sets the reference
  current (52 uA typical); mirrors copy it to every lane. It also makes the cascode voltage VB2 and Vref = 0.48 VDD (a
  resistor divider with a 2 pF capacitor). EN = 0 opens these branches and parks every internal node, so the macro
  draws almost nothing (133 nA worst).

Typical current: 0.755 mA per lane and 0.166 mA for the bias, about 2.4 mA for the whole macro at 3.3 V.

What the macro deliberately does **not** do in this first version (v0): *failsafe* (a defined output when no sender is
connected; the output stays stable but may be 0 or 1) and *under-voltage lockout* (the system holds EN low until the
supply is above 2.0 V). Both are in section 11.

The circuit is written device by device in `netlist/lvds_circuit.py`; the reasons for every size are in
`DESIGN_GUIDE.md` section 3 and `sizing/sizing_report.md`.

---

## 4. How the macro was made: method and tools

### 4.1 Principles that shaped the work

1. **The referee before the player.** Before any circuit existed (task T0), the pass/fail rules were written and
   frozen: `spec/spec.yaml` (what the receiver must do), `spec/gates.yaml` (how each test is judged: metric, limit,
   corners, number of runs), `spec/pins.yaml`, `spec/paths.yaml`, with their sha256 in `spec/FREEZE.json`. Changing any
   of them later needs a dated entry in `spec/decisions.yaml` carrying the new hash; the lint check fails otherwise.
2. **A pre-planned fallback ladder.** Nine "ladders" (R1 data rate ... R9 power) list in advance which requirement may
   be relaxed by how much if the design cannot meet it. Taking a rung is allowed and recorded; anything outside the
   ladder is a *waiver* that needs reasons, and after results exist, the owner's decision.
3. **One source of truth per thing.** One sizing script writes every device size; generators write the netlists from
   it; the layout reads the same device table. Nothing is copied by hand.
4. **A test passes only if it really ran.** A gate passes only if every run finished and the number of runs equals
   the number the plan requires (corners x conditions x Monte Carlo samples). A failed measurement is a failure, never
   a silent skip.
5. **Test the tests.** *Mutation tests* deliberately break things (a missing run, a loosened limit, a shrunken input
   pair, swapped input wires ...) and check that the gates notice. All 11 are caught.
6. **Small committed steps.** Each piece of work ends in a commit, so a crash or interruption loses little.

### 4.2 Tools

| Tool | Used for |
|---|---|
| Docker container `apic_headless` | every EDA tool, reached through `tools/cx` |
| PDK gf180mcuD (GF180MCU, 3.3 V devices) | transistor and resistor models, design rules, pad cells |
| ngspice-46 | all circuit simulation (DC, AC, transient, Monte Carlo) |
| Python with numpy / matplotlib / pygmid | sizing, netlist generators, the simulation harness, measurements, plots, layout generators |
| Jespers & Murmann gm/ID method and lookup tables | sizing (the book with its errata; tables regenerated on this PDK) |
| Magic 8.3.636 | drawing the layout from scripts, extraction (PEX) |
| KLayout 0.30.8 | the foundry design-rule and antenna decks (the real DRC check), pictures |
| Netgen | layout versus schematic (LVS) |
| OpenROAD / OpenSTA | package checks (the LEF and Liberty load and time correctly) |

### 4.3 The flow, step by step

1. **Foundation (Phase 0).** Facts about the PDK measured, gm/ID lookup tables regenerated (bit-identical to the
   reference kit, then extended), the pad modelled, the simulation harness built, and a small amplifier laid out end
   to end by script to prove the layout flow.
2. **Frozen criteria and gate machinery (T0).**
3. **Risk first (T1).** The riskiest idea, the stage-1 dump twins, was tested alone with ideal bias before any other
   sizing.
4. **Sizing script and netlists (T2).** `sizing/lvds_rx_sizing.py` sizes every device by the gm/ID method and checks
   itself with 128 assertions; it writes `sizing/sizes.spice` (stamped with a hash of the script), the device table
   for layout and a report.
5. **Testbenches (T2 to T4).** TB0 to TB12, each a deck plus a JSON spec plus a small Python hook, run by the harness
   over corners and Monte Carlo seeds; first a quick *smoke tier*, then the *full tier*.
6. **Full regression, audit, freeze (T5 to T7).** Everything at the full tier, an audit of the whole pre-layout
   result, then the sizing frozen (`sizing/FROZEN.md`).
7. **Layout library (T8).** Python that writes Magic scripts: transistor rows (matched pairs, interleaved mirrors,
   pairs with dump twins), resistor arrays, the ESD cell, a router that refuses shorts and spacing errors before
   drawing, and per-cell checks (DRC, antenna, strict LVS, finger order read back, deliberate faults detected).
8. **Lane, then macro, then extraction (T9, T10).**
9. **Post-layout re-simulation (T11).** The benches re-run on the extracted layout and compared with the pre-layout
   results (gate TBL); three design iterations; the final audit.
10. **Package (T12) and close (T13).**

### 4.4 How the work was organised

The work ran on the owner's machine in scripted sessions, with at most four simulations at a time (the owner's
choice). The foundation and tasks T0 to T5 (with the layout library, T8) were done mostly by single-purpose agents,
each ending in a report; after a PC crash in T5 (section 9.4) the rest, from closing T5 to T13, was done by one session
working in small committed pieces. The owner gave the go-ahead at each
layout milestone, asked for pauses when the machine was needed, and decided the two test-definition questions that
came up after results existed (D-019, D-020). Everything else was decided inside the frozen rules and recorded in
`spec/decisions.yaml` and `DESIGN_LOG.md`.

---

## 5. Timeline

| Date | Task | What happened |
|---|---|---|
| October 2026 | plan | The handoff plan (`LVDS/HANDOFF_FOR_CLAUDE.md`) and the owner's background guide (`LVDS/GUIDE_FOR_YOU.md`) were written. |
| 2026-11-07 | evaluation | Feasibility and pin cost of an LVDS link for the chip. |
| 2026-11-10 | go-ahead | The owner asked for the complete receiver, schematic to layout, with as little human involvement as possible. |
| 2026-11-10/11 | Phase 0 | Plan reviewed from three angles (circuit, automation, layout); tools proven; `PLAN_V2.md` written. |
| 2026-11-11 | T0-T3, T8 | Frozen criteria; stage-1 spike passes; first sizing and netlist; benches TB1-TB5 and TB12 at the smoke tier; layout library with 29 leaf cells. |
| 2026-11-12 | T4, T5 | Benches TB6-TB10. First full regression: 7.8 h, 13 gates pass, 6 fail; fixes D-009 to D-014. A PC crash killed the final regression three hours in. |
| 2026-11-13 | | Resumed with four parallel simulations. |
| 2026-11-14 | T5-T7, T9, T10 | Full tier green (17 gates, 21,017 runs); audit 1 passes; sizing frozen; one lane, then the whole macro laid out and extracted. |
| 2026-11-15 | T11 | The extracted layout misses the delay limit (6.76 ns against 5 ns): iteration 0 fails. A Magic extraction bug found and repaired. Iteration 1 designed and redrawn. Branch pushed to GitHub (66d34d0). Paused. |
| 2026-11-20/21 | T11 | Iteration-1 regression (restarted after a container kill): the hysteresis Monte Carlo fails. Iteration 2 (D-017, could not be drawn, corrected by D-018). Post-layout suite: only two power-up checks fail; the owner chooses waiver D-019. |
| 2026-11-22 | T11-T13 | D-019 applied; full regression flags one idle run; the owner chooses D-020; final audit; package; closing regression and layout re-run; project closed. |

---

## 6. The sizing story: from the first sizing to iteration 2

### 6.1 The first sizing (T2, 2026-11-11)

The gm/ID method picks, for every transistor, an inversion level (gm/ID) and a length, reads the current density from
the lookup tables, and sets the width from the current. Key choices:

- **Resistor-diode bias:** the reference current is (VDD - VGS) / Rb. Gain and hysteresis are ratios of the same poly
  resistors, so most of the corner spread cancels. The stage-1 load drop VR was set to 1.23 V at typical (raised from
  the spike's 1.0 V) to keep the gain >= 4 at the slow, hot corner, where it falls 14 %.
- **Source resistors in stage 2:** a plain hysteresis pair would spread 4:1 over corners against a 3:1 window; a
  resistor in each source adds a term that follows the gain and cancels most of that.
- **Current-mirror stage 3:** the original plan's converter could not pull its output low enough.

First run: **11 of the sizing assertions failed** (hysteresis spread 4.4:1, a fold pole too close, a mirror without
headroom at a corner); fixed by the stage-2 resistors, a cascode gm/ID of 13, a slightly higher VR and a mirror gm/ID
of 7.5. The first simulation then found one input transistor with 45 mV of margin where the script had predicted
110-150 mV: the script had used the half-current case and the nominal input. Fixed, and the fold voltage lowered from
0.54 to 0.46 V. Result at typical: reference 52 uA, tails 107/105 uA, gain 8.0 / 8.4, lane current 545 uA.

### 6.2 Tuning before the freeze (T2 to T5)

- Stage-3 mirror length 0.5 -> 0.28 um: its pole was 39 MHz at the slow corner, below the 80 MHz needed.
- VR 1.25 -> 1.17 V (D-013): the NMOS pair slipped out of saturation at 2.35 V common mode at hot, 3.0 V corners.
- Hysteresis window 8-25 mV -> 6-35 mV (D-009, ladder R3 rung 1): the hysteresis Monte Carlo fell below 8 mV at the
  fast, cold, 3.6 V corner twice.
- Saturation-margin waiver at the fast, hot common-mode extremes (D-012), with a condition: re-check gain and timing
  there after layout (met later: gain 4.78, delay 2.48 / 3.10 ns).
- The offset gate tightened from 8 mV to the 5 mV design sigma (D-014), because a mutation test with a four-times
  smaller input pair still passed the looser gate.

Then T7 froze the sizing (`sizing/FROZEN.md`).

### 6.3 Iteration 0: the layout was a third slower (T11, 2026-11-15)

The first extracted layout failed gate TBL outright at the slow corner (ss, 125 C, 3.0 V): delay 4.57 -> 6.76 ns
against 5 ns at 350 mV input and 5.55 -> 8.22 ns against 8 ns at 100 mV; chain bandwidth 56 -> 37 MHz; delays +46 to
49 % everywhere. The cause was in the pre-layout netlist, not the drawing: it had no wiring capacitance at all (the
sizing only assumed 10 fF on two nodes; the layout has 27.6 fF there) and modelled transistor junctions with 0.18 um
of diffusion per side where the layout has about 0.27 um. The frozen design had 9.5 % of delay margin for none of
that load.

### 6.4 Iteration 1 (D-016): model the layout, then speed up stage 2

1. A **layout parasitic estimate** went into every simulation netlist: 31 nets, extracted wiring times 1.2, calibrated
   on 36 extracted delay points (at scale 1.2 it is at least the real extraction at 35 of 36).
2. **Stage 2 re-sized:** twice the tail current (`n_t2` 5 -> 10), a smaller, faster input pair (`gmid_s2` 12 -> 8),
   shorter loads (0.40 -> 0.28 um). Delay at the slow corner with the estimate: 4.50 ns.
3. Redrawn and extracted: lane delays 3.71 ns (5.36 ns at iteration 0).

But the iteration-1 regression failed the hysteresis Monte Carlo: 17 of 600 runs below 6 mV at ff, -40 C, 3.6 V
(mean 8.3-8.6 mV, spread 15-22 % of the mean). The faster loads had made the hysteresis more sensitive to transistor
mismatch.

### 6.5 Iteration 2 (D-017, corrected by D-018): make the hysteresis robust

How strongly mismatch moves the hysteresis depends on the feedback ratio alpha: the sensitivity is 2 alpha /
(alpha^2 - 1), 4.4 at alpha 1.25 and 2.4 at 1.5. D-017 chose alpha 1.4 with 1.6 um fingers, but **that sizing could
not be drawn**: the layout generator needs fingers of at least 1.81 um when a row carries three source/drain nets, and
its interleaved mirror takes at most two devices with an odd finger count. D-018 settled on:

- alpha 1.5 = 6 / 4 fingers, load fingers 1.85 um;
- Rs 5 um wide (365 ohm; a 2 um wide resistor this small would be shorter than the 1 um minimum);
- the resistor end resistance modelled as 1/W (it had been a constant 85 ohm per end);
- `vh_scale` 1.08 to calibrate the script's hysteresis target against simulation.

Result: the Monte Carlo spread fell to 7-11 % of the mean; hysteresis 600 of 600 runs inside 6-35 mV (7.3-24.2 mV);
lane delay after extraction 3.50 ns; the lane grew slightly and the macro became 650 x 194.2 um.

### 6.6 The final sizing in brief (typical corner)

| Block | Key devices |
|---|---|
| Bias | Rb 45.4 kohm, reference 52.4 uA; NMOS diode 12.5/1.0 um x 5; PMOS diode 55/1.0 um x 11; Vref divider 42.9 / 39.4 kohm with 2 pF |
| Stage 1 | PMOS pair and dump twins 105.6/0.4 um (22 fingers), 53.7 uA each, gm/ID 15; NMOS pair and twins 47.5/0.5 um (10), gm/ID 16; loads RL 9.40 kohm; VR 1.17 V |
| Stage 2 | tail 125.8 uA; pair 8.74/0.5 um; Rs 0.37 kohm; diode loads 7.4/0.28 um (4 fingers); cross-coupled loads 11.1/0.28 um (6 fingers) |
| Stage 3 and output | PMOS copies 14.8/0.28 um; NMOS mirror 4.66/0.28 um; NAND2 + three inverters up to 8/20 um |

The complete tables are `DESIGN_GUIDE.md` section 3 and `sizing/sizing_report.md`.

---

## 7. Verification: what was simulated and how it was judged

### 7.1 The testbenches

| Bench | Question it answers |
|---|---|
| TB0 | the analog pad: capacitance (0.88-1.15 pF) and leakage |
| TB1 | operating point: is every transistor where the sizing said (LUT vs SPICE within 2.9 % in gm/ID, 3.5 % in current, 8.6 mV in VGS), headroom, currents |
| TB2 | small-signal gain and bandwidth |
| TB3_trip / TB3_off / TB3_hmc | trip points and hysteresis; input offset under mismatch (1000 samples per condition); hysteresis under mismatch |
| TB4 / TB4b | delay, duty cycle, edges; delay against input swing |
| TB5 / TB12 | eye diagram and bit errors with a PRBS7 pattern through pad, package and termination; package spread |
| TB6 | supply ripple, current spikes, common-mode steps during data |
| TB7 / TB7_mc | idle inputs, without and with mismatch |
| TB8 | enable and supply ramps |
| TB9 | input current |
| TB10 | three lanes together: skew, crosstalk |
| TB11 | bias loop stability (not applicable: the constant-gm loop was never needed) |
| TBL (`sim/tbl_*`) | the extracted layout against the pre-layout results |

**Corners.** Five process corners (tt, ss, ff, fs, sf) x three temperatures (-40, 27, 125 C) x three supplies (3.0,
3.3, 3.6 V) = 45, plus resistor cross corners where they matter. **Monte Carlo** adds random transistor mismatch:
15,000 offset runs, 600 hysteresis runs, 1500 idle runs.

### 7.2 How results are judged

- A *gate* per bench: every run ok, the exact run count, every metric inside its limit (`flow/gates.py`).
- **Gate TBL** (post-layout): the extracted layout may use at most 30 % of each metric's margin; gains of margin over
  30 % are listed and explained rather than failed. Final: 178 matched pairs, at most 23.6 %.
- **Hash audit** (`tools/audit_hashes.py`): every stored result must come from the current design files.
- **Mutation tests** (`flow/mutants.py`): 11 deliberate faults, all caught.
- **Audits:** `results/AUDIT_1.md` (before layout) and `results/AUDIT_2.md` (final): both PASS with findings.

### 7.3 The final record

The closing regression (2026-11-22, `tools/run_full.sh 4`): 19 gates PASS, TB11 not applicable, 21,201 gated runs,
every stored result unchanged, hash audit clean, 11 of 11 mutants caught. Gate TBL PASS, gate LAYOUT PASS, package
all_ok.

---

## 8. The layout

- **Floorplan.** The macro is 650 x 194.2 um: a 600 x 144.2 um core with a 25 um margin. Three identical lanes sit
  under the RX pins (centred at x = 100, 300 and 500 um, as the frozen pin plan fixes); the bias block takes the
  53 um east of lane 2. The RX pins are on the top edge (pad side, Metal3); EN and the three outputs on the bottom edge
  (core side).
- **Cells.** Lane `lvds_lane` 142.8 x 126.4 um; bias block `lvds_bias` 53.2 x 141.1 um. 158 devices in the reference
  netlist of the macro; the layout adds *dummy* devices (46 in each lane, 22 in the bias block) that keep matched
  devices at the ends of rows in the same surroundings as those in the middle.
- **Generated, not drawn by hand.** `layout/lib/` builds every row from `layout/device_table.json`: matched pairs in
  ABBA order, interleaved mirrors, pairs with their dump twins, resistor arrays (long resistors as snakes of equal
  pieces), the ESD cell, the Vref capacitor; a grid router; a power-strap planner; mirrored generation for the
  symmetric half.
- **Checks on every cell.** KLayout foundry deck (0 main, 0 antenna), Magic DRC on a flattened copy (0), via-array
  rule (0), strict Netgen LVS (unique match, no property or port errors), finger order read back from the extraction,
  and negative controls (wrong width, cut wire, Metal3 bridge, rule sliver: each must be detected). 32 leaf tests.
- **Symmetry.** Input-net capacitance balance INP / INN 0.16 %, gp / gn 0.60 % (limit 2 %; measured on the lane in T9).
- **Extraction (PEX).** A C-only and an RC netlist of the whole macro, flat (10,601 resistors and 5,813 capacitors in
  the RC netlist; 2842.6 fF of wiring capacitance after the repair of section 9.1).

---

## 9. Bugs, errors and surprises

Everything that went wrong, how it showed up, and what was done. Grouped by where the fault was.

### 9.1 Tool and PDK traps

| What | How it showed up | What was done |
|---|---|---|
| Magic 8.3.636 `extresist` counted every coupling capacitance twice in the RC netlist | post-layout delay too slow; the RC netlist carried 4304 fF of wiring C against 2843 fF in the C-only one; one n-well node lost its 103 fF | `check.rc_repair()` takes the capacitance from the C-coupled extraction and keeps the RC network (every net-pair total within 3e-6) |
| Magic DRC on a hierarchical cell counts subcell errors several times; its total never matched its list | inconsistent DRC counts on the macro | DRC is run on a flattened copy |
| Magic `getcell` places an instance by its bounding box unless the child's origin is named | macro instances shifted | origin named explicitly |
| Magic merges wire pieces that carry the same label | a deliberately cut wire still "matched" in LVS | unique labels per segment (`NET.k`); plain names only on pins |
| Cutting only the Metal2 pad of a via stack does not open the net in Magic | an open-circuit negative control passed | the control cuts the via itself |
| Magic read bare contacts left in a diode marker as 640 diodes | wrong device count in the antenna run | contacts removed with the diode plates |
| Magic DRC misses some foundry rules | a toy layout clean in Magic failed KLayout | the KLayout foundry deck is the real check |
| Netgen prints "match uniquely" even when device sizes differ | LVS looked clean with wrong sizes | the LVS script also fails on property errors |
| The PDK's MOS-capacitor generator draws a varactor that vanishes when the GDS is read back and breaks two rules | Vref capacitor missing in extraction | the capacitor is drawn as an NMOS with source = drain = VSS (and the LVS reference says so) |
| 0.28 um logic transistors: the gate-pad corner sits 0.209 um from the next contact (rule 0.23 um) | DRC error on small devices | contact bars trimmed; one inverter drawn with two fingers |
| Magic cannot draw deep n-well | | v1 uses none |
| ngspice needs every statistics parameter set explicitly | "Undefined parameter" | the harness header sets them |
| Without `.option wnflag=1` the model picks its size bin from the total width | 9.9 % gate-capacitance error against the tables | wnflag set in every deck |
| `op` does not converge on this latching circuit | no operating point | every deck ramps the supply, with a 100 Gohm shunt |
| ngspice evaluates subcircuit lines even inside a false `.if` | a "not implemented" guard misfired | the guard is a resistor with an undefined value |
| ngspice stalls (picosecond steps for ever) when a model quantity decays into the denormal range | settled runs hung (TB7, TB8) | `.option reltol=0.01` on those benches (D-006); any edit of a deck can move the stall |
| ngspice hang with a static input before the supply is up | all slow-corner delay runs timed out | the stimulus ramps up with the supply |
| "Timestep too small" with an input pin at -0.125 V | TB5 at VIC 0.05 V, 350 mV | both pins kept inside 0-2.4 V (D-005) |
| First operating point stalls at VDD 0.3 V | 4 of 270 TB3_trip runs (iteration 1) | retry variants that change solver options only (D-017) |
| A 10 us settled tail stalled ngspice at four corners in every solver variant | TB8 case 7 timeouts | the case ends 0.2 us after its ramp (D-019) |
| ngspice's OpenMP build grabs every core per run | 7.3 s at 639 % CPU instead of 4.0 s | one thread per run (`OMP_NUM_THREADS=1`) |
| A matched device written as `m=4` copies shares one random mismatch draw | offset 6.79 mV instead of 3.3 mV | matched devices always use fingers (`nf`); a lint rule enforces it |
| Interpolating the lookup tables between lengths | up to 22 % (NMOS) and 47 % (PMOS) error in output conductance | lengths only from the table grid |
| The book PDF is the uncorrected printing | three equations wrong | corrected from the errata |
| Magic writes the current date into every GDS and numbers RC nodes differently on each run | a layout re-run never matches byte for byte | equality defined and checked by `tools/gds_same.py`, `tools/same_netlist.py`, `tools/compare_layout_rerun.py` (T13) |

### 9.2 Errors in our own flow, benches and measurements

| What | How it showed up | What was done |
|---|---|---|
| The pre-layout netlist had no wiring capacitance and too little junction area | iteration 0 failed delay by a third after layout | calibrated parasitic estimate in every simulation (D-016) |
| The sizing script did not know two limits of the layout generator | the D-017 sizing could not be drawn; one iteration lost | D-018; recorded as finding F8 (asserts to add at the next sizing change) |
| Resistor end resistance modelled as a constant 85 ohm per end | latent: wrong only for non-2 um widths | modelled as 1/W (D-018) |
| TB8's pulse rule took every pair of 50 % crossings as a pulse | a 3 ns runt read as a 0.084 ns pulse; TB8 failed | counts completed swings, as its own description says (D-019, finding F14) |
| TB8 never tested EN = 0 on the specified supply ramps | a coverage gap; the extracted off-state was 0.363 V on a 50 ns ramp that is not a spec ramp | new cases 6 and 7 on the 1 us and 100 us ramps, gated (D-019, F15) |
| TB8 asked for an under-voltage lockout the design does not have | output HIGH at 1.9 V with EN = 1 | gate EN = 0 at 1.9 V; EN = 1 reported; integration rule "EN low until VDD >= 2.0 V" (D-008) |
| TB8 pulse just under 2 ns during the bench's own setup ramp | 10 of 251 runs at 1.987-2.000 ns | judged from 100 ns, after the setup ramp (D-011) |
| TB7 called a single power-up settling flip an oscillation | 4 of 1500 runs | one flip per lane allowed, finished by 500 ns (D-010) |
| A settling flip 0.76 ns before TB7's window read as a crossing-free wobble | 1 of 1500 runs after iteration 2 | crossings counted from 5 ns before the window (D-020, F17) |
| TB6 counted edges that coincide with a 2 ns common-mode step | jitter 0.13-0.25 UI against 0.1 | those edges reported, not gated; no false toggles anywhere (D-007) |
| The offset measurement point was biased by +5.5 mV | offset did not match the hysteresis centre | measured at the stage-2 balance point |
| The harness called a run non-converged when ngspice recovered after a "gmin stepping failed" message | false failures | harness 1.2 |
| The harness cache key depends on a file the previous run left behind | a run simulated once is simulated once more (identical result) | open, low (F2); `tools/audit_hashes.py` is the staleness test |
| `run_all.py --stage gates` printed PASS for results from an older sizing | seven benches showed PASS from the old design | hash audit inside `tools/run_full.sh`; a stale result fails the run (F4, D-017) |
| A mutant reported a false survivor; another real mutant survived | `frozen_edit` test broken; `offset_area_div4` passed the 8 mV gate | test repaired (F3); offset gate tightened to 5 mV (D-014) |
| LVS references not regenerated after a sizing change | layout would have been compared with old resistor lengths | regenerated; the rebuild is now part of the audit (F1) |
| `check.magic_drc` compared totals with per-rule counts | a leaf test failed on a negative difference | counts the rules off the allow-list (F9) |
| The post-layout runner logged a parallel run's wall time when it joined it | a 5.3 h figure that was the other benches' time | logs the run's own time (F11) |
| Plots and report text lagged behind decisions | histograms drew the old 8-25 mV window; the sizing report describes the first sizing | plots fixed (F6); report text open (F13) |
| Early sizing mistakes | a corner variant with sinks reduced instead of increased; a margin computed for the wrong current | fixed in T2 |
| An odd dump unit under one gate strap | input-net capacitance 3.4 % unbalanced (limit 2 %) | the odd unit moved to the other side: 0.60 % |
| Router corner cases | stubs 0.15 um apart, pins at the wrong height, rails | rejected before painting; fixed in T8 |
| The briefing page quoted the regression as about 19,000 runs | found while writing the T13 gallery | corrected to 21,201 |

### 9.3 The circuit missing a requirement (design iterations)

| When | Missed | Cure |
|---|---|---|
| T2 | 11 sizing assertions | stage-2 source resistors, cascode and mirror gm/ID, VR |
| T5 | NMOS pair out of saturation at 2.35 V, hot | VR 1.25 -> 1.17 V (D-013) |
| T5 | hysteresis under 8 mV at ff, -40 C, 3.6 V | window 6-35 mV (D-009, a pre-planned rung) |
| T5 | saturation margin at fast, hot extremes | waiver with a post-layout condition (D-012, met) |
| T11 iteration 0 | delay after layout (6.76 ns against 5 ns) | iteration 1 (D-016) |
| T11 iteration 1 | hysteresis Monte Carlo (17 of 600 under 6 mV) | iteration 2 (D-017, D-018) |
| T11 iteration 2 | with EN = 0 and the supply below about 1.2 V no output stage conducts, so the outputs float to about a third of the supply | known limitation, the integration rule of D-008 covers it (D-019) |

### 9.4 Incidents on the way

- **Usage limits** stopped the agents twice on the first day; work resumed from checkpoints.
- An early agent **overwrote one cached file in the reference folder** `Analog/` (`techsweep_nfet_03v3.spice`). The
  original is kept in `lut_regen/decks/kit_original/`; nothing reads that file.
- Simulations ran slowly while another job shared the machine (65 s per eye run at six jobs).
- **PC crash, 2026-11-12, about 17:40:** it killed the T5 agent three hours into its final regression, before any
  report or commit. The state was reconstructed from files (`log/T5_state.md`, AUDIT_1 F5), and the owner's feedback
  was to split such big tasks into small single-purpose ones.
- The 7.8 h first regression spent two thirds of its time on 15,000 offset runs and on 19 stalled simulations each
  waiting out a 30-minute timeout; shorter timeouts and resuming from finished benches cut the rest to about four
  hours. More parallel jobs would not have helped: the machine has four physical cores.
- **Container killed, 2026-11-20,** in the middle of a regression; the buffered log was lost. Logs are unbuffered since.
- **Machine restart, 2026-11-22:** the container was started again; nothing was lost (finished runs are cached).

---

## 10. Decisions on record (D-001 to D-020)

Kinds: *note* (a choice the plan left open, no limit changed), *rung* (a pre-planned relaxation), *waiver* (a test
definition changed with reasons; after results exist, the owner decides).

| ID | Date | Kind | What it decided |
|---|---|---|---|
| D-001 | 11-11 | note | how the plan's open points became countable gates (e.g. the extra bench TB4b) |
| D-002 | 11-11 | note | the stage-1 dump-device input stage works (spike result) |
| D-003 | 11-11 | note | first sizing choices: resistor-diode bias, stage-2 source resistors, current-mirror stage 3 |
| D-004 | 11-11 | note | TB1 / TB2 benches and the PMOS-only shake-down |
| D-005 | 11-11 | note | T3 bench definitions (input pins kept inside 0-2.4 V) |
| D-006 | 11-12 | note | T4 bench definitions (reltol 0.01 against ngspice stalls) |
| D-007 | 11-12 | waiver | TB6: edges that coincide with a common-mode step reported, not gated |
| D-008 | 11-12 | waiver | TB8: no under-voltage lockout; EN = 0 at 1.9 V gated; hold EN low until VDD >= 2.0 V |
| D-009 | 11-12 | rung | hysteresis window 8-25 -> 6-35 mV (ladder R3 rung 1) |
| D-010 | 11-12 | waiver | TB7: one settling flip per lane allowed, finished by 500 ns |
| D-011 | 11-12 | waiver | TB8: pulses judged after the bench's setup ramp |
| D-012 | 11-12 | waiver | saturation margin at the fast, hot extremes, with a post-layout condition (met) |
| D-013 | 11-12 | note | the first full regression and its fixes (VR 1.17 V, corner tables, harness retries) |
| D-014 | 11-12 | note | offset gate tightened to 5 mV (a mutant had survived) |
| D-015 | 11-14 | note | gate TBL defined (30 % of margin) |
| D-016 | 11-15 | note | iteration 1: parasitic estimate and stage-2 re-size |
| D-017 | 11-21 | note | iteration 2: alpha 1.4 (could not be drawn); retry variants; hash audit in the regression |
| D-018 | 11-21 | note | iteration 2 as built: alpha 1.5, Rs 5 um wide, 1.85 um fingers |
| D-019 | 11-22 | waiver | TB8 power-up: off-state after the setup ramp, completed swings only, new EN = 0 spec-ramp cases; TBL wake-up pulse worst against worst (the owner's choice) |
| D-020 | 11-22 | waiver | TB7: idle-window crossings counted from 5 ns before the window (the owner's choice) |

Full text: `spec/decisions.yaml`; the audits' rulings: `results/AUDIT_1.md`, `results/AUDIT_2.md` (all accepted).

---

## 11. Known limitations and open items

Listed for the integrator in `package/KNOWN_LIMITS.json`:

- **ESD:** the secondary ESD cell has no discharge (HBM / CDM) or latch-up qualification.
- **Failsafe off (v0):** with no sender connected the output is stable and never oscillates, but may rest at 0 or 1.
- **No under-voltage lockout:** keep EN low until VDD >= 2.0 V (D-008).
- **Low-supply off-state:** with EN = 0 and the supply below about 1.2 V the outputs float to about a third of the
  supply (up to 0.316 V on the 1 us ramp after layout, 14 mV under the 0.33 V limit); keep the logic that reads
  RXk_O in reset until the supply is up (D-019).
- **Unpowered inputs:** the pad's own ESD diode conducts into an unpowered supply from about 0.58 V.
- **Assumptions:** package and board values (50 ohm source, 3 nH, 0.7 pF) and the pad-slot x positions are assumed,
  not measured.
- **No timing arcs** in the Liberty: the outputs are asynchronous and must be captured through synchronizers.
- **Hysteresis window** 6-35 mV instead of the handoff's 8-25 mV (D-009).

Open, each needing the owner:

- **Chip integration** (plan phases P7/P8): placing the macro, chip-level DRC / LVS, and the handoff's items 15-18
  (clocks and input delays on macro output pins in OpenSTA / OpenROAD, whether `RSZ_DONT_TOUCH_RX` stops port
  buffering, the analog template geometry and slot, the LVS key semantics).
- **Version 1 work:** failsafe, ESD qualification, latch-up checks.
- **Small audit findings:** F2 (harness cache key), F8 and F13 (two sizing assertions and the report text, at the next
  sizing change).
- Optional: restore the overwritten kit file in `Analog/` from `lut_regen/decks/kit_original/`.

---

## 12. Lessons learned

1. **Freeze the rules first.** Every relaxation became visible, and the two that came after the results went to the
   owner as explicit choices with their costs.
2. **Count the runs and test the tests.** A gate that only checks the runs that exist can pass a half-finished job;
   one mutant showed a limit that was too loose.
3. **Model the layout before drawing it.** A netlist without wiring capacitance under-estimated every delay by a
   third. A parasitic estimate calibrated on a first extraction fixed it for good.
4. **Teach the sizing what the layout can build.** One iteration was lost to two generator limits the sizing script
   did not know.
5. **Robust beats nominal.** The hysteresis was right at typical every time; what failed was its sensitivity to
   mismatch, and the cure was a stronger feedback ratio, not a different target.
6. **Measurement code is part of the design.** A pulse rule, an offset definition and a window edge each produced a
   false failure; each was found by looking at the waveform, not the number.
7. **Simulators stall; plan for it.** Timeouts, retry variants that change solver options only, and a record of each.
8. **Check tools against each other.** Two DRC engines, LVS with property errors, and extraction totals cross-checked
   (that is how the double-counted coupling capacitance was caught).
9. **Define "the same" before re-running.** Byte equality never holds for regenerated layout files; record equality
   and netlist-element equality do.
10. **Commit small, log unbuffered.** A PC crash and a container kill cost minutes, not days.

---

## 13. By the numbers

| Quantity | Value |
|---|---|
| Calendar time | 12 days from the go-ahead (2026-11-10) to the close (2026-11-22); commits on 7 of them |
| Commits | 74 touching the project before this record (11-11: 10, 11-12: 4, 11-13: 1, 11-14: 28, 11-15: 9, 11-21: 14, 11-22: 8) |
| Code | 140 Python files, 20,747 lines (sizing, generators, harness, bench hooks, layout library, checks, package) |
| Benches | 27 bench folders under `sim/` and 9 post-layout ones (`sim/tbl_*`); 32 layout leaf tests |
| Final full tier | 21,201 gated simulations (15,000 of them offset Monte Carlo), 19 gates |
| Post-layout | 178 matched pre-layout / extracted pairs |
| Machine time | first full regression 7.8 h; a post-layout suite about 5-6 h (the extracted three-lane run alone 2.5 h); the iteration-2 regression 2.1 h; the closing regression 13 min (from the cache) |
| Decisions | 20: 12 notes, 1 ladder rung, 7 waivers (2 of them chosen by the owner after results) |
| Design iterations | first sizing, tuning to the freeze, then iterations 0, 1, 2 after layout |
| Layout | 650 x 194.2 um; 158 devices plus dummies (46 per lane, 22 in the bias block); RC extraction 10,601 R and 5,813 C |

---

## 14. Where everything lives and how to run it again

**Documents** (in `analog/lvds_rx/`):

| File | What it holds |
|---|---|
| `LVDS_RX_DESIGN_RECORD.md` | this record |
| `DESIGN_GUIDE.md` | architecture, every size and why, which knob moves which spec |
| `DESIGN_LOG.md` | the dated log, task by task, with numbers |
| `CARRY_ON_GUIDE.md` | how to run and continue the project |
| `PLAN_V2.md` | the plan that was executed (spec, architecture, verification, layout, tasks T0-T13) |
| `log/T*_report.md`, `log/T11_notes.md` | per-task reports and the working notes of T11 |
| `results/AUDIT_1.md`, `results/AUDIT_2.md` | the two audits |
| `results/REPORT.md`, `results/gates.json` | the final regression |
| `results/post_layout/TBL.md` | the post-layout comparison |
| `package/README.md`, `package/KNOWN_LIMITS.json` | what the integrator receives |
| `docs/figures/index.html` | picture gallery: schematics, waveforms, eyes, histograms, layout |

**Sources:** `spec/` (frozen criteria, decisions), `sizing/` (sizing script, sizes), `netlist/` (generators and
netlists), `sim/` (harness, benches, results), `layout/` (library, leaves, lane, bias, macro), `flow/` (gates,
report, lint, mutants), `tools/` (container wrapper, regression and audit scripts), `package/`.

**Commands** (from `analog/lvds_rx/`, with
`CX="docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx"`):

```bash
$CX make check                              # environment, LUT self-test, harness tests, lint
$CX bash tools/run_full.sh 4                # full pre-layout regression (hours from scratch, minutes from the cache)
$CX python3 sim/tbl/run_tbl.py --jobs 4     # post-layout suite, then the evaluator (gate TBL)
$CX make layout                             # every leaf, the lane, the bias block, the macro and its PEX
python3 tools/compare_layout_rerun.py       # after a layout re-run: the same layout apart from date stamps?
$CX make package                            # build and check the integration package
python3 flow/gates.py --tier full           # gate table again;  python3 flow/report.py  writes results/REPORT.md
$CX python3 tools/audit_hashes.py --tier full   # are all stored results from the current files?
```

---

## 15. Glossary

| Word | Meaning |
|---|---|
| LVDS | Low-Voltage Differential Signalling: data sent as a small voltage difference between two wires, fast and quiet |
| Differential (VID) | the difference between the two wires; at least 100 mV here |
| Common mode (VIC) | the average level of the two wires; 0.05 to 2.35 V here |
| Hysteresis | the input must move a little past the switching point before the output flips back; stops chatter on noise |
| Offset | the small built-in error of the switching point, caused by random transistor differences |
| Propagation delay (tPD) | time from the input crossing to the output crossing |
| Duty-cycle distortion (DCD) | how much longer the output stays high than low (or the reverse), in fractions of a bit |
| Eye diagram, UI | all bits drawn on top of each other; UI = one bit time (10 ns at 100 Mb/s); a wide-open eye means clean timing |
| Corner | one combination of process speed (tt, ss, ff, fs, sf), temperature and supply voltage |
| Monte Carlo, mismatch | many simulations, each with random small differences between "identical" transistors, as on real chips |
| gm/ID | transconductance per unit current: the sizing method that picks how strongly each transistor is turned on |
| LUT | lookup table of simulated transistor data used by the gm/ID sizing |
| Saturation margin, headroom | how far a transistor is from leaving its proper operating region |
| Gate (in this project) | the pass/fail check of one testbench |
| Smoke / full tier | a quick subset of corners / every corner and every Monte Carlo sample |
| Rung, waiver | a pre-planned relaxation / a reasoned change of a test definition |
| Mutation test | a deliberately broken version that the checks must catch |
| Layout, GDS | the drawn shapes of the chip; GDS is the file format |
| DRC | design-rule check: the drawing obeys the factory's rules |
| LVS | layout versus schematic: the drawing is the intended circuit |
| Antenna rule | no long wire may collect enough charge in manufacturing to damage a transistor gate |
| PEX, extraction | reading the real wiring resistance and capacitance back out of the layout |
| Dummy device | an unused transistor or resistor at the end of a row that makes the real ones match |
| ESD | electrostatic discharge protection |
| Failsafe | a defined output when no sender is connected |
| UVLO | under-voltage lockout: forcing a safe output while the supply is too low |
| Hard macro | a finished block of layout that the chip places as one piece |
| LEF / Liberty | the block's outline and pins for place-and-route / its pins and timing for synthesis and timing analysis |
| PDK | process design kit: models, rules and cells from the foundry |
| Netlist | the circuit as a text list of devices and their connections |
| Testbench | one simulation setup that answers one question |
