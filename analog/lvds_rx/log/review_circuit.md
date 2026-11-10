# Plan review, lens "circuit" (2026-11-10)

Scope: spec (handoff 4.4), architecture (5), sizing (7), offset (8), verification (9), risks (16).
Everything below marked MEASURED was run in the container; scratch decks and scripts are in
`analog/lvds_rx/.scratch/review_circuit/`.

## What I measured (and what it means)

1. **Monte Carlo mechanism works** (`mc_pair.spice`, ngspice-46, `typical`, `sw_stat_mismatch=1`).
   `setseed` + `reset` + `op` in a `dowhile` loop re-draws the per-instance mismatch each pass, and
   a second run with the same seed gives identical numbers (so it is reproducible).
   sigma of the VGS difference of two nominally identical NMOS at 50 uA each, 300 draws:

   | Device pair | sigma (MEASURED) | Pelgrom prediction |
   |---|---|---|
   | W=13 um, L=0.5, nf=1 | 3.41 mV | 7.148/sqrt(0.35*13.1) = 3.34 mV |
   | W=13 um total, nf=4 | 3.31 mV | 3.34 mV |
   | W=3.25 um, `m=4` | **6.79 mV** | 4 parallel copies share ONE random draw, so the model sees W=3.25 |

   Lessons: (a) the handoff's AVT = par_vth (7.15 mV*um for the pair) and the Leff/Weff corrections are
   confirmed. (b) Always express a matched device as total `w` with `nf`, never as `m`: with `m` the
   Monte Carlo is 2x pessimistic here (and wrong in general). (c) `nf` with total W is handled correctly.

2. **N/P common-mode window at the real corners** (`cm_window.py`). Tail current of a PMOS pair
   (W=24, L=0.28, 110 uA tail, tail L=1) and an NMOS pair (W=13, L=0.5, 90 uA tail, tail L=1), edge = tail
   current falls to 90 % of plateau. Gates at VIC, drains at fold node 0.5 V (P) or VDD-0.8 V (N).

   | corner | VDD | T | PMOS pair valid up to | NMOS pair valid from | overlap |
   |---|---|---|---|---|---|
   | typical | 3.3 | 27 | 2.075 | 1.150 | 0.925 |
   | typical | 3.0 | 27 | 1.775 | 1.150 | 0.625 |
   | ss | 3.0 | 125 | 1.650 | 1.300 | **0.350** |
   | ss | 3.0 | -40 | 1.600 | 1.275 | **0.325** |
   | fs | 3.0 | 27 | 1.650 | 1.075 | 0.575 |
   | sf | 3.0 | 125 | 1.900 | 1.275 | 0.625 |
   | ff | 3.6 | -40 | 2.500 | 1.025 | 1.475 |

   So the handoff estimate (1.25 to 1.77 V at 3.0 V TT) is right for TT, but at SS/3.0 V the overlap is only
   0.33 V wide, centred near 1.45 V. The dump-device gate reference must therefore sit within about
   +-60 mV of the centre at SS. A divider Vref = 0.48*VDD lands in the middle at every corner above
   (TT 3.3 -> 1.58 V vs centre 1.61; SS 3.0 -> 1.44 vs 1.46; FF 3.6 -> 1.73 vs 1.76), so a VDD-ratio reference
   is the right kind of source; a diode/VT-based one would not track.
   Also: the PMOS-only milestone (Option A) tops out at 1.60 V at SS/3.0 V/-40 C. A standard LVDS driver
   (VOS up to 1.375 V, VOD up to 0.454 V) puts its high pin at 1.6 V, so Option A is marginal even for a
   standard host at the worst corner. It is a flow milestone, not a product.

3. **A deliberate W-ratio failsafe shift is not PVT-stable** (`fs_shift.py`). A 1.8:1 W ratio (13 vs 7.2 um,
   L=0.5, equal currents, bias scaled like constant-gm: +33 % at ss/125, -22 % at ff/-40):

   | device | TT | ss/125 C | ff/-40 C | spread vs TT |
   |---|---|---|---|---|
   | NMOS | 60.5 mV | 86.0 mV | 45.7 mV | -24 % / +42 % |
   | PMOS | 114 mV | 164 mV | 82 mV | -28 % / +44 % |

   Two facts: the shift is strongly inversion-level dependent (the same W ratio gives 60 mV on NMOS but
   114 mV on PMOS at 45 uA), so "1.8:1" is not a universal recipe; and temperature alone moves it by
   about +-30 % (weak inversion: dVGS = n*UT*ln(r) is PTAT). The handoff assumed +-25 %.

4. **Corner-aware two-sided window** (`window_budget.py`, my arithmetic, inequalities of handoff 8.1 with
   sys 3 mV, margin 5 mV):

   | assumption | best nominal V_fs | max total sigma | needed pair WLeff | W at L=0.5 / L=1.0 |
   |---|---|---|---|---|
   | handoff: nominal only, VH 25, k=6 | 50 | 4.9 mV | 3.0 um2 | 8.5 / 3.5 um |
   | + corners (fs +-25 %), VHmax 33, k=6 | 50 | **2.2 mV** | 15.6 | 44 / 18 |
   | + measured fs spread, VHmax 33, k=6 | 46 | **1.7 mV** | 25.4 | 72 / 30 |
   | measured spread, VHmax 20, k=6 | 46 | 2.8 mV | 9.5 | 27 / 11 |
   | measured spread, VHmax 33, 3 sigma failsafe / 4.5 sigma sensitivity | 44 | 2.9 mV | 8.7 | 25 / 10 |
   | measured spread, VHmax 20, 3 sigma / 4.5 sigma | 42.5 | 4.8 mV | 3.2 | 9 / 4 |
   | **no failsafe shift (V_fs = 0)**, VHmax 33, k=6 | 0 | **12.6 mV** | 0.46 | tiny |

   VHmax 33 comes from: V_H varies 2x across VIC (A1 doubles in the overlap), 1.3x across corners, and
   the >10 mV floor at the minimum. The handoff's "sigma <= 4 mV" is true only if V_fs and V_H do not move
   with PVT. Real requirement for a 6-sigma failsafe is sigma_total <= about 2 mV, and "total" must
   include stage 2 / A1 (see finding 3), not just stage 1.

5. **DCD vs the failsafe shift** (`window_budget.py`). DCD = V_fs * tr / A (A = VID amplitude, tr = 0-100 % edge).
   With V_fs = 50 mV at VID = +-100 mV: 5 % UI at tr = 1 ns, 10 % at 2 ns, 15 % at 3 ns. The spec (4.4, TB5)
   says DCD <= 5 % UI and also the TIA edge rate 0.5-3 ns at VID down to 100 mV. These cannot both hold.
   At VID = +-350 mV the same shift costs only 1.4-4.3 %.

6. **TB3 triangle artefact.** A 1 us triangle of +-150 mV is 0.6 mV/ns. A 4 ns tPD makes each trip point
   appear 2.4 mV late, so measured hysteresis looks 4.8 mV too wide (20 % of 25 mV) and offset is fine.
   Same size as the sigma budget, so it matters.

7. **Leakage is not a trap.** Off-state leakage, W=100 um L=0.5, VDS=3.3 V: NMOS 5.6 nA at ff/125 C,
   4.3 pA at tt/27 C; PMOS 0.53 nA at ff/125. IDD <= 1 uA in power-down holds up to about 18 mm of total
   NMOS width at the worst corner. The risk is resistive paths (bias resistors, failsafe bias, divider for
   the dump reference), which EN must break.

8. **Poly resistor**: `ppolyf_u_1k` exists in the model (rsh 1000, res_ss 1200, res_ff 800, 85 ohm end
   resistance per end). No resistor mismatch model exists (no agauss on resistors), so RL pair mismatch
   must be budgeted by hand: dR/R of 0.5 % gives about 0.4 mV input-referred at gm/ID=12, negligible, but
   it will not show in Monte Carlo.

## Not measured (reasoned only)

- Whether the dump-device current-steering really holds the stage-1 output CM within +-0.15 V.
  I recommend a one-day spike with ideal bias to test it before any sizing script is written.
- Cost of Monte Carlo transients on a loaded machine.
