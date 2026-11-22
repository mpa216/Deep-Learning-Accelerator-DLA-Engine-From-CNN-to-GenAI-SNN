# lvds_rx_x3 design guide: architecture, sizing and tuning

Written 2026-11-15 for iteration 1 (decision D-016), updated 2026-11-21 for iteration 2 (D-017, D-018: the stage-2
hysteresis). Companion to `CARRY_ON_GUIDE.md` (how to finish
the project). Every number here comes from `sizing/sizing_report.md` (regenerated with the current sizing), the
simulations, or the extracted layout; the report and the netlist are the sources of truth when they differ.
Paths are relative to the project folder `analog/lvds_rx/` (= `LVDS/lvds_rx_work/`).

---

## 1. What the macro is

Three LVDS receiver lanes (CLK, D0, D1) sharing one bias block, in GF180MCU 3.3 V devices. Each lane turns a
differential pad pair into a 3.3 V CMOS output: `RXk_O = (RXk_P > RXk_N)`. `EN = 0` powers everything down and
forces the outputs LOW.

| Specification (spec/spec.yaml) | Value |
|---|---|
| Data rate | 100 Mb/s NRZ per lane (UI 10 ns); margin eye at 200 Mb/s |
| Input common mode (VIC) | 0.05 to 2.35 V with VID >= 100 mV (TIA/EIA-644-A) |
| Hysteresis, input-referred | 6 to 35 mV (decision D-009; the handoff asked 8 to 25) |
| Offset window | mean + 6 sigma + V_H,max/2 + 3 mV <= 95 mV; sigma design target <= 5 mV |
| Propagation delay | <= 5 ns at VID 350 mV, <= 8 ns at VID 100 mV (with a +-10 mV offset source) |
| Output | 10-90 % edge <= 1 ns into 30 fF |
| Supply / corners | 3.0 / 3.3 / 3.6 V, -40 / 27 / 125 C, tt ss ff fs sf (45 corners) |
| Current | <= 1.5 mA per lane, <= 0.3 mA bias; EN = 0: <= 1 uA at 27 C |
| Area | macro 650 x 194.2 um (core 600 x 144.2 plus a 25 um margin; spec core limit 600 x 150), Metal1-Metal3 only |

The full criteria per testbench are PLAN_V2 section 3.2 and `spec/gates.yaml`.

---

## 2. Architecture

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

Why each block is what it is (decisions in `spec/decisions.yaml`, details in PLAN_V2 section 4):

- **Hybrid complementary input with dump devices (D-002).** No single pair covers 0.05 to 2.35 V: the PMOS pair
  works at the bottom, the NMOS pair at the top, and both overlap in the middle. Each pair has "dump twins" with
  their gates at Vref = 0.48 VDD and their drains on the pair's own drains. When the inputs leave a pair's range, its tail current
  flows through the twin instead of collapsing, so the tails stay saturated and the gain stays nearly constant
  over VIC (spread <= 2.2x is a gate).
- **Folded cascode into resistor loads.** The PMOS pair folds into NMOS sinks (m3) and cascodes (m5); the NMOS
  pair pulls straight from the load nodes. The loads RL are poly resistors, so the gain is a resistor ratio
  that tracks the bias resistor Rb.
- **Hysteresis comparator in stage 2.** A pair with diode plus cross-coupled loads (positive feedback alpha =
  nf_cross/nf_diode = 1.5 since iteration 2) gives a clean decision with built-in hysteresis, so slow or noisy edges
  do not chatter.
- **Current-mirror converter in stage 3 (D-003).** The stage-2 outputs drive PMOS gates directly; the copy of one
  side is mirrored by an NMOS diode and subtracted from the other at node d3. d3 swings rail to rail with no
  tail, which an NMOS diff-pair converter could not do at the stage-2 output level (about 2 V).
- **Resistor-diode bias (v0).** I_ref = (VDD - VGS)/Rb. Currents move with supply and temperature, but the gain
  and the hysteresis are ratios of the same poly (RL/Rb, Rs/Rb), so most of that spread cancels. A constant-gm
  bias is the pre-authorised upgrade (ladder R6) if the corner spread ever needs it.
- **Secondary ESD per input:** 151 ohm poly in series, then clamp diodes (40 um2 each) to VDD and VSS at the
  pair gates. It is UNQUALIFIED: no HBM / CDM data exists.

The circuit itself, device by device, is `netlist/lvds_circuit.py` (one comment per device).

---

## 3. How each block is sized (gm/ID method)

The method (book 1.2 and 2.3, summarised in `docs/GMID_METHOD_NOTES.md`): choose an inversion level gm/ID and a
length L per role, read the current density ID/W from the corner look-up tables, then W = ID / (ID/W). High gm/ID
gives more gain per current but wider, slower devices; low gm/ID gives speed and matching at a headroom cost
(VDsat about 2/(gm/ID)). Every device keeps VDS >= VDsat + 50 mV. Mirror ratios are integer finger counts of one
NMOS unit (2.5 um, L 1, about 10.5 uA) and one PMOS unit (5 um, L 1, about 4.9 uA), so ratios are exact in layout.

All values at tt, 27 C, 3.3 V unless noted.

### 3.1 Bias block

| Device | Role | W / L (um), fingers | Current |
|---|---|---|---|
| Rb | VDD to the NMOS reference diode | 45.4 kohm | I_ref 52.4 uA |
| mbn | NMOS reference diode, VBN | 12.5 / 1.0, nf 5 (5 units) | 52.4 uA |
| mbs | 1:1 copy that feeds the PMOS diode | 12.5 / 1.0, nf 5 | 52.4 uA |
| mbp | PMOS reference diode, VBP | 55 / 1.0, nf 11 | 53.7 uA |
| mb2p, mb2, Rf | VB2 = Vf + VGS(m5): a one-finger m5 replica at a quarter of its current on Vf = I x Rf | 20 / 1, 7.91 / 0.5, Rf 23.5 kohm | 19.5 uA; Vf 0.46 V |
| rdt, rdb, mvs | Vref = 0.48 VDD divider, EN-gated, 2 pF decap | 42.9 / 39.4 kohm | 40 uA |

I_ref ranges 40 uA (ss, 125 C, 3.0 V) to 70 uA (ff, -40 C, 3.6 V); the whole bias draws 166 uA at tt.

### 3.2 Stage 1

| Device | Role | W / L (um), fingers | ID | gm/ID |
|---|---|---|---|---|
| mp1 x2, mpd x2 | PMOS pair and its dump twins (gate at Vref) | 105.6 / 0.4, nf 22 | 53.7 uA each | 15 |
| mpt | PMOS tail (2x mbp) | 110 / 1.0, nf 22 | 107.5 uA | 7.5 |
| mn1 x2, mnd x2 | NMOS pair and its dump twins | 47.5 / 0.5, nf 10 | 52.4 uA each | 16 |
| mnt | NMOS tail (2x mbn) | 25 / 1.0, nf 10 | 104.8 uA | 7.5 |
| m3 x2 | fold sinks (2.4x mbn) | 30 / 1.0, nf 12 | 124 uA each | 7.5 |
| m5 x2 | fold cascodes | 31.6 / 0.5, nf 7 | 72 uA | 13 |
| RL x2 | loads to VDD | 9.40 kohm | VR = 1.15 V drop | |

- Gain: A1 = (gm/ID) x (Itp / 2 I3) x VR. It needs no extra current; the PMOS path gives 7.48 at tt, 5.28 at
  ss/125 C/3.0 V, 4.59 at the worst resistor cross corner (gate: >= 4 at the VIC extremes).
- `vr_tt` = 1.17 V sets VR. It was lowered from 1.25 in T5 (D-013) because the NMOS pair ran into triode at
  VIC 2.35 V at hot / 3.0 V corners.
- Vf = 0.46 V (`vf_tt`) is squeezed between m3 headroom at ss/125 C and the steered PMOS pair at VIC 0.05 V at
  ff/-40 C; the resistor cross corners leave 50 to 70 mV on each side.
- Poles: output f1 = 1/(2 pi RL C_out) = 112 MHz at tt (96 MHz at ss) with the layout wiring included; fold pole
  0.60 GHz (>= 3 x f1 is an assert).
- Known exception (D-012): at fast / hot corners and VIC 0.05 V the steered PMOS pair device runs up to 100 mV
  into triode; gain, delay and eye are checked there after extraction (met in iteration 0).

### 3.3 Stage 2 (hysteresis comparator), re-sized in iterations 1 and 2

| Device | Role | W / L (um), fingers | ID | gm/ID |
|---|---|---|---|---|
| mt2 | tail (2.4x mbn) | 30 / 1.0, nf 12 | 125.8 uA | 7.5 |
| ms x2 | input pair, gates on oa / ob | 8.74 / 0.5, nf 2 | 62.9 uA each | 8 |
| Rs x2 | source degeneration | 0.37 kohm (5 um wide, 1.637 um long) | | |
| mld x2 | diode loads | 7.4 / 0.28, nf 4 (1.85 um fingers) | 25.2 uA | 8.6 |
| mlc x2 | cross-coupled loads (alpha = 6/4) | 11.1 / 0.28, nf 6 | 37.7 uA | 8.6 |
| mpu2 x2 | park d2a / d2b at VDD when EN = 0 | 2 / 0.5 | | |

- Hysteresis: V_H,in = V_H2 / A1. A plain pair would spread about 4:1 over the corners (V_H2 follows 1/(gm/ID),
  A1 follows gm/ID x VR). With Rs the trip is partly the drop I_T2 x Rs, which follows (VDD - VGS) x Rs/Rb exactly
  as VR does, so it cancels against A1. The script solves Rs for vh_scale x 14 mV = 15.1 mV at tt (large-signal,
  from the tables; `vh_scale` 1.08 calibrates that solve against simulation). Simulated: 9.3 to 25.3 mV over the
  eight V_H-extreme corners, inside the 6 to 35 mV window.
- Mismatch of the load ratio moves V_H by 2 alpha / (alpha^2 - 1) times its relative error: 4.4 at alpha 1.25,
  2.4 at 1.5. At 1.25 (iterations 0 and 1) the Monte Carlo spread was 15 to 22 % of the mean and 17 of 600 runs fell
  below 6 mV at ff/-40C/3.6 V; at 1.5 it is 7 to 11 % (480 runs: 7.3 to 30.4 mV, 6.68 to 31.59 mV at +-3 sd).
- Speed: the latch regenerates with tau about C_d2 / (gm_cross - gm_diode); the script's model gives 449 ps at
  tt, 653 ps at ss/125 C (iteration 1: 833 ps and 1.2 ns). This stage dominated the delay before iteration 1.
- Iteration 1 changed `n_t2` 5 -> 10 (tail 63 -> 126 uA), `gmid_s2` 12 -> 8 (a smaller pair for twice the
  current, so less gate load on oa / ob) and `L_ld` 0.40 -> 0.28 (faster loads; at 0.40 the latched pair margin
  failed at ss with the resistor cross corner).
- Iteration 2 changed alpha 1.25 -> 1.5 (4 / 6 fingers), Rs to 5 um wide (a 2 um wide Rs this small would be
  shorter than the 1 um minimum length), the load fingers 2.0 -> 1.85 um and `vh_scale` to 1.08. The layout
  generator set two limits: an interdigitated load row with three source/drain nets needs fingers of at least
  1.81 um, and at most two devices in it may have an odd finger count, so alpha 1.4 = (5, 7) cannot be built.

### 3.4 Stage 3 and the output chain

| Device | Role | W / L (um), fingers |
|---|---|---|
| mp3 x2 | PMOS copies of the stage-2 diodes, ratio `r3` = 2 | 14.8 / 0.28, nf 8 |
| mn3 x2 | NMOS mirror (diode + copy), 50.3 uA at balance | 4.66 / 0.28, nf 1 |
| NAND2, INV1, INV2, INV3 | n / p widths 2.0/3.0, 1.5/3.7, 3.0/7.5, 8.0/20.0 um, L 0.28 | fan-out <= 4 each |

`L_n3` = 0.28 (was 0.5) came from T2: the d3 pole was 39 MHz at ss/125 C, below the 80 MHz needed.

### 3.5 Currents and offset

| Corner | I_lane | I_bias |
|---|---|---|
| tt 27 C 3.3 V | 755 uA | 166 uA |
| ss 125 C 3.0 V | 572 uA | 129 uA |
| ff -40 C 3.6 V | 1025 uA | 220 uA |

Three lanes plus bias draw about 2.43 mA at tt. The hand offset budget gives sigma_total = 3.34 mV (target 5 mV):
stage 1 2.80, stage 2 / A1 1.47, hysteresis spread / 2 0.88, stage 3 0.58 mV. The trip window is 42.5 mV
against 95 mV. The Monte Carlo of TB3_off (N = 1000 per corner and VIC) is the judge.

---

## 4. Tuning: which knob moves which spec

All knobs are keys of the `D` dict in `sizing/lvds_rx_sizing.py` (each with a comment). Try one without touching
frozen files: `tools/cx python3 sizing/lvds_rx_sizing.py --set key=value --out .scratch/tryN`, then simulate the
candidate (CARRY_ON_GUIDE section 7).

| Knob (now) | Moves | Costs or limits | Learned so far |
|---|---|---|---|
| `n_t2` (10) | stage-2 tail current: latch speed, the main tPD lever; hysteresis through I_T2 x Rs | about +38 uA per lane per unit (tail plus stage 3); ms, Rs, stage 3 follow | 5 -> 10: slow-corner tPD 6.51 -> 5.26 ns with layout loads |
| `L_ld` (0.28) | L of the stage-2 loads and stage-3 copies: speed | hysteresis spread from load VT mismatch | 0.40 -> 0.28 on top of n_t2 10: 5.26 -> 4.79 ns |
| `gmid_s2` (8) | stage-2 pair inversion: lower = smaller pair, less load on oa / ob | more stage-2 offset, less pair headroom | 12 -> 8 on top of the two above: 4.79 -> 4.50 ns; with L_ld 0.40 it failed the latched pair margin at the cross corner |
| `r3` (2) | stage-3 current = r3 x diode current: d3 speed | more gate load on d2a / d2b, more current | 3 gave no gain for +139 uA |
| `L_n3`, `gmid_n3` (0.28, 8) | d3 pole | mirror matching | 0.5 -> 0.28 in T2 fixed the stage-3 bandwidth |
| `i_ref` (48 uA design, 52.4 uA built) | every current at once: speed everywhere | power; 19 of 35 devices change size (big re-layout) | 60 uA gave 4.11 ns but was not taken |
| `n_tail_n`, `n_m3`, `p_ratio_tail` (8, 10, 2) | stage-1 currents and the ratio Itp/2I3 in A1 | power; the input quads grow | not changed |
| `gmid_pair_p`, `gmid_pair_n` (15, 16) | gain A1 and input capacitance | lower = less gain | PMOS 13 failed A1 >= 4.2 at the cross corner |
| `L_pair_p`, `L_pair_n` (0.4, 0.5) | speed vs L-offset | PMOS 0.28 is ladder R4 rung 2 | not changed |
| `vr_tt` (1.17 V) | RL drop: A1 is proportional to VR; stage-1 output CM | NMOS pair headroom at VIC 2.35 V | 1.25 -> 1.17 in T5 (D-013); 1.10 bought 2 % speed for 6 % gain |
| `gmid_m5` (13) | fold pole | headroom | 10 failed the fold-pole assert |
| `vf_tt` (0.46 V) | cascode bias window | m3 vs PMOS pair margins | squeezed at both ends: leave it |
| `vref_ratio` (0.48) | dump threshold: centre of the N/P overlap | the overlap window at the slow corner | not changed |
| `alpha_cands` ([(4, 6)]) | hysteresis: Monte Carlo spread of V_H, regeneration speed | the load row: at most two odd finger counts | (4, 5) -> (4, 6) in iteration 2 halved the V_H spread; (5, 7) cannot be built; (3, 5) needs Rs < 0 |
| `vh_scale` (1.08) | the V_H target of the Rs solve (centres V_H in the window) | higher = less room at the top (ff/125C/3.6 V, VIC 0.05 V has the lowest A1) | 1.03 / 1.06 / 1.10: +-3 sd 6.31-30.32 / 6.54-31.15 / 6.87-32.07 mV |
| `rw_rs` (5.0 um) | Rs width only (RL, Rb, Rf and the divider stay 2 um, their ratios unchanged) | wider = longer Rs for the same value | lets the 0.37 kohm Rs meet the 1 um minimum length |
| `wf_ld` (1.85 um) | load and stage-3 copy finger width: d2 capacitance | layout floor 1.81 um (three contact bars) | with alpha 1.4: 2.0 um 4.82 ns, 1.6 um 4.66 ns (not drawable); final 1.85 um with alpha 1.5: 4.54 ns (ss/125C/3.0 V, VID 0.35 V) |
| `dig` widths | output chain delay and edge into 30 fF | input load on d3 | not changed |
| `wiring estimate scale` (1.2, `sim/tbl/make_estimate.py`) | how pessimistic the layout loads are in pre-layout sims | frozen file: needs a decision entry | calibrated on 36 extracted points |

Rules of thumb from the trials:

- Delay is mostly stage 2, then stage 1, stage 3, the output chain (at the slow corner after iteration 1:
  1.66 / 1.47 / 0.64 / 0.60 ns).
- Scaling a current with gm/ID sizing scales W and C too: speed comes only from the fixed loads (wiring, the next
  stage's gates). Lower gm/ID or shorter L buys real speed at the same current.
- Check the hysteresis (TB3) after any stage-2 change: iteration 1 moved V_H from 10.7-17.3 to 8.3-14.3 mV, and at
  ff/-40C/3.6 V its Monte Carlo spread (sd 1.4-1.6 mV on a mean of 8.3-8.6 mV) put 17 of 600 runs below 6 mV.
  Check TB3_hmc, not only the corner trip points.
- Spec limits are not knobs. Relaxing one is a ladder rung (`spec/decisions.yaml`), taken only when its trigger
  fired twice in a row.

---

## 5. Layout-aware design (what T11 taught)

The first post-layout run (iteration 0) failed because the pre-layout netlist did not know the layout:

| Effect | Pre-layout assumption | Extracted |
|---|---|---|
| Wiring on oa / ob (stage-1 outputs) | none in the netlist (the script's own model assumed 10 fF) | 27.6 fF each |
| Wiring on d2a / d2b (latch) | none | 22 to 24 fF |
| Junction (drain / source) area | 0.18 um of diffusion per region | 2.84 x that (about 0.5 um), dummies included |
| PMOS pair n-well (tied to its tail tp) | none | about 100 fF to substrate |
| Result | tPD 3.71 ns (tt, VIC 0.05, VID 0.1) | 5.55 ns (+49 %) |

Since iteration 1 the simulation netlist carries a layout parasitic estimate (`sizing/parasitic_estimate.json`,
made by `sim/tbl/make_estimate.py`):

- `ldiff` = 0.511 um replaces 0.18 um in every device's ad / as / pd / ps formula;
- one capacitor to VSS and one to VDD per net (31 nets), equal to the extracted wiring x 1.2. The VDD part
  matters for supply coupling (TB8 output glitch during supply ramps).

The scale 1.2 was calibrated on 36 extracted TB4 points: at 1.0 the estimate captured 87 to 90 % of the added
delay everywhere; at 1.2 it is at or above the extraction at 35 of 36 points (7 ps short at the last). The
estimate never enters the LVS reference (`lvds_circuit.ESTIMATE` is used only by the simulation emitter).

Two more lessons:

- Gate TBL allows each metric to move by 30 % of its pre-layout margin. A spec met with 9.5 % margin can absorb
  only about 3 %, which no layout achieves; keep real margin at the slow corner.
- Magic 8.3.636 `extresist` counts every coupling capacitor twice in the RC netlist. `check.rc_repair` takes the
  capacitance from the C-coupled extraction instead; wire resistance itself adds only about 6 ps here.
- The sizing must stay inside what the layout generator can draw. Iteration 2 lost one round to it: (5, 7) load
  fingers (more than two odd counts in an interdigitated row) and 1.6 um fingers (below the 1.81 um that three
  contact bars need) both failed `make layout`. The sizing asserts every poly resistor at least 1 um long; the two
  row limits are not asserted yet (AUDIT_2 F8).
- The poly resistor model has 85.45 ohm/sq x 1 um / W at each terminal, so the end resistance scales as 1/W.
  Sizing (`res_len`) and layout (`passives.seg_len`) use 85 ohm x 2 um / W per end; at the 2 um of every resistor
  except Rs this is the old constant.

---

## 6. Verification: what is checked and where it stands

| Gate | Testbench (sim/...) | What it proves | Status 2026-11-22 (T13, final sizing) |
|---|---|---|---|
| TB1 | tb1_op | headroom, LUT vs SPICE, stage-1 CM, currents, node range | PASS, 987 runs (D-012: headroom waiver at the fast / hot common-mode extremes) |
| TB2 | tb2_ac | A1 >= 4, gain spread over VIC, stage and chain bandwidth | PASS: A1 >= 4.78, spread 1.59 (<= 2.2), stage 0.92 x DR (>= 0.8), chain 60.7 MHz (>= 50) |
| TB3 | tb3_trip, tb3_off, tb3_hmc | hysteresis window, offset Monte Carlo, functional MC | PASS: V_H >= 9.1 mV by DC sweep, 7.3-24.2 mV in the Monte Carlo (window 6-35 mV); offset window 39.9 mV (<= 95 mV) |
| TB4 / TB4b | tb4_pd, tb4b_pd_vid | delay, DCD, edge, delay spread | PASS: tPD 4.54 ns at VID 0.35 (<= 5), 5.26 ns at VID 0.1 (<= 8); change over VID 200-450 mV 0.30 ns (<= 1) |
| TB5 / TB12 | tb5_eye, tb12_pkg | eye and BER through the input network and package | PASS: eye >= 0.926 UI at 200 Mb/s, >= 0.973 at 100 Mb/s; package sweep >= 0.925 UI; no bit errors |
| TB6 to TB10 | tb6 ... tb10 | CM steps and ripple, idle inputs, EN and supply ramps, input leakage, three lanes | PASS (TB7 / TB7_mc with D-010 and D-020; TB8 with D-019: EN = 0 output <= 0.262 V, shortest wake-up pulse 3.0 ns) |
| LAYOUT | results/layout.json | DRC (Magic, KLayout deck), strict LVS, antenna, via arrays, negative controls | PASS (iteration-2 layout; re-run in T13: the same layout, only the GDS date stamps differ) |
| TBL | sim/tbl_* | the extracted macro against pre-layout, 30 % of margin | PASS (iteration 2, with D-019): 178 pairs, at most 23.6 % of a margin used |

Final records: `results/gates.json` and `results/REPORT.md` (closing regression of T13, 2026-11-22),
`results/post_layout/TBL.md`, `results/AUDIT_2.md`, `package/`. Earlier full-tier records: `results/full_2026-11-14/`
(the frozen sizing before T11) and `results/post_layout/iter0/` (the failed post-layout run). Decisions on record that
shape the gates: D-007 (TB6 jitter window, waiver), D-008 (EN with low supply, waiver), D-009 (hysteresis window, ladder
R3 rung 1), D-010 / D-011 (idle and EN pulse definitions), D-012 (triode corner, waiver with a post-layout condition,
met), D-014 (offset gate tightened), D-015 (gate TBL defined), D-016 (iteration 1), D-017 / D-018 (iteration 2: stage-2
hysteresis, retry variants for TB3_trip / TB3_hmc), D-019 (TB8 power-up checks, waiver chosen by the owner), D-020 (TB7
idle-window guard, waiver chosen by the owner).

---

## 7. Where to read more

| Topic | Document |
|---|---|
| gm/ID theory with book pages | `docs/GMID_METHOD_NOTES.md` |
| Why the hybrid input with dump devices | `docs/SPIKE_STAGE1.md` |
| Every device, corner table, offset budget, asserts | `sizing/sizing_report.md` |
| Spec, gates, architecture, build order | `PLAN_V2.md` sections 3 and 4 |
| Original research and alternatives | `HANDOFF_FOR_CLAUDE.md` section 5 |
| Plain-language LVDS background | `LVDS/GUIDE_FOR_YOU.md` |
| History of every change | `DESIGN_LOG.md`, `spec/decisions.yaml`, `results/iterations.jsonl` |
| Layout construction | `layout/lib/LANE_RECIPE.md`, `layout/lib/README.md`, `log/T9_report.md`, `log/T10_report.md` |
| T11 working notes | `log/T11_notes.md` |
