# T4 hand-over (2026-11-12): TB6-TB10 at the smoke tier

## Result
`make smoke` (container, via tools/cx) exits 0: 19 PASS, TB11 NOT_APPLICABLE. Run counts: TB6 20, TB7 105, TB7_mc 450, TB8 30, TB9 20, TB10 10 (plus T1-T3 gates unchanged and cached/re-run PASS).
Sizing script and gates.yaml / spec.yaml untouched. Two WAIVERS (no ladder rung covers them): D-007 (TB6 CM-step population) and D-008 (TB8 no UVLO); note D-006 (bench choices, ngspice stall, LVS-ref change). All in spec/decisions.yaml and printed at the top of results/REPORT.md.

## Key numbers
TB6 ripple/spike jitter <= 0.011 UI (0.1), CM step clear edges <= 0.003 UI, coincident edges 0.126-0.247 UI (reported); TB7 no oscillation/pulse in 555 runs, nominal held state LOW; TB8 IDD(EN=0) 18 nA (27C) / 31 nA (125C), valid <= 30 ns, min pulse 3.0 ns, EN=0 at 1.9 V -> output <= 0.21 V; TB9 <= 3.9 nA, balance 1e-15 A; TB10 skew 44 ps, 3-sigma 216 ps, crosstalk 0.0008 UI.

## How to run
`python3 sim/harness/cli.py run sim/<tb>/<tb>.json --corners worst5 --jobs 6` (add `--force` after changing only a hooks.py: the cache key is the deck text). TB8 cases take ~5 min (case 4, 100 us, is the long one); TB6 7 min; TB7_mc ~10 min.
Diagnostics: `tools/show_runs.py <results.json> metric,metric` (one line per run), `tools/count_held.py` (TB7 held states), `sim/tb6_cm_supply/analyze_edges.py <run_dir> <vdd>` (per-edge delay vs the nearest CM step), `sim/tb6_cm_supply/diag/` (internal-node plot of an edge hit by a down step; needs a rerun to regenerate d.txt).

## Things the next agent must know
1. TB6 case 0 gates edges >= 1 UI from every step (CLEAR_UI in hooks.py); `added_jitter_all_ui` and `hit_dev_max_ps` carry the strict all-edge numbers (worst 0.247 UI / 1.67 ns at ss/125C/3.0 V). If the owner wants the strict version gated, the lever is a faster stage-1 hand-over (tail current / pair size), which reopens T1-T3.
2. TB8 case 1 = copy b EN = 0 at 1.9 V (gated), copy a EN = 1 (reported: output is HIGH, the macro decodes). Integration note: EN must stay low until VDD >= 2.0 V. The EN = 0 output shows a 0.2 V bump during the supply ramp (limit 0.33 V): thin-ish margin.
3. ngspice stall with EN = 1 and a settled supply: `.option reltol=0.01` in TB7 and TB8 (cases 1, 3, 4). Do not edit those decks casually: a different deck text can move the stall to a different run (a first attempt with extra wrdata columns hung in case 3).
4. TB9 balance (1e-15 A) and TB10 crosstalk (0.0008 UI) are simulation-symmetry results; they test the shared bias and supply only, not the layout. Re-check in post-layout (TBL).
5. The LVS reference has XCVREF as nfet_03v3 (D = S = B = VSS); `netlist/check_lvs_ref.sh` PASS (158 devices, 77 nets). Layout LVS (T9/T10) should now match the cap leaf of T8b without a property workaround.
6. Not done (later tiers): full45 sweeps of TB7/TB8/TB9, MC N = 100 for TB7_mc, tb9_input_hot is run (reported) but not gated.
