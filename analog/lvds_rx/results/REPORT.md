# LVDS RX macro: verification report (generated)

Generated 2026-11-10 22:48:51 by flow/report.py from results/gates.json. Tier **smoke**, phases env, commit `6a92d76` (dirty flag unavailable: no working git in the container). Criteria: spec/gates.yaml sha256 `08ed08af51de...`.

## Waivers and fallback-ladder rungs

| id | date | kind | ladder / rung | trigger | measured | gate relaxed |
|---|---|---|---|---|---|---|
| D-001 | 2026-11-11 | note |   | T0 had to turn PLAN_V2 3.1/3.2 into countable gates; points the plan table left open were decided here (no limit changed) | n/a (design decisions, recorded in spec/gates.yaml at freeze) | none |

## Summary

**GREEN**: 2 PASS

| gate | phase | status | runs (found/expected) | worst margin | note |
|---|---|---|---|---|---|
| ENV | env | PASS | -/- | - |  |
| SELFTEST | env | PASS | 14/14 | 48.15 |  |

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
| harness_tests.run | json_value | all | 45 .. +inf | 1 | 45 | PASS |
| lint.failed | json_value | all | == 0 | 1 | 0 | PASS |
| omp.ok | json_value | all | == 1 | 1 | 1 | PASS |
| layout_toy.ok | json_value | all | == 1 | 1 | 1 | PASS |

### SELFTEST: placeholder testbench: PDK resistor/MOS over the harness corner sets (proves resistor corners follow process, wnflag set)

Status **PASS**. Runs 14 of 14 expected; run status counts {'ok': 14}; results `sim/tb_selftest/results/tb_selftest/results.json` (sha256 `88c6ad2a02e8...`).

| metric | kind | where | limit | n | worst | status |
|---|---|---|---|---|---|---|
| r_ohm | per_run | corner=['tt_27c_3v30', 'fs_27c_3v30', 'sf_27c_3v30'] | 1150 .. 1250 | 6 | 1202 | PASS |
| r_ohm | per_run | corner=ss_125c_3v00 | 1200 .. 1330 | 2 | 1263 | PASS |
| r_ohm | per_run | corner=ff_m40c_3v60 | 1130 .. 1240 | 2 | 1182 | PASS |
| r_ohm | per_run | corner=ss_125c_3v00_xrff | 820 .. 940 | 2 | 879.1 | PASS |
| r_ohm | per_run | corner=ff_m40c_3v60_xrss | 1550 .. 1700 | 2 | 1623 | PASS |
| idsat_a | report | all | reported | 14 | - | PASS |

## Environment (results/env.json)

| item | value |
|---|---|
| LUT selftest | 296/296 passed |
| LUT load test | vgs_v=0.8016, ft_hz=3.298e+09, id_w_a_per_um=2.702e-06 |
| harness tests | 45 run, 0 failures |
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

Wall time 0.1 s; sizes.spice sha256 `None`; LUT hash `b6c716358b26...`.
