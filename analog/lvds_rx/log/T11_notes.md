# T11 working notes: post-layout re-simulation and final audit (started 2026-11-14, owner's go-ahead "Yes go ahead")

Solo, small pieces with one local commit each. Simulations with 4 parallel jobs. Report and wait for the owner before T12.

## Scope (PLAN_V2 6.5, gate TBL of spec/gates.yaml)

About 100 runs on the PEX netlists of T10 (`results/layout/`): TB1 op at VIC 1.2 V (tt), TB2 ac, TB3 DC trips and offset
at 3 VIC x worst5, TB4 tPD at 2 VID, TB5 eye at 100 and 200 Mb/s with the TB12 package corners at the worst corners, TB7
idle, TB8 EN, TB10 three lanes. Gate: every metric within 30 % of its margin to the limit of its pre-layout gate. Audit
condition D-012 (AUDIT_1): re-check the fast-hot-3.6 V corner after extraction.

Findings so far: every bench instantiates the whole macro `lvds_rx_x3` as `xdut` (the PEX subckt has the same name and
port order). TB1, TB2 and TB3_off also probe internal nodes by the pre-layout hierarchy (`v(xdut.xl0.xpre.tp)`,
`v(xdut.vbn)`, ...); TB2 and TB3_off reference devices (`xdut.xl0.xhyst.xmlc1.m0`). Node probes can be served by naming
the PEX nodes after the pre-layout paths (the layout uses the reference's own net names); device probes cannot (one
schematic device is several layout fingers).

## Pieces

| Piece | What | State |
|---|---|---|
| 0 | `results/layout.json` for gate LAYOUT (T10 left it out), evaluated with `flow/gates.py --phases layout --out results/gates_layout.json` | done: PASS |
| A | PEX node names = pre-layout hierarchical paths (probe-compatible macro netlists) | done (b91c4d2) |
| B | `sim/tbl_*` specs (the pre-layout benches with the PEX include, the 6.5 corner / grid subset) + cost of one run each | in progress |
| C | the runs (detached, 4 jobs) | open |
| D | evaluator (post vs pre, 30 % of margin) and gate TBL | open |
| E | AUDIT_2, REPORT, DESIGN_LOG, make check; report to the owner and wait | open |

## Piece B findings (2026-11-14, after the owner's "keep going without waiting for my approval")

- ngspice keeps every node of a transient in memory: TB4 on the RC netlist (about 9400 nodes, 18000 time points) asked
  for 548 MB and was refused. `make_benches.py` now writes one `.save` line per deck with the vectors its control section
  reads (no circuit change; pre and pex share the deck).
- Cost of one extracted (RC) run, tt, first grid point: tbl_op 3.8 s, tbl_ac 15.6 s, tbl_trip 158 s, tbl_pd 252 s
  (C-only 75 s), tbl_idle 92 s, tbl_en 108 s.
- **tPD rises a lot**: TB4 at tt, VIC 0.05 V, VID 100 mV: pre-layout 3.71 ns (the TBL deck with the pre-layout core
  reproduces TB4 exactly), C-only extraction 5.54 ns, RC extraction 6.45 ns (+2.74 ns, 64 % of the 4.29 ns margin to 8 ns).
  Two thirds capacitance, one third wire resistance. Being diagnosed stage by stage (`.scratch/t11/diag_tb4.py`).
- D-012 (sizing/FROZEN.md) asks for op, gain, delay and one eye run at ff/125C/3.6 V, VIC 0.05 V after extraction:
  tbl_op now covers the 7 VIC x VID +-100 mV at tt and that corner; new bench tbl_eye (TB5 deck) at that corner.

## Criterion reading for gate TBL (fixed here before the full runs)

Per pair (same deck, corner, grid point): margin = distance of the value to the source TB gate's limit (the nearer side
of a two-sided limit, as flow/gates.py). used = (margin_pre - margin_pex) / margin_pre. PASS when used <= 0.30.
Checks with no margin by construction (ber_errors, toggle_diff, osc_flag, model_warnings) pass when the extracted value
meets the limit. A GAIN of margin over 30 % is listed and explained, not failed. Spread checks use the same rule on the
spread. The systematic offset added by the layout (TB3_trip off_v delta) is compared with 30 % of the TB3_off window
margin. D-012 is judged on the absolute limits (A1 >= 4, TB4 limits, TB5 eye limits) at ff/125C/3.6 V, VIC 0.05 V.
Evaluator: `sim/tbl/evaluate.py` -> `results/post_layout/tbl.json`, `TBL.md`.

## Finding: the T10 RC netlists counted every coupling twice (Magic 8.3.636 extresist)

Diagnosis of the TB4 slow-down (`.scratch/t11/diag_tb4.py`, `node_cap_ac.py`, `lane_res.py`, `c_vs_rc.py`, `rc_test*.py`):
- Stage by stage (tt, VIC 0.05 V, VID 100 mV, rise/fall): pre 3.46/3.71 ns, C-only 5.12/5.51, RC 5.91/6.42; the
  hysteresis stage takes the largest part (+0.7-0.8 ns C-only), then stage 3, stage 1, the output chain.
- The extracted resistances are small (largest element 83 ohm, largest per-net sum 1.8 kohm over 80 elements): they
  cannot explain the 0.9 ns between C-only and RC.  The RC netlist carries 4304 fF of wiring C against 2843 fF in the
  C-only one: for every net that extresist splits, the capacitance to VSS equals that net's whole C-coupled total
  (oa 27.56 fF, d2a 24.04, d3 14.41: exactly the C-only totals) while all coupling capacitors are written as well; the
  n-well node of the PMOS pair (tp) lost its 103 fF well capacitance and all its couplings.
- `ext2sim -p` before extresist (the sak-pex.sh full-RC flow) gives the identical netlist; a decoupled RC extraction
  (`extract no coupling`) drops the capacitance of every split net.  The Magic tech file gives diffusion no area cap
  (no double count of junctions); the n-well has 120 aF/um2 (the tp well capacitance is real).
- Fix: `check.rc_repair()` keeps the RC netlist's devices and resistor networks and takes the capacitance from the
  C-coupled extraction of the same layout (ground capacitors of each net and coupling capacitors of each net pair
  scaled to the C extraction's totals, lost pairs added between representative nodes).  On the lane: every one of the
  145 net-pair totals equals the C extraction (largest relative error 3e-6), 3125 resistors kept.
  `run_macro.py --stage pex` redoes step 6 with the repair on the delivered GDS (same sha256).
- The TBL run started on the double-counted netlist was stopped (op, ac, trip-pre had finished); it is re-run.
- What stays true: with the correct capacitance the slow-down is the C-only one, +49 % at that point (3.71 -> 5.54 ns,
  43 % of the margin to 8 ns); node capacitance on the chain is +35 to +120 % (effective, AC at 1 GHz).  The pre-layout
  netlist carries no wiring estimate at all (sizing assumed cw = 10 fF on oa/ob in its pole estimate only; extracted
  wiring is 27.6 fF there) and models junctions with 0.18 um of diffusion per side (layout: about 0.27 um average).
