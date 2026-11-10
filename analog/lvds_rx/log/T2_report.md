# T2 hand-over, part 1 (2026-11-11): sizing script and netlist

Part 1 = sizing script, netlist, LVS reference, first operating point. Part 2 (TB1 and TB2 specs, S1 shake-down through TB1-TB4 smoke, then T3) is open.

## Result
127 sizing assertions pass; `make check` green (46 harness tests); lint 0 findings; SIZE gate PASS (`make smoke`: 4 PASS, 15 NOT_RUN as before for the benches that do not exist yet).
First `.op` (60 runs, status ok) and AC (15 runs: A1 5.49-10.2 over worst5 x 3 VIC, within 6.1 % of the script at the extremes, f3dB 135-218 MHz): output at the right logic level in every run, stage-1 CM flat to 20-24 mV over VIC 0.05-2.35 V, minimum BSIM saturation margin 109 mV, ID/gm-ID/VGS within 3 %/2 %/5 mV of the script at tt.
No ladder rung taken. Iterations: 2 logged for phase T2 (`results/iterations.jsonl`: block stage1_real_bias 1, option_a_variant 1).

## What exists
- `sizing/lvds_rx_sizing.py` (run: `tools/cx python3 sizing/lvds_rx_sizing.py`, `--no-write` to try, `--set key=value` for a scalar of dict `D`) -> `sizing/sizes.spice`, `sizing/sizing_report.md`, `layout/device_table.json`, `results/sizing.json` (the SIZE gate reads it).
  Re-run it after ANY edit of the script, the LUTs or spec.yaml (lint rule `sizes` checks the hash header), then `netlist/gen_core.py` and `netlist/gen_lvs_ref.py` (device table changes the LVS ref).
- `netlist/lvds_circuit.py` = connectivity (edit here, then regenerate); `lvds_rx_core.spice` = simulation netlist; `lvds_rx_lvs_ref.spice` / `_flat.spice`; `check_lvs_ref.sh` (Netgen hier-vs-flat self-check, PASS).
  Instances are hierarchical: `xdut.xl0.xpre.xmp1a`, BSIM device `@m.xdut.xl0.xpre.xmp1a.m0[id|gm|vdsat]`. Nets: `xl0.oa/ob` (stage-1 outputs), `xl0.d2a/d2b`, `xl0.xout.d3`; shared `vbn vbp vb2 vref`.
- Stage-2 polarity as built: gate A = OA, gate B = OB; VID > 0 (P pin above N pin) gives OB > OA, output HIGH. EN gates a NAND2 (EN = 0 gives OUT = 0).
- Build flags are parameters of `sizes.spice` (`flag_nmos_pair`, `flag_dump_devices`; redefine them with `.param` AFTER the include): the other four flags abort the parse by design.
- `sim/t2_op/`: `make_deck.py` (writes decks + `devices.json`), `t2_op.json`, `t2_flags.json`, `t2_ac.json`, `check_op.py` (-> `results/op_table.md`), `flags_table.py` (-> `results/flags_table.md`), `ac_table.py` (-> `results/ac_table.md`).
  Run: `tools/cx bash -c "python3 sim/t2_op/make_deck.py && python3 sim/harness/cli.py run sim/t2_op/t2_op.json --jobs 6 --force; python3 sim/t2_op/check_op.py"` (about 5 s).

## Rules for the TB1/TB2 decks (learned the hard way)
- DC operating point: `dc Vsup 0.3 {vdd} 0.1` with EN and VIC from B sources scaled by v(vdd), and `.option rshunt=1e11`; read node voltages as `v(x)[n]`, `n = length(v(vdd)) - 1`; device parameters `@m...[x]` are those of the last point. Plain `op` fails to converge.
- Harness 1.2: a gmin/source-stepping failure followed by a recovery note no longer makes a run `nonconverged`.
- AC: `ac dec 20 1e6 3e9` right after the `dc` ramp in the same `.control` block works (the ac operating point starts from the ramp state; `sim/t2_op/t2_ac.spice` is the pattern, A1 and f3dB measured there).
- Pins: the macro has the PIN order of `spec/pins.yaml`; ESD2 is INSIDE the macro (use `lvds_input_network`, not `lvds_input_network_esd`, in front of it).

## Known gaps and open items for part 2 and T3
1. TB1 (full47, 7 VIC, 3 VID) and TB2 (A1, f3dB, CMRR) are not written. The T2 exit criterion "S1 shake-down (PMOS-only stage 1, flag `nmos_pair = 0`) through TB1-TB4 smoke" is open: the flag works (t2_flags) and the PMOS-only variant is right up to 1.8 V at tt.
2. Hysteresis is predicted 10-22 mV (tt, ss/125 C, ff/-40 C, 3.0-3.6 V) and 8.5-27 mV including the two resistor cross corners (not in the 45); fs, sf and ss/-40 C have no LUT and are unchecked. If TB3 misses: first knob is Rs (sizing `D`, via alpha_cands), rung R3 only after two misses.
3. Stage-2 regeneration time constant is 0.6-1.2 ns (estimate); stage-1 pole 98-151 MHz; fold pole 3.2-7.4x f1. tPD and DCD are not measured: TB4 decides (ladder R4: extra gain stage flag is declared but NOT implemented).
4. Headroom at the two resistor cross corners is narrow: M3 margin 65 mV at ss/125 C + res_ff and PMOS pair 71 mV at ff/-40 C + res_ss (limit 50). The 45 corners have at least 137 mV / 91 mV (script) and 116 / 109 mV (SPICE at worst5).
5. Diode and MOS-cap names in the LVS reference (`diode_pd2nw_03v3`, `diode_nd2ps_03v3`, `cap_nmos_03v3`) and `ppolyf_u` bulk tie (VDD here) must be checked against Magic extraction in T8. Dummies are not in the LVS ref.
6. The secondary ESD diode junction capacitance is an assumption (1 fF/um2); input capacitance of one lane input is about 340 fF (script), R_esd x C pole 3+ GHz.
7. VDsat factor 0.86 is calibrated only for NMOS L = 1 um (T1 data); others use 2/(gm/ID). TB1 compares per device with the simulator.
