# LVDS RX macro: verification report (generated)

Generated 2026-11-11 15:02:33 by flow/report.py from results/gates.json. Tier **smoke**, phases env, prelayout, commit `ef2e65a` (dirty flag unavailable: no working git in the container). Criteria: spec/gates.yaml sha256 `08ed08af51de...`.

## Waivers and fallback-ladder rungs

| id | date | kind | ladder / rung | trigger | measured | gate relaxed |
|---|---|---|---|---|---|---|
| D-001 | 2026-11-11 | note |   | T0 had to turn PLAN_V2 3.1/3.2 into countable gates; points the plan table left open were decided here (no limit changed) | n/a (design decisions, recorded in spec/gates.yaml at freeze) | none |
| D-002 | 2026-11-11 | note |   | T1 stage-1 spike (PLAN_V2 S0, C4): is the hybrid input stage with dump devices viable over VIC 0.05-2.35 V? Answer measured: yes, no ladder rung taken (R5 stays at rung 0). | results/spike_stage1.json, 8 corners x 47 VIC x 3 variants (1128 runs, all ok). H1 (hybrid + dump): CM span 12-31 mV (limit +-150 mV), A1 at VIC 0.05/2.35 V >= 4.26, A1 spread <= 1.27x (limit 2.2x), min saturation margin 88 mV (limit 50 mV), f3dB >= 170 MHz. H0 (no dump): CM fails at 7 of 8 corners (span up to 1.20 V), A1 0.08 at ss/125C/2.35 V. Iterations 2 of 8 (results/iterations.jsonl). | none (gates.yaml untouched, sha unchanged) |
| D-003 | 2026-11-11 | note |   | T2 part 1 (sizing script + netlist): design choices the plan left open or that the first numbers forced; no frozen file changed, no ladder rung taken | sizing/sizing_report.md (127 assertions, 0 failed), sim/t2_op/results/op_table.md (60 runs worst5 x VIC 0.05/1.2/2.35 V x EN x VID, all ok; min saturation margin 109 mV), results/iterations.jsonl phase T2 | none (gates.yaml / spec.yaml sha unchanged) |
| D-004 | 2026-11-11 | note |   | T2 part 2: TB1/TB2 benches, LUT-vs-SPICE table, S1 shake-down (PMOS-only stage 1) | results/gates.json (TB1 147/147, TB2 35/35 PASS at smoke), results/shakedown_s1.md, sim/tb1_op/results/lut_vs_spice.md, results/iterations.jsonl phase T2 block stage3_pole | none (gates.yaml / spec.yaml unchanged); no ladder rung taken |

## Summary

**NOT GREEN**: 1 NOT_APPLICABLE, 7 NOT_RUN, 12 PASS

| gate | phase | status | runs (found/expected) | worst margin | note |
|---|---|---|---|---|---|
| ENV | env | PASS | -/- | - |  |
| SELFTEST | env | PASS | 14/14 | 48.15 |  |
| SIZE | prelayout | PASS | -/- | - |  |
| TB0 | prelayout | PASS | -/- | - |  |
| TB1 | prelayout | PASS | 147/147 | 0 |  |
| TB2 | prelayout | PASS | 35/35 | 0.03564 |  |
| TB3_trip | prelayout | PASS | 30/30 | 0.0025 |  |
| TB3_off | prelayout | PASS | 450/450 | 0.05775 |  |
| TB3_hmc | prelayout | NOT_RUN | -/- | - | MISSING: testbench spec sim/tb3_hmc/tb3_hmc.json not written yet |
| TB4 | prelayout | PASS | 70/70 | 3.871e-10 |  |
| TB4b | prelayout | PASS | 70/70 | 6.71e-10 |  |
| TB5 | prelayout | PASS | 60/60 | 0 |  |
| TB6 | prelayout | NOT_RUN | -/- | - | MISSING: testbench spec sim/tb6_cm_supply/tb6_cm_supply.json not written yet |
| TB7 | prelayout | NOT_RUN | -/- | - | MISSING: testbench spec sim/tb7_idle/tb7_idle.json not written yet |
| TB7_mc | prelayout | NOT_RUN | -/- | - | MISSING: testbench spec sim/tb7_idle_mc/tb7_idle_mc.json not written yet |
| TB8 | prelayout | NOT_RUN | -/- | - | MISSING: testbench spec sim/tb8_en/tb8_en.json not written yet |
| TB9 | prelayout | NOT_RUN | -/- | - | MISSING: testbench spec sim/tb9_input/tb9_input.json not written yet |
| TB10 | prelayout | NOT_RUN | -/- | - | MISSING: testbench spec sim/tb10_lanes/tb10_lanes.json not written yet |
| TB11 | prelayout | NOT_APPLICABLE | -/- | - | CONDITION: needs ladder R6 rung >= 1 (not taken) |
| TB12 | prelayout | PASS | 40/40 | 0 |  |

## Gates

### ENV: make check: tools, LUT load + self-test, harness tests, lint, OMP exports

Status **PASS**. 

| metric | kind | where | limit | n | worst | status |
|---|---|---|---|---|---|---|
| lut_selftest.failed | json_value | all | == 0 | 1 | 0 | PASS |
| lut_selftest.passed | json_value | all | 296 .. +inf | 1 | 296 | PASS |
| lut_load.vgs_v | json_value | all | 0.7996 .. 0.8036 | 1 | 0.8016 | PASS |
| lut_load.ft_hz | json_value | all | 3.25e+09 .. 3.35e+09 | 1 | 3.298e+09 | PASS |
| lut_load.id_w_a_per_um | json_value | all | 2.67e-06 .. 2.74e-06 | 1 | 2.702e-06 | PASS |
| harness_tests.failures | json_value | all | == 0 | 1 | 0 | PASS |
| harness_tests.run | json_value | all | 45 .. +inf | 1 | 46 | PASS |
| lint.failed | json_value | all | == 0 | 1 | 0 | PASS |
| omp.ok | json_value | all | == 1 | 1 | 1 | PASS |
| layout_toy.ok | json_value | all | == 1 | 1 | 1 | PASS |

### SELFTEST: placeholder testbench: PDK resistor/MOS over the harness corner sets (proves resistor corners follow process, wnflag set)

Status **PASS**. Runs 14 of 14 expected; run status counts {'ok': 14}; results `sim/tb_selftest/results/tb_selftest/results.json` (sha256 `a1d3ee42e2db...`).

| metric | kind | where | limit | n | worst | status |
|---|---|---|---|---|---|---|
| r_ohm | per_run | corner=['tt_27c_3v30', 'fs_27c_3v30', 'sf_27c_3v30'] | 1150 .. 1250 | 6 | 1202 | PASS |
| r_ohm | per_run | corner=ss_125c_3v00 | 1200 .. 1330 | 2 | 1263 | PASS |
| r_ohm | per_run | corner=ff_m40c_3v60 | 1130 .. 1240 | 2 | 1182 | PASS |
| r_ohm | per_run | corner=ss_125c_3v00_xrff | 820 .. 940 | 2 | 879.1 | PASS |
| r_ohm | per_run | corner=ff_m40c_3v60_xrss | 1550 .. 1700 | 2 | 1623 | PASS |
| idsat_a | report | all | reported | 14 | - | PASS |

### SIZE: sizing script asserts, current tally, nf-not-m

Status **PASS**. 

| metric | kind | where | limit | n | worst | status |
|---|---|---|---|---|---|---|
| asserts_failed | json_value | all | == 0 | 1 | 0 | PASS |
| nf_m_violations | json_value | all | == 0 | 1 | 0 | PASS |
| tally_ok | json_value | all | == 1 | 1 | 1 | PASS |

### TB0: analog pad: C_pad and pin leakage (built before T0)

Status **PASS**. 

| metric | kind | where | limit | n | worst | status |
|---|---|---|---|---|---|---|
| rows[*].C_100MHz_fF | json_value | all | == 15 | 15 | 15 | PASS |
| rows[*].C_100MHz_fF | json_value | all | -inf .. 1.2e-12 | 15 | 1.15e-12 | PASS |
| rows[*].I_leak_A | json_value | all | -inf .. 1e-06 | 15 | 4.473e-11 | PASS |

### TB1: operating point: headroom, LUT-vs-SPICE, stage-1 CM, currents, node range

Status **PASS**. Runs 147 of 147 expected; run status counts {'ok': 147}; results `sim/tb1_op/results/tb1_op/results.json` (sha256 `f7a00a31d667...`).

| metric | kind | where | limit | n | worst | status |
|---|---|---|---|---|---|---|
| min_headroom_v | per_run | all | 0.05 .. +inf | 147 | 0.0521 | PASS |
| gmid_err | per_run | all | -inf .. 0.1 | 147 | 0.02217 | PASS |
| id_err | per_run | all | -inf .. 0.1 | 147 | 0.03458 | PASS |
| vgs_err_v | per_run | all | -inf .. 0.03 | 147 | 0.008553 | PASS |
| s1_cm_dev_v | per_run | all | -inf .. 0.15 | 147 | 0.01295 | PASS |
| np_overlap_v | per_run | all | 0.25 .. +inf | 147 | 0.6787 | PASS |
| vnode_min_v | per_run | all | -0.3 .. +inf | 147 | 6.78e-11 | PASS |
| vnode_over_vdd_v | per_run | all | -inf .. 0.3 | 147 | 0 | PASS |
| model_warnings | per_run | all | -inf .. 0 | 147 | 0 | PASS |
| i_lane_a | per_run | all | -inf .. 0.0015 | 147 | 0.0007093 | PASS |
| i_bias_a | per_run | all | -inf .. 0.0003 | 147 | 0.0002201 | PASS |

### TB2: AC: stage-1 gain, bandwidth

Status **PASS**. Runs 35 of 35 expected; run status counts {'ok': 35}; results `sim/tb2_ac/results/tb2_ac/results.json` (sha256 `5ea1a5c452d3...`).

| metric | kind | where | limit | n | worst | status |
|---|---|---|---|---|---|---|
| a1 | per_run | vic=[0.05, 2.35] | 4 .. +inf | 10 | 5.489 | PASS |
| a1 | spread | all | -inf .. 2.2 | 5 | 1.121 | PASS |
| f3db_stage_over_dr | per_run | all | 0.8 .. +inf | 35 | 0.8356 | PASS |
| f3db_chain_hz | per_run | all | 5e+07 .. +inf | 35 | 5.55e+07 | PASS |
| cmrr_db | report | all | reported | 35 | - | PASS |
| psrr_db | report | all | reported | 35 | - | PASS |

### TB3_trip: hysteresis by DC sweeps (up from -150 mV, down from +150 mV, continuation)

Status **PASS**. Runs 30 of 30 expected; run status counts {'ok': 30}; results `sim/tb3_trip/results/tb3_trip/results.json` (sha256 `ac7f9630f407...`).

| metric | kind | where | limit | n | worst | status |
|---|---|---|---|---|---|---|
| vh_v | per_run | all | 0.008 .. 0.025 | 30 | 0.0105 | PASS |
| dvh_dvdd | report | all | reported | 30 | - | PASS |
| dvtrip_dvdd | report | all | reported | 30 | - | PASS |

### TB3_off: DC input-referred offset Monte Carlo, hysteresis off (N = 1000)

Status **PASS**. Runs 450 of 450 expected; run status counts {'ok': 450}; results `sim/tb3_off/results/tb3_off/results.json` (sha256 `8b9154a8c840...`).

| metric | kind | where | limit | n | worst | status |
|---|---|---|---|---|---|---|
| vos_v | mc_offset_window | all | <= 0.095 (k=6, extra=0.0155) | 15 | 0.03725 | PASS |
| vos_v | report | all | reported | 450 | - | PASS |

### TB3_hmc: transient hysteresis Monte Carlo: hysteresis spread, functional at VID = +-100 mV (N = 100)

Status **NOT_RUN**. 

- MISSING: testbench spec sim/tb3_hmc/tb3_hmc.json not written yet

### TB4: propagation delay, pulse skew, DCD, output edge

Status **PASS**. Runs 70 of 70 expected; run status counts {'ok': 70}; results `sim/tb4_pd/results/tb4_pd/results.json` (sha256 `6a7d346c43c3...`).

| metric | kind | where | limit | n | worst | status |
|---|---|---|---|---|---|---|
| tpd_s | per_run | vid=0.35 | -inf .. 5e-09 | 35 | 4.613e-09 | PASS |
| tpd_s | per_run | vid=0.1 | -inf .. 8e-09 | 35 | 5.596e-09 | PASS |
| dcd_ui | per_run | vid=0.35 | -inf .. 0.05 | 35 | 0.009889 | PASS |
| dcd_ui | per_run | vid=0.1 | -inf .. 0.1 | 35 | 0.06296 | PASS |
| edge_10_90_s | per_run | all | -inf .. 1e-09 | 70 | 1.164e-10 | PASS |
| tpd_s | spread | vid=0.35 | -inf .. 1e-09 | 5 | 3.753e-10 | PASS |

### TB4b: delta tPD over VID 200-450 mV at fixed VIC (the VID set of TB4 cannot show it)

Status **PASS**. Runs 70 of 70 expected; run status counts {'ok': 70}; results `sim/tb4b_pd_vid/results/tb4b_pd_vid/results.json` (sha256 `ba56c17c016d...`).

| metric | kind | where | limit | n | worst | status |
|---|---|---|---|---|---|---|
| tpd_s | spread | all | -inf .. 1e-09 | 35 | 3.29e-10 | PASS |

### TB5: eye at 100 and 200 Mb/s through the full input network

Status **PASS**. Runs 60 of 60 expected; run status counts {'ok': 60}; results `sim/tb5_eye/results/tb5_eye/results.json` (sha256 `48a95cb185ed...`).

| metric | kind | where | limit | n | worst | status |
|---|---|---|---|---|---|---|
| ber_errors | per_run | all | -inf .. 0 | 60 | 0 | PASS |
| toggle_diff | per_run | all | -inf .. 0 | 60 | 0 | PASS |
| eye_open_ui | per_run | rate=100000000.0 | 0.6 .. +inf | 30 | 0.9736 | PASS |
| eye_open_ui | per_run | rate=100000000.0, vid=0.1, corner=tt_27c_3v30 | 0.7 .. +inf | 3 | 0.995 | PASS |
| eye_open_ui | per_run | rate=200000000.0, vid=0.35, corner=['tt_27c_3v30', 'ss_125c_3v00'] | 0.5 .. +inf | 6 | 0.9284 | PASS |
| dcd_ui | report | all | reported | 60 | - | PASS |

### TB6: CM step, supply ripple, current spikes

Status **NOT_RUN**. 

- MISSING: testbench spec sim/tb6_cm_supply/tb6_cm_supply.json not written yet

### TB7: idle inputs: stable held state, no oscillation, no pulse < 2 ns (v0)

Status **NOT_RUN**. 

- MISSING: testbench spec sim/tb7_idle/tb7_idle.json not written yet

### TB7_mc: idle inputs under mismatch (N = 100)

Status **NOT_RUN**. 

- MISSING: testbench spec sim/tb7_idle_mc/tb7_idle_mc.json not written yet

### TB8: EN and supply ramps

Status **NOT_RUN**. 

- MISSING: testbench spec sim/tb8_en/tb8_en.json not written yet

### TB9: input leakage and balance

Status **NOT_RUN**. 

- MISSING: testbench spec sim/tb9_input/tb9_input.json not written yet

### TB10: three lanes: skew and crosstalk

Status **NOT_RUN**. 

- MISSING: testbench spec sim/tb10_lanes/tb10_lanes.json not written yet

### TB11: bias loop stability (only if a constant-gm loop exists)

Status **NOT_APPLICABLE**. 

- CONDITION: needs ladder R6 rung >= 1 (not taken)

### TB12: package sweep L {1,5} nH x C {0.5,1.5} pF at the worst corners

Status **PASS**. Runs 40 of 40 expected; run status counts {'ok': 40}; results `sim/tb12_pkg/results/tb12_pkg/results.json` (sha256 `e193df32c8d5...`).

| metric | kind | where | limit | n | worst | status |
|---|---|---|---|---|---|---|
| ber_errors | per_run | all | -inf .. 0 | 40 | 0 | PASS |
| eye_open_ui | per_run | all | 0.5 .. +inf | 40 | 0.9268 | PASS |

## Environment (results/env.json)

| item | value |
|---|---|
| LUT selftest | 296/296 passed |
| LUT load test | vgs_v=0.8016, ft_hz=3.298e+09, id_w_a_per_um=2.702e-06 |
| harness tests | 46 run, 0 failures |
| OMP exports | ok=1 {'OMP_NUM_THREADS': '1', 'OMP_THREAD_LIMIT': '1', 'OMP_WAIT_POLICY': 'PASSIVE'} |
| lint | 0 findings {'matched': 0, 'ngspice': 0, 'sizes': 0, 'pins': 0, 'frozen': 0} |
| toy layout regression | ok=1 |
| tool ngspice | ****** |
| tool python3 | Python 3.12.3 |
| tool make | GNU Make 4.3 |
| tool magic | 8.3.636 |
| tool netgen | present |
| tool klayout | KLayout 0.30.8 |
| tool openroad | 26Q2-254-g61932e897 |
| tool sta | 3.1.0 |
| tool iverilog | Icarus Verilog version 14.0 (devel) (s20251012-145-g9b0d46b4-dirty) |
| tool yosys | Yosys 0.64 (git sha1 6d2c445ae, g++ 13.3.0-6ubuntu2~24.04.1 -fPIC -O3) |

## Gate mutation tests (results/mutants.json)

| mutant | target | control | mutant result | detected |
|---|---|---|---|---|
| meas_failed | harness status -> gate STATUS check | PASS | control PASS; mutant FAIL ['NODATA', 'STATUS'] {'meas_failed': 10} | YES |
| run_removed | expected-run-count check | PASS | control PASS (10 runs); mutant FAIL ['COUNT'] expected 10 found 9 | YES |
| limit_exceeded | per_run limit check | PASS | control PASS; mutant FAIL ['LIMIT'] | YES |
| stale_sizes_hash | lint rule sizes / assert_fresh_sizes (netlist build refusal) | PASS | control findings []; mutant findings 1, build refused=True | YES |
| m_not_nf | lint rule matched | PASS | mutant findings: [".scratch/mutants/m_not_nf/bad.spice:2: matched-device rule: 'm=4' (use one device with nf fingers): xm1 d g s b nfet_03v3 w=5u l=0.5u m=4"] | YES |
| bare_ngspice | lint rule ngspice | PASS | mutant findings: 1 | YES |
| frozen_edit | lint rule frozen | PASS | control []; edit findings 1; with decisions entry [] | YES |
| pin_mismatch | lint rule pins | PASS | control []; mutant ["netlist/lvds_rx_core.spice: pins ['RX0_N', 'RX0_O', 'RX0_P', 'RX1_N', 'RX1_O', 'RX1_P', 'RX2_N', 'RX2_O', 'RX2_P', 'VDD', 'VSS'] differ from spec/pins.yaml ['EN', 'RX0_N', 'RX0_O', 'RX0_P', 'RX1_N', 'RX1_O', 'RX1_P', 'RX2_N', 'RX2_O', 'RX2_P', 'VDD', 'VSS']"] | YES |

## Manifest

Wall time 1371 s; sizes.spice sha256 `96c2d8be8e8b95aa60f30bc4fe7317f8de2517792131e8ee0e979257a8f7b8d6`; LUT hash `58dac49d5f90...`.
