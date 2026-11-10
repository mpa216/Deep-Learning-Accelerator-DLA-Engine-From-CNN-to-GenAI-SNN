# pad-model log (2026-11-11): the input path every later bench will use

Everything below was observed by running ngspice in the `apic_headless` container.
Re-run: `docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx python3 sim/tb0_pad/run_tb0.py`
then `... python3 sim/tb0_pad/run_net.py` (4 s and 16 s). Check of the pad netlist against the PDK: `... bash sim/tb0_pad/check_pad_netlist.sh`.
Results: `sim/tb0_pad/results/` (tb0_table.md/.csv/.json, net_table.md/.json, plots/*.png). Example decks: `sim/tb0_pad/decks/`.

## 1. What is inside the analog pad `gf180mcu_fd_io__asig_5p0`

It is only a bond pad with **primary ESD diodes**. No buffer, no series resistor. Pins: `ASIG5V` (the pad), `DVDD`, `DVSS`
(pad-ring supplies, 3.3 V / 0 V), `VDD`, `VSS` (in the pin list but connected to nothing inside the cell, so I tie them to DVDD/DVSS).

| device | connects | what it does | PDK ngspice model |
|---|---|---|---|
| D2 | anode DVSS, cathode ASIG5V | N+/Psub diode: clamps the pad when it goes below about -0.6 V | `diode_nd2ps_06v0`, m=4, area=150e-12 m2, pj=106e-6 m (x4) |
| D3 | anode ASIG5V, cathode DVDD | P+/Nwell diode: clamps the pad above DVDD + 0.6 V | `diode_pd2nw_06v0`, m=4, area=150e-12, pj=106e-6 |
| D0 | anode DVSS, cathode DVDD | rail diode, only joins the two supplies | `diode_nd2ps_06v0`, m=4, area=40e-12, pj=82e-6 |
| C1 | DVDD to DVSS | supply decoupling, 36 x 15um x 15um NMOS-inversion cap (about 17 pF when fully inverted: 36 x 225 um2 x 2.2 fF/um2, hand estimate) | CDL `$[cap_nmos_06v0]` = ngspice subckt `cap_nmos_06v0` with `m=36 c_length=15u c_width=15u` |

Findings that surprised me:
* The **PDK already ships the converted ngspice netlist** (`libs.ref/gf180mcu_fd_io/spice/gf180mcu_fd_io.spice`); the only change from the CDL is
  `C1 ... $[cap_nmos_06v0] l= w=` becoming `X1 ... cap_nmos_06v0 c_length= c_width=`. `check_pad_netlist.sh`: **the 4 device lines of
  `netlist/pad_asig_5p0.spice` are identical to the PDK file** (case-insensitive).
* The pad uses the **6.0 V diode models** even though it runs at 3.3 V (that is what the layout contains).
* D0 and C1 only touch DVDD/DVSS. With ideal supplies they have no effect on the pin; they are kept for faithfulness.
* The cell's Liberty file says `capacitance : 0` for every pin (checked in `gf180mcu_fd_io__tt_025C_3v30.lib`), so the pad cap is invisible to digital tools: measured below.
* Model sections needed: `diode_typical|ss|ff` and `moscap_typical|ss|ff` (the cap is a behavioural tanh() charge model). Loading the deck gives only
  `Warning: diode_*_06v0: IKR too small - model effect disabled!` (a PDK model note, harmless), no other warning or error in any of the 150+ runs.

## 2. TB0 results (DVDD = 3.3 V; `run_tb0.py`)

**C_pad of one pad = 0.88 to 0.99 pF at tt/27C over 0.05..2.35 V (nominal 0.9 pF); 1.0 to 1.15 pF at ss/125C; 0.76 to 0.85 pF at ff/-40C.**
The handoff's guess of 1-1.5 pF was a bit high. It is flat with frequency (1 MHz to 10 GHz: no resistive part worth mentioning, G about 0.05 uS).
Cause of the bias dependence: it is two reverse-biased junctions, D2 (reverse by V) and D3 (reverse by 3.3 - V); the sum is smallest near the middle (1.7 V).

| corner | V(pin) = 0.05 | 0.6 | 1.2 | 1.8 | 2.35 V |
|---|---|---|---|---|---|
| tt 27C, C at 100 MHz (fF) | 987 | 911 | 881 | 876 | 891 |
| ss 125C | 1150 | 1041 | 1001 | 996 | 1017 |
| ff -40C | 846 | 788 | 764 | 760 | 771 |

(A hand check of the junction formula gives about 1.0 pF at 0.05 V, matching 987 fF, so the `area=150e-12` m2 unit convention is right.)
**Number to use in later benches: 1.0 pF per pad (1.15 pF worst case), already included by instantiating the pad cell.**

**Leakage** (current into the pin, 0.05..2.35 V): at tt/27C and ff/-40C it is a few femtoamps, below what the simulator resolves (I set gmin = abstol = 1e-15);
at ss/125C it is **44.7 pA**, flat over the range. TIA-644 allows 20 uA: margin of more than 5 orders of magnitude. (These are model numbers; real silicon leaks more, especially hot, but the margin to 20 uA is huge.)

**DC sweep (`tb0_dc_sweep.png`)**: the diodes start to conduct (|I| > 1 uA / > 20 uA) at
| corner | upper clamp (pin above DVDD) | lower clamp (pin below 0 V) |
|---|---|---|
| tt 27C | 3.88 V / 3.96 V | -0.58 V / -0.66 V |
| ss 125C | 3.66 V / 3.77 V | -0.35 V / -0.46 V |
| ff -40C | 4.03 V / 4.09 V | -0.72 V / -0.79 V |

So the whole TIA-644 range 0..2.4 V is clean in every corner (worst margin 0.35 V at the lower edge in the hot corner).
**Power-off (DVDD = 0, tt)**: D3 conducts from 0.58 V (1 uA) and 0.66 V (20 uA): an LVDS line at 1.2 V would force current into the dead supply.
This confirms handoff 7.8: the pad cannot meet the power-off requirement of TIA-644 (document it as a deviation).

## 3. `netlist/input_network.spice` (what it contains)

`driver emf -> RS 50 ohm -> board node -> [100 ohm termination across P/N here] -> package pi (CPKG/2, LPKG + 0.2 ohm, CPKG/2) -> asig_5p0 pad -> secondary ESD hook -> macro pin`.
Subcircuits: `lvds_drv_pulse` (alternating pattern, VOS/VOD/TR/HALF), `lvds_esd2_none` (1 mohm wire), `lvds_esd2_poly` (proposal), `lvds_front`, and the two tops
`lvds_input_network` (no secondary ESD) and `lvds_input_network_esd` (with it). Parameters: RS=50, LPKG=3n, CPKG=0.7p, RLPKG=0.2, RT_OFF=100, RT_ON=1e12 (= no on-die termination; set RT_OFF=1e12, RT_ON=100 for an on-die one).
Package values are UNVERIFIED (assumed range 2-5 nH, 0.5-1 pF): ask the organizers.

Decisions: (a) `VOD` means |V(P)-V(N)| at the terminated pins in each state (swing +-VOD); the driver scales its emf by (2 RS + RT)/RT so 350 mV really arrives. (b) The 100 ohm
sits on the **board side** of the bond wire by default because the plan is off-chip termination. (c) The package C is split half/half around the bond-wire inductor (pi model).
(d) I did not add package R beyond 0.2 ohm; the lane is lossless apart from that (see caveats).

**Secondary ESD first cut (`lvds_esd2_poly`)**: `ppolyf_u r_width=5u r_length=1.8u` (3-terminal subckt, body tied to DVSS) = **151 ohm tt / 173 ohm ss-125C / 129 ohm ff-(-40C)** (measured), then
`diode_pd2nw_03v3` (to DVDD) and `diode_nd2ps_03v3` (to DVSS), each area 40 um2, perimeter 28 um, about 60 fF together (derived from the measured pole: 1/(2 pi x 151 ohm x 2.91 GHz) = 362 fF minus the 300 fF load).
RC pole with the receiver input (300 fF per side, my reading of "a few hundred fF") plus those diodes, measured by AC simulation: **2.91 GHz tt, 2.49 GHz ss/125C, 3.49 GHz ff**, i.e. 12 to 17 times
the 200 MHz needed. Pessimistic check: if the whole pad cap (0.9 pF) sat on the receiver side of the resistor, 151 ohm x 1.26 pF gives 0.84 GHz, still 4 times 200 MHz. In the real topology the pad is on the *source* side
of the resistor, so it does not enter this pole. CAVEAT: not sized for ESD current (HBM needs a much wider resistor and bigger diodes); replace by the organizers' Metal2/Metal3 cell when available.

## 4. Sanity transient: what really arrives at the receiver (`run_net.py`, plots `net_tran_100M.png`, `net_tran_200M.png`)

Alternating pattern (a 50 MHz / 100 MHz square wave), 0.5 ns ramp at the driver (10-90 % = 0.4 ns), 300 fF across the macro pins, defaults L = 3 nH, C = 0.7 pF, 150 ohm ESD2 optional.

| case (tt 27C, 100 and 200 Mb/s give identical numbers) | amplitude at RX pins at end of bit | overshoot peak | tr 10-90 % at RX pins | tr at board pins |
|---|---|---|---|---|
| VOD 350 mV, no ESD2 | 350.0 mV (no loss) | 396 mV (+13 %) | 360 ps | 430 ps |
| VOD 350 mV, with ESD2 | 350.0 mV | 350 mV | 420 ps | 439 ps |
| VOD 100 mV, no ESD2 | 100.0 mV | 113 mV | 360 ps | 430 ps |
| VOD 100 mV, with ESD2 | 100.0 mV | 100 mV | 420 ps | 439 ps |

Corners (ss/125C, ff/-40C) change the amplitude by < 0.1 mV and the rise time by < 15 ps (`net_table.md`). Lane -3 dB bandwidth (differential, 300 fF across): 3.2 GHz with 4.3 dB peaking
(the 3 nH + pad/package capacitance resonance, which a hand estimate puts at about 2-2.5 GHz) without ESD2; 2.44 GHz and flat with ESD2 (ss/125C: 2.18 GHz). Package sensitivity at 200 Mb/s, VOD 350 mV: L 5 nH, C 1 pF gives 434 mV overshoot (+24 %)
without ESD2 and 377 mV (+8 %) with it; L 2 nH, C 0.5 pF gives 385 / 350 mV.

**What this means for the circuit designer**: the amplitude at the end of each bit is the full VOD (the path is lossless and the pad leaks only fA), and 200 Mb/s is slow compared with the 2-3 GHz lane bandwidth, so there is no
inter-symbol loss and no amplitude loss to budget. What the receiver must tolerate is (i) a **ringing overshoot of 13 % (up to 24 % with a 5 nH package) on each edge (a short ring, visible in the plots)**, unless the
secondary ESD resistor damps it (it does: that is a free benefit of the 150 ohm), (ii) edges of 0.36-0.43 ns rise time, and (iii) the common-mode swing coupled through the pad capacitance is not
modelled (ideal driver). Caveats: ideal, lossless driver/line (no skin loss, no reflection from a real 100 ohm line, no crosstalk, no common-mode noise), the 0.5 ns driver ramp is my choice (TIA-644 allows 0.26 ns and up).

## 5. Pitfalls I hit

1. **`.option abstol=1e-15 reltol=1e-4` makes these transient decks run for more than 10 minutes** (default options: 1.2 s). I first blamed the behavioural MOS cap; a test with the cap removed was equally slow,
   so the cause was the tight tolerances. Keep the default tolerances in transient decks (only the DC/AC leakage decks in `run_tb0.py` use gmin=abstol=1e-15).
2. `wrdata` with `let`-vectors from an AC run produced a mangled file; writing `wrdata file i(vp)` (complex, columns f, re, im) and computing C = -Im/(2 pi f) in Python is reliable.
3. Node names in hierarchy: pad node inside the top subckt is `xn.padp`, board node is `xn.xf.bp`.
4. The DC sweep was extended to -1.2..4.6 V (handoff: -0.5..3.8 V) because at tt the diodes only reach 1 uA at 3.88 V.
