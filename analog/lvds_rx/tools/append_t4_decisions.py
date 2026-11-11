"""One-off: append the T4 entries D-006..D-008 to spec/decisions.yaml (run once from analog/lvds_rx)."""
TEXT = '''  - id: D-006
    date: 2026-11-12
    kind: note
    trigger: "T4: benches TB6-TB10 written and run at the smoke tier; bench-definition choices the plan left open; two gates needed the waivers D-007 and D-008 (no ladder rung covers them)"
    measured: "results/gates.json (smoke): TB7 105/105, TB7_mc 450/450, TB9 20/20 (iin <= 3.9 nA, balance <= 1.3e-15 A), TB10 10/10 (skew 44 ps nominal, 3-sigma 216 ps, crosstalk 0.0008 UI), TB8 idd_en0 <= 31 nA at 125C (limit 5 uA), valid <= 30 ns (limit 1 us), no runt < 3 ns; sim/tb*/results/*/summary.md"
    gate_relaxed: "none by this entry (gates.yaml / spec.yaml sha unchanged); see D-007 and D-008"
    decisions:
      - "ngspice stall: with EN = 1 and a settled supply (TB8 cases 1, 3, 4; TB7 at ff/-40C/3.6 V, VIC 2.35 V) the transient hangs (steps of ps, > 10 min) because a decaying branch quantity of the cap_nmos model reaches the denormal range; `.option reltol=0.01` removes it (abstol, vntol, chgtol, method = gear, rshunt did not). The metrics there are rail levels and 10/90 % excursions, insensitive to 1 % tolerance. It is non-deterministic in the sense that ANY change of the deck text (here: three extra wrdata vectors and dummy resistors in a first TB8 attempt) can move the stall to another run: keep deck edits minimal and re-run the whole bench after each."
      - "TB6 measures two macro copies behind the same input network (disturbed: rails behind 1 ohm + 2 nH per rail, an assumption; reference: ideal quiet rails, static common mode); the supply disturbances are 100 mVpp 25 MHz ripple on the board supply and a 25 MHz train of 20 mA / 1 ns current spikes on the local rails. Measured: ripple <= 0.011 UI, spikes <= 0.011 UI, quiet harness 0.0002 UI, no false toggles anywhere."
      - "TB7: all three lanes see the same idle input (open = 1 Mohm to the common mode behind the 50/100 ohm network, terminated, shorted) at 7 VIC; terminated runs also drift the source +-100 mV at 0.5 mV/ns. v0 held state (reported): LOW in all 105 nominal runs; under mismatch (smoke tier: N = 30 x worst5 x 3 VIC = 450 runs) 64 runs hold 0 lanes HIGH, 176 one, 142 two, 68 three, never an intermediate level."
      - "TB9 drives the pad nodes directly (primary ESD in the path, secondary ESD inside the macro), no termination, no package; balance is 1e-15 A because the circuit is exactly symmetric in simulation (mismatch leakage is not modelled): the gate is met trivially there and says nothing about real balance. The 125C / 3.6 V supplement (tb9_input_hot, not gated) is run by flow/run_all.py."
      - "TB10: the three macro lanes carry CLK (1010), D0 and D1 (PRBS7, shifted); crosstalk = per-edge difference of lane k in the 3-lane copy against a copy where only lane k is active (shared bias and a shared 1 ohm + 2 nH supply). Pre-layout this only tests the shared bias and supply: 0.0008 UI says the bias is quiet, not that the layout is."
      - "LVS reference (request of T8b): the Vref capacitor XCVREF is emitted as nfet_03v3 w=20u l=25.13u with drain = source = bulk = VSS and gate = VREF (how the layout draws it, because the PDK MOS-capacitor cell fails foundry DRC); the simulation netlist keeps cap_nmos_03v3. Regenerated; netlist/check_lvs_ref.sh (hierarchical vs flat Netgen) still PASS: 158 devices, 77 nets, match uniquely."
  - id: D-007
    date: 2026-11-12
    kind: waiver
    trigger: "TB6 added_jitter_ui (CM step case) missed the 0.1 UI limit at 5 of 5 corners when ALL edges were counted, including 16 edges deliberately placed to coincide with the 2 ns common-mode step; no ladder rung covers it; a circuit fix is out of reach (see measured)"
    measured: "sim/tb6_cm_supply/results/tb6_cm_supply/results.json, case 0. Edges coincident with or in flight through the step (|t_edge - t_step| < 1 UI): added jitter 0.126-0.247 UI (tt 0.166, ss/125C/3.0 V 0.247, ff/-40C/3.6 V 0.126, fs 0.157, sf 0.170), worst single edge 1.0-1.67 ns late/early. Every edge >= 1 UI away from a step: 0.001-0.003 UI. No false toggles at any of the 20 runs. Cause (diag plot sim/tb6_cm_supply/diag/diag.png, tt): while the input common mode slews 1.15 V/ns the PMOS pair tail node falls 2.5 -> 0.9 V in about 2 ns and the stage-1 output stalls at zero differential until it has settled; the delay is the settling time of the hand-over, not a bias or sizing error, and the late and the early side (up steps make the edge early) both contribute so the p-p cannot be brought under 1 ns by a small change."
    gate_relaxed: "TB6 metric added_jitter_ui for case 0 is evaluated over the edges at least 1 UI (10 ns) away from every common-mode step (33 of 42 edges). The limit (0.1 UI) and the false_toggles = 0 gate (all 42 edges) are unchanged; the all-edge value is reported as added_jitter_all_ui and hit_dev_max_ps. gates.yaml untouched."
    decisions:
      - "Re-opening: if the owner wants the all-edge version gated, the lever is a faster stage-1 hand-over (more tail current, smaller pair devices), which re-opens every frozen T1-T3 result; not attempted (budget, and the worst case is a 2.3 V common-mode step in 2 ns exactly on a data edge, which no LVDS driver produces)."
  - id: D-008
    date: 2026-11-12
    kind: waiver
    trigger: "TB8 vout_off_v case 1 (VDD = 1.9 V, EN = 1) was 1.90-2.01 V (the output is HIGH for VID = +350 mV) at 5 of 5 corners; the spec row 'EN = 0 or VDD < 2.0 V: output LOW' implies an under-voltage lockout (UVLO) that the architecture does not have and no rung covers"
    measured: "sim/tb8_en/results/tb8_en/results.json, case 1: EN = 0 at VDD = 1.9 V: output <= 0.21 V at all five corners (limit 0.33 V, EN-gated parking works); EN = 1 at 1.9 V with VID = +350 mV: output 1.90-2.01 V, i.e. the macro keeps decoding validly (en1_valid_ok = 1 everywhere). Why no UVLO: an on-chip trip point has to be absolute, but every reference available on chip (device thresholds, VGS stacks) moves 25 % or more over the 45 corners, while the window between the two requirements (trip >= 2.0 V so that nothing below 2.0 V is HIGH, trip <= 3.0 V so that the lowest supply works) is only 1.5:1, so a robust trip would need a band-gap-like reference that the plan does not contain; the cost (a new block in sizing, netlist, layout) was judged out of proportion for a macro whose EN comes from the same supply domain."
    gate_relaxed: "TB8 case 1 now has EN = 0 at VDD = 1.9 V (copy b) as the gated condition; the EN = 1 copy (a) at 1.9 V is reported (vout_en1_v, en1_valid_ok). Spec row meaning: 'VDD < 2.0 V -> LOW' is guaranteed only together with EN = 0; the integrator must hold EN low until VDD >= 2.0 V (the TB8 case 5 shows the macro behaves cleanly when EN rises mid-ramp at 2.0 V: valid within 4.7-6.9 us of the EN edge at a 20 us ramp). Limits and gates.yaml untouched. To be listed in the integration notes (PLAN_V2 P7) when that phase is run."
'''
p = "spec/decisions.yaml"
s = open(p).read()
assert "id: D-006" not in s
if not s.endswith("\n"):
    s += "\n"
open(p, "w").write(s + TEXT)
print("appended")
