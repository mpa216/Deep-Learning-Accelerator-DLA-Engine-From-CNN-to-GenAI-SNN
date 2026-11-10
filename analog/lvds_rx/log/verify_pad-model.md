# Independent verification of "pad-model" (2026-11-11)

Verdict: the deliverable reproduces and is usable. No number in the builder's report failed to reproduce. Three small
robustness defects were fixed (listed below). Scratch scripts: `.scratch/verify_pad/` (git-ignored).

## Re-run from a clean state
* Moved results/ aside, deleted work/ and results/, ran `run_tb0.py` (5 s), `run_net.py` (18 s), `check_pad_netlist.sh` (0.2 s): all exit 0.
  `diff -r` of the regenerated results/ against the builder's copy: no difference (byte-identical, so the flow is deterministic).
  `check_pad_netlist.sh`: "IDENTICAL to PDK spice (4 devices)".
* 447 files in work/, 0 logs containing "error"; the only warnings are 146 + 146 x "diode_nd2ps_06v0 / diode_pd2nw_06v0: IKR too small"
  (the builder's claim is exact). `run_net.py` prints "WARNINGS: none".
* Repeated the whole thing again after my fixes: rc 0, results again byte-identical.

## Independent checks (own decks, different method from the builder)
1. Pad C by hand from the PDK model parameters (cjo 0.95/0.912 fF/um2, cjp 1.33e-10/1.4649e-10 F/m, pb, php, mj, mjsw; area 600 um2 and perimeter 424 um
   per diode after m=4; D2 reverse-biased by V, D3 by 3.3-V): 987.0 / 911.0 / 880.5 / 875.9 / 891.0 fF at 0.05/0.6/1.2/1.8/2.35 V.
   This equals the AC table, so the area/perimeter unit convention (m2, m) is right and the "pad is two reverse-biased junctions" explanation is right.
2. Pad C by a different simulation method (transient ramp 1.2 to 1.4 V at 2e7 V/s, C = I/(dV/dt)): 877.6 fF, vs 876-881 fF from AC.
3. Leakage at a corner the builder did not run (ff, 125 C, DVDD 3.3, pin 0.4..2.4 V): about 60 pA (47 pA at 0 V). The hot corner is the worst
   case for leakage, so the worst number is 60 pA, not the builder's 44.7 pA (ss/125C); still 5.5 orders below 20 uA.
4. Liberty file: `capacitance : 0` on the 5 pins of asig_5p0 (file is under `lib/`, not `liberty/`; confirmed).
5. Lane transient with a hand-built linear netlist (pad replaced by 0.88 pF to ground, same R/L/C, 300 fF load, own ngspice `.meas`):
   flat-top 350.00 mV, overshoot peak 396.35 mV (builder 396.3), 10-90 % rise 360.1 ps (builder 360). Independent agreement.
6. `lvds_esd2_poly` resistor measured at 1.0 V: 151.45 ohm (builder 151.4). The on-die termination knob (RT_OFF=1e12, RT_ON=100) works:
   differential DC at the macro pins 349.3 mV for a 350 mV drive, common mode 1.2 V.
7. DC sweep PNG inspected: clamp knees where the table says, DVDD=0 curve conducts from about 0.6 V; consistent.
8. Plain-reading check of the topology: RC-pole claim is correct (pad is on the source side of the ESD resistor; the builder also gives the pessimistic 0.84 GHz case).

## Things I checked that are right but worth knowing
* "Amplitude loss 0" is by construction: the bench is lossless and an ideal driver. Only overshoot and edge rate are informative. The builder says so.
  VOD means the magnitude at the terminated pins, so the peak-to-peak differential swing is 2 x VOD (700 mV for "350 mV").
* The ss/125C leakage (44.7 pA) is not the worst leakage corner (ff/125C, about 60 pA). Irrelevant against 20 uA.
* The pad's diodes are the 6 V models run at 3.3 V; no silicon correlation.

## Defects found and fixed
1. `run_tb0.py`, `run_net.py`: a failed ngspice run could be hidden by a stale `.txt` result left in work/ from an earlier run. `run_ngspice()` / `run()`
   now delete the previous `.log` and `.txt` of that deck first.
2. `check_pad_netlist.sh` only worked when started from analog/lvds_rx; it now cds to its own tree first (tested from /tmp: OK).
3. `netlist/input_network.spice` header did not say that the including deck must also `.include netlist/pad_asig_5p0.spice`; added, plus a note that line 1
   of an ngspice deck is the title (I tripped on that myself while writing a test deck: a `.param` on line 1 is silently ignored and gives a confusing
   "Undefined parameter [r_l]" error from the PDK resistor).

## Remaining (not fixed, not blocking)
* Package L/C, RS=50 and the ideal driver are assumptions (builder flagged). Secondary ESD is a first cut, not HBM-sized.
* TB0 was run only at DVDD = 3.3 V (and 0 V). Pad C depends on DVDD through D3 (reverse bias DVDD - V); at 3.0/3.6 V it would shift by a few percent. Not needed now.
* sim/tb0_pad/work/ is about 130 MB (git-ignored); delete it before archiving.
