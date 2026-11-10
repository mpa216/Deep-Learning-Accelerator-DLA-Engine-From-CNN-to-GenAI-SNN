# T1 hand-over (2026-11-11): stage-1 spike

## Result
Hybrid complementary input stage + dump devices (Vref = 0.48*VDD) PASSES every stage-1 criterion at all 8 corners (tt 3.3 V/27 C, ss 3.0 V/125 C and -40 C,
fs 3.0 V/27 C, sf 3.0 V/125 C, ff 3.6 V/-40 C, plus ss/125 C+res_ff and ff/-40 C+res_ss), VIC 0.05-2.35 V in 47 steps. CM span 12-31 mV, A1 4.26-10.1, spread <= 1.27x,
min saturation margin 88 mV, f3dB >= 170 MHz. The no-dump control fails (CM span up to 1.2 V). Topology decision: dump devices ON (D-002 in `spec/decisions.yaml`). No ladder rung taken.
Iterations: 2 of 8 (block stage1_spike 2/5, phase T1 2/8).

## What exists
- `sizing/spike_stage1.py`: gm/ID sizing for the spike (defaults = iteration 2) and generator of `sim/spike_stage1/tb_spike_{A,H0,H1}.spice` + `spike_*.json`.
  `--set key=value` overrides a parameter (see dict `P`); writes `results/spike_stage1_sizing.json` (device table and LUT predictions).
- `sim/spike_stage1/`: `hooks.py` (ideal-bias scale ibs: 1.33 ss/125 C, 0.78 ff/-40 C), `analyze.py` (aggregation, verdicts, plots, LUT-vs-SPICE), `run_all.sh`, `make_doc.py` + `doc_template.md`
  (build `docs/SPIKE_STAGE1.md`), `results/tables.md`, `plots/*.png`. Raw run directories are in `results/*/work` (gitignored).
- `results/spike_stage1.json` (all numbers + verdicts), `results/iterations.jsonl`, `docs/SPIKE_STAGE1.md` (tables, plots, book reasoning for each gm/ID and L).
- Re-run: `docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx bash sim/spike_stage1/run_all.sh` (about 30 s), then `... python3 sim/spike_stage1/make_doc.py`.

## What T2 should reuse
- Netlist pattern (generated in `spike_stage1.py: netlist()`): PMOS pair + dump twins share the tail node and its n-well; dump drains go to the same nodes as the pair drains
  (fold nodes for PMOS, RL nodes for NMOS); M5 gate from a replica diode on an offset Vf; one NMOS diode biases tail and sinks (integer mirror multiples, nf in multiples of the unit).
- Starting sizes: pair gm/ID 15 (NMOS L 0.5 W 34 um nf 7; PMOS L 0.4 W 100 um nf 20), tails/sinks gm/ID 7 L 1, M5 gm/ID 10 L 0.5, I3 = 1.2 Itp, Itp = Itn = 100 uA, VR 1.0 V, Vf 0.45 V.
- TB1/TB2 definitions to adopt (D-002): `s1_cm_dev_v` = span/2 over VIC; `np_overlap_v` evaluated on the dump-free control (dump gates disconnected) AND Vref >= 0.125 V inside that window;
  A1 at VIC 0.05 and 2.35 V; saturation margin from BSIM `@m.x<name>.m0[vdsat]` (`mg_*` metrics in the spike decks, `echo RESULT` pattern).

## Open for T2+
1. Mismatch: the dump twins add their own sigma at the input (about 2 mV for the NMOS twins at W*Leff = 12 um2). Include in the C3 offset budget; a k-times-wider twin lowers it by sqrt(k)
   and moves the hand-over by n*UT*ln(k) (reasoned, not simulated).
2. Real bias: the spike used ideal currents x ibs. With a resistor-diode bias VR follows (VDD - VGS_b) x (RL/R_b), so slow 3.0 V corners lose gain; the weakest A1 in the spike is only
   6-11 % above 4 (4.26 ss/125 C+res_ff, 4.45 sf/125 C). Re-check A1 and the absolute CM (1.56 V at ss/125 C, 2.94 V at ff/-40 C) on the real bias; stage 2 must accept that range.
3. Large signal (VID up to 450 mV), tPD versus VIC, input capacitance (PMOS pair + dump 4 x 100 um, about 150 fF Cgg per PMOS device), fold-pole assertion in the sizing script.
4. The spike's idd (421 uA at tt) includes 88 uA of ideal reference currents (M5 replica at full current); scale the replicas down in the real bias.
