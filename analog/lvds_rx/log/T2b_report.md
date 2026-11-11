# T2 hand-over, part 2 (2026-11-11): TB1 / TB2 benches, LUT-vs-SPICE table, S1 shake-down

## Result
`make smoke`: SIZE, TB0, TB1 (147/147 runs), TB2 (35/35) PASS; the other gates are NOT_RUN (benches of T3 and later; make smoke therefore exits 2 until they exist). `make check` green, lint 0. No ladder rung, no limit changed (D-004).
Key numbers: TB1 min headroom 52.1 mV (limit 50), gm/ID err <= 2.2 %, ID err <= 3.5 %, VGS err <= 8.6 mV, CM <= 13 mV; TB2 A1 >= 5.49, spread <= 1.12x, stage f3dB >= 0.836 DR (limit 0.8), chain >= 55.5 MHz.

## What exists / how to run (container, from `analog/lvds_rx`, through tools/cx)
- `make smoke` -> lint, then harness runs of every existing bench (TB1 at worst7 plus its helper tb1_np, TB2 at worst5), gates, report, and the tables `sim/tb1_op/results/lut_vs_spice.md`, `sim/tb2_ac/results/ac_table.md`.
- `make shakedown` -> `flow/shakedown.py`: regenerates the TB1 decks (baseline and PMOS-only `tb1_op_pmos.*`), builds `tb2_ac_pmos.*`, runs both variants, writes `results/shakedown_s1.{md,json}` (usable VIC range of the PMOS-only input: A1 >= 4 at 0.05-1.2 V, gone at 1.8 V).
- After ANY change of sizing script, LUTs or spec: run the sizing script, then `netlist/gen_core.py`, `netlist/gen_lvs_ref.py`, `sim/tb1_op/make_deck.py`, then `make smoke` (lint rule `sizes` checks the hash).
- TB1 hook metrics are defined at the top of `sim/tb1_op/hooks.py`; TB2's at the top of `sim/tb2_ac/hooks.py`. The TB1 deck is generated (`make_deck.py`, device list from `netlist/lvds_circuit.py`); the TB2 deck is hand-written.

## Open items / thin margins for T3 and later
1. TB1 headroom 52.1 mV (limit 50) at ss/125 C + resistors fast (m3 sink); the five normal corners have >= 109 mV. Knob if a later change eats it: gm/ID of the mirror unit (sizing `D`).
2. Stage-3 pole 83.6 MHz at ss/125 C (limit 80): L_n3 is already 0.28 um; further knob = stage-3 bias current (I3 / Itp).
3. PSRR is 14-21 dB (reported only, no limit); CMRR 46-54 dB nominal. TB6 (supply ripple) is where this matters.
4. TB1 does not check the output logic level (reported as `vout_v`); TB3/TB5 do.
5. PMOS-only variant: m3a sinks untuned, no row in the sizing device table; only a flow vehicle. Usable-range points between 1.2 and 1.8 V were not simulated.
6. TB2 PSRR/CMRR definitions are half-circuit; mismatch-driven CMRR needs Monte Carlo (T5).
