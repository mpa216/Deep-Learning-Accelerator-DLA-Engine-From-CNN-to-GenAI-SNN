# tb7_idle

**Overall: PASS**

TB7: idle inputs on all three lanes: open (driver removed, 1 Mohm to the common mode), terminated (VID = 0, 50 ohm source + 100 ohm termination), shorted (P = N), 7 VIC; terminated runs also drift the source +-100 mV slowly. v0: no failsafe guarantee, the held state is reported

Runs: **105** (ok 105); 0 reused from cache.

## Worst case per metric

| metric | limit | worst run | value | margin | verdict |
|---|---|---|---|---|---|
| osc_flag | - .. 0 | `ff_m40c_3v60__vic0.05_term0` | **0** | 0 | PASS |
| min_pulse_s (ns) | 2 .. - | `ff_m40c_3v60__vic0.6_term1` | **500** | 498 | PASS |

## All runs

| run | corner | term | vic | status | osc_flag | min_pulse_s (ns) | drift_toggles | held_state | n_high | n_mid | out_end_v | out_final_v | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `tt_27c_3v30__vic0.05_term0` | tt_27c_3v30 | 0 | 0.05 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 9.162e-10 | PASS |
| `tt_27c_3v30__vic0.05_term1` | tt_27c_3v30 | 1 | 0.05 | ok | 0 | 500.2 | 2 | 0 | 0 | 0 | 9.141e-10 | 9.136e-10 | PASS |
| `tt_27c_3v30__vic0.05_term2` | tt_27c_3v30 | 2 | 0.05 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 9.141e-10 | PASS |
| `tt_27c_3v30__vic0.3_term0` | tt_27c_3v30 | 0 | 0.3 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 9.162e-10 | PASS |
| `tt_27c_3v30__vic0.3_term1` | tt_27c_3v30 | 1 | 0.3 | ok | 0 | 500.2 | 2 | 0 | 0 | 0 | 9.141e-10 | 9.136e-10 | PASS |
| `tt_27c_3v30__vic0.3_term2` | tt_27c_3v30 | 2 | 0.3 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 9.141e-10 | PASS |
| `tt_27c_3v30__vic0.6_term0` | tt_27c_3v30 | 0 | 0.6 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 9.162e-10 | PASS |
| `tt_27c_3v30__vic0.6_term1` | tt_27c_3v30 | 1 | 0.6 | ok | 0 | 500.2 | 2 | 0 | 0 | 0 | 9.141e-10 | 9.136e-10 | PASS |
| `tt_27c_3v30__vic0.6_term2` | tt_27c_3v30 | 2 | 0.6 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 9.141e-10 | PASS |
| `tt_27c_3v30__vic1.2_term0` | tt_27c_3v30 | 0 | 1.2 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 9.162e-10 | PASS |
| `tt_27c_3v30__vic1.2_term1` | tt_27c_3v30 | 1 | 1.2 | ok | 0 | 500.2 | 2 | 0 | 0 | 0 | 9.141e-10 | 9.165e-10 | PASS |
| `tt_27c_3v30__vic1.2_term2` | tt_27c_3v30 | 2 | 1.2 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 9.162e-10 | PASS |
| `tt_27c_3v30__vic1.8_term0` | tt_27c_3v30 | 0 | 1.8 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 9.162e-10 | PASS |
| `tt_27c_3v30__vic1.8_term1` | tt_27c_3v30 | 1 | 1.8 | ok | 0 | 500.2 | 2 | 0 | 0 | 0 | 9.141e-10 | 9.135e-10 | PASS |
| `tt_27c_3v30__vic1.8_term2` | tt_27c_3v30 | 2 | 1.8 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 9.141e-10 | PASS |
| `tt_27c_3v30__vic2.1_term0` | tt_27c_3v30 | 0 | 2.1 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 9.162e-10 | PASS |
| `tt_27c_3v30__vic2.1_term1` | tt_27c_3v30 | 1 | 2.1 | ok | 0 | 500.2 | 2 | 0 | 0 | 0 | 9.141e-10 | 9.135e-10 | PASS |
| `tt_27c_3v30__vic2.1_term2` | tt_27c_3v30 | 2 | 2.1 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 9.141e-10 | PASS |
| `tt_27c_3v30__vic2.35_term0` | tt_27c_3v30 | 0 | 2.35 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 9.162e-10 | PASS |
| `tt_27c_3v30__vic2.35_term1` | tt_27c_3v30 | 1 | 2.35 | ok | 0 | 500.2 | 2 | 0 | 0 | 0 | 9.141e-10 | 9.136e-10 | PASS |
| `tt_27c_3v30__vic2.35_term2` | tt_27c_3v30 | 2 | 2.35 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 9.141e-10 | PASS |
| `ss_125c_3v00__vic0.05_term0` | ss_125c_3v00 | 0 | 0.05 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 4.904e-09 | PASS |
| `ss_125c_3v00__vic0.05_term1` | ss_125c_3v00 | 1 | 0.05 | ok | 0 | 500.4 | 2 | 0 | 0 | 0 | 4.904e-09 | 4.905e-09 | PASS |
| `ss_125c_3v00__vic0.05_term2` | ss_125c_3v00 | 2 | 0.05 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 4.904e-09 | PASS |
| `ss_125c_3v00__vic0.3_term0` | ss_125c_3v00 | 0 | 0.3 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 4.904e-09 | PASS |
| `ss_125c_3v00__vic0.3_term1` | ss_125c_3v00 | 1 | 0.3 | ok | 0 | 500.4 | 2 | 0 | 0 | 0 | 4.904e-09 | 4.905e-09 | PASS |
| `ss_125c_3v00__vic0.3_term2` | ss_125c_3v00 | 2 | 0.3 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 4.904e-09 | PASS |
| `ss_125c_3v00__vic0.6_term0` | ss_125c_3v00 | 0 | 0.6 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 4.904e-09 | PASS |
| `ss_125c_3v00__vic0.6_term1` | ss_125c_3v00 | 1 | 0.6 | ok | 0 | 500.4 | 2 | 0 | 0 | 0 | 4.904e-09 | 4.905e-09 | PASS |
| `ss_125c_3v00__vic0.6_term2` | ss_125c_3v00 | 2 | 0.6 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 4.904e-09 | PASS |
| `ss_125c_3v00__vic1.2_term0` | ss_125c_3v00 | 0 | 1.2 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 4.904e-09 | PASS |
| `ss_125c_3v00__vic1.2_term1` | ss_125c_3v00 | 1 | 1.2 | ok | 0 | 500.4 | 2 | 0 | 0 | 0 | 4.904e-09 | 4.904e-09 | PASS |
| `ss_125c_3v00__vic1.2_term2` | ss_125c_3v00 | 2 | 1.2 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 4.904e-09 | PASS |
| `ss_125c_3v00__vic1.8_term0` | ss_125c_3v00 | 0 | 1.8 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 4.904e-09 | PASS |
| `ss_125c_3v00__vic1.8_term1` | ss_125c_3v00 | 1 | 1.8 | ok | 0 | 500.4 | 2 | 0 | 0 | 0 | 4.904e-09 | 4.904e-09 | PASS |
| `ss_125c_3v00__vic1.8_term2` | ss_125c_3v00 | 2 | 1.8 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 4.904e-09 | PASS |
| `ss_125c_3v00__vic2.1_term0` | ss_125c_3v00 | 0 | 2.1 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 4.904e-09 | PASS |
| `ss_125c_3v00__vic2.1_term1` | ss_125c_3v00 | 1 | 2.1 | ok | 0 | 500.4 | 2 | 0 | 0 | 0 | 4.904e-09 | 4.904e-09 | PASS |
| `ss_125c_3v00__vic2.1_term2` | ss_125c_3v00 | 2 | 2.1 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 4.904e-09 | PASS |
| `ss_125c_3v00__vic2.35_term0` | ss_125c_3v00 | 0 | 2.35 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 4.904e-09 | PASS |
| `ss_125c_3v00__vic2.35_term1` | ss_125c_3v00 | 1 | 2.35 | ok | 0 | 500.4 | 2 | 0 | 0 | 0 | 4.904e-09 | 4.905e-09 | PASS |
| `ss_125c_3v00__vic2.35_term2` | ss_125c_3v00 | 2 | 2.35 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 4.904e-09 | PASS |
| `ff_m40c_3v60__vic0.05_term0` | ff_m40c_3v60 | 0 | 0.05 | ok | **0** (worst) | 1e+09 | n/a | 0 | 0 | 0 | n/a | 1.359e-09 | PASS |
| `ff_m40c_3v60__vic0.05_term1` | ff_m40c_3v60 | 1 | 0.05 | ok | 0 | 500.2 | 2 | 0 | 0 | 0 | 1.359e-09 | 1.359e-09 | PASS |
| `ff_m40c_3v60__vic0.05_term2` | ff_m40c_3v60 | 2 | 0.05 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 1.359e-09 | PASS |
| `ff_m40c_3v60__vic0.3_term0` | ff_m40c_3v60 | 0 | 0.3 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 1.359e-09 | PASS |
| `ff_m40c_3v60__vic0.3_term1` | ff_m40c_3v60 | 1 | 0.3 | ok | 0 | 500.2 | 2 | 0 | 0 | 0 | 1.359e-09 | 1.359e-09 | PASS |
| `ff_m40c_3v60__vic0.3_term2` | ff_m40c_3v60 | 2 | 0.3 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 1.359e-09 | PASS |
| `ff_m40c_3v60__vic0.6_term0` | ff_m40c_3v60 | 0 | 0.6 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 1.359e-09 | PASS |
| `ff_m40c_3v60__vic0.6_term1` | ff_m40c_3v60 | 1 | 0.6 | ok | 0 | **500** (worst) | 2 | 0 | 0 | 0 | 1.359e-09 | 1.359e-09 | PASS |
| `ff_m40c_3v60__vic0.6_term2` | ff_m40c_3v60 | 2 | 0.6 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 1.359e-09 | PASS |
| `ff_m40c_3v60__vic1.2_term0` | ff_m40c_3v60 | 0 | 1.2 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 1.359e-09 | PASS |
| `ff_m40c_3v60__vic1.2_term1` | ff_m40c_3v60 | 1 | 1.2 | ok | 0 | 500.2 | 2 | 0 | 0 | 0 | 1.359e-09 | 1.359e-09 | PASS |
| `ff_m40c_3v60__vic1.2_term2` | ff_m40c_3v60 | 2 | 1.2 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 1.359e-09 | PASS |
| `ff_m40c_3v60__vic1.8_term0` | ff_m40c_3v60 | 0 | 1.8 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 1.359e-09 | PASS |
| `ff_m40c_3v60__vic1.8_term1` | ff_m40c_3v60 | 1 | 1.8 | ok | 0 | 500 | 2 | 0 | 0 | 0 | 1.359e-09 | 1.359e-09 | PASS |
| `ff_m40c_3v60__vic1.8_term2` | ff_m40c_3v60 | 2 | 1.8 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 1.359e-09 | PASS |
| `ff_m40c_3v60__vic2.1_term0` | ff_m40c_3v60 | 0 | 2.1 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 1.359e-09 | PASS |
| `ff_m40c_3v60__vic2.1_term1` | ff_m40c_3v60 | 1 | 2.1 | ok | 0 | 500.2 | 2 | 0 | 0 | 0 | 1.359e-09 | 1.359e-09 | PASS |
| `ff_m40c_3v60__vic2.1_term2` | ff_m40c_3v60 | 2 | 2.1 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 1.359e-09 | PASS |
| `ff_m40c_3v60__vic2.35_term0` | ff_m40c_3v60 | 0 | 2.35 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 1.359e-09 | PASS |
| `ff_m40c_3v60__vic2.35_term1` | ff_m40c_3v60 | 1 | 2.35 | ok | 0 | 500 | 2 | 0 | 0 | 0 | 1.359e-09 | 1.359e-09 | PASS |
| `ff_m40c_3v60__vic2.35_term2` | ff_m40c_3v60 | 2 | 2.35 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 1.359e-09 | PASS |
| `fs_27c_3v30__vic0.05_term0` | fs_27c_3v30 | 0 | 0.05 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 7.894e-10 | PASS |
| `fs_27c_3v30__vic0.05_term1` | fs_27c_3v30 | 1 | 0.05 | ok | 0 | 500.3 | 2 | 0 | 0 | 0 | 7.877e-10 | 7.897e-10 | PASS |
| `fs_27c_3v30__vic0.05_term2` | fs_27c_3v30 | 2 | 0.05 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 7.895e-10 | PASS |
| `fs_27c_3v30__vic0.3_term0` | fs_27c_3v30 | 0 | 0.3 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 7.894e-10 | PASS |
| `fs_27c_3v30__vic0.3_term1` | fs_27c_3v30 | 1 | 0.3 | ok | 0 | 500.2 | 2 | 0 | 0 | 0 | 7.877e-10 | 7.897e-10 | PASS |
| `fs_27c_3v30__vic0.3_term2` | fs_27c_3v30 | 2 | 0.3 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 7.895e-10 | PASS |
| `fs_27c_3v30__vic0.6_term0` | fs_27c_3v30 | 0 | 0.6 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 7.894e-10 | PASS |
| `fs_27c_3v30__vic0.6_term1` | fs_27c_3v30 | 1 | 0.6 | ok | 0 | 500.3 | 2 | 0 | 0 | 0 | 7.877e-10 | 7.897e-10 | PASS |
| `fs_27c_3v30__vic0.6_term2` | fs_27c_3v30 | 2 | 0.6 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 7.895e-10 | PASS |
| `fs_27c_3v30__vic1.2_term0` | fs_27c_3v30 | 0 | 1.2 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 7.894e-10 | PASS |
| `fs_27c_3v30__vic1.2_term1` | fs_27c_3v30 | 1 | 1.2 | ok | 0 | 500.3 | 2 | 0 | 0 | 0 | 7.876e-10 | 7.877e-10 | PASS |
| `fs_27c_3v30__vic1.2_term2` | fs_27c_3v30 | 2 | 1.2 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 7.877e-10 | PASS |
| `fs_27c_3v30__vic1.8_term0` | fs_27c_3v30 | 0 | 1.8 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 7.894e-10 | PASS |
| `fs_27c_3v30__vic1.8_term1` | fs_27c_3v30 | 1 | 1.8 | ok | 0 | 500.3 | 2 | 0 | 0 | 0 | 7.877e-10 | 7.876e-10 | PASS |
| `fs_27c_3v30__vic1.8_term2` | fs_27c_3v30 | 2 | 1.8 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 7.877e-10 | PASS |
| `fs_27c_3v30__vic2.1_term0` | fs_27c_3v30 | 0 | 2.1 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 7.894e-10 | PASS |
| `fs_27c_3v30__vic2.1_term1` | fs_27c_3v30 | 1 | 2.1 | ok | 0 | 500.3 | 2 | 0 | 0 | 0 | 7.877e-10 | 7.877e-10 | PASS |
| `fs_27c_3v30__vic2.1_term2` | fs_27c_3v30 | 2 | 2.1 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 7.877e-10 | PASS |
| `fs_27c_3v30__vic2.35_term0` | fs_27c_3v30 | 0 | 2.35 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 7.894e-10 | PASS |
| `fs_27c_3v30__vic2.35_term1` | fs_27c_3v30 | 1 | 2.35 | ok | 0 | 500.3 | 2 | 0 | 0 | 0 | 7.877e-10 | 7.877e-10 | PASS |
| `fs_27c_3v30__vic2.35_term2` | fs_27c_3v30 | 2 | 2.35 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 7.891e-10 | PASS |
| `sf_27c_3v30__vic0.05_term0` | sf_27c_3v30 | 0 | 0.05 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 1.351e-09 | PASS |
| `sf_27c_3v30__vic0.05_term1` | sf_27c_3v30 | 1 | 0.05 | ok | 0 | 500.2 | 2 | 0 | 0 | 0 | 1.351e-09 | 1.35e-09 | PASS |
| `sf_27c_3v30__vic0.05_term2` | sf_27c_3v30 | 2 | 0.05 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 1.351e-09 | PASS |
| `sf_27c_3v30__vic0.3_term0` | sf_27c_3v30 | 0 | 0.3 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 1.351e-09 | PASS |
| `sf_27c_3v30__vic0.3_term1` | sf_27c_3v30 | 1 | 0.3 | ok | 0 | 500.2 | 2 | 0 | 0 | 0 | 1.351e-09 | 1.35e-09 | PASS |
| `sf_27c_3v30__vic0.3_term2` | sf_27c_3v30 | 2 | 0.3 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 1.351e-09 | PASS |
| `sf_27c_3v30__vic0.6_term0` | sf_27c_3v30 | 0 | 0.6 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 1.351e-09 | PASS |
| `sf_27c_3v30__vic0.6_term1` | sf_27c_3v30 | 1 | 0.6 | ok | 0 | 500.1 | 2 | 0 | 0 | 0 | 1.351e-09 | 1.35e-09 | PASS |
| `sf_27c_3v30__vic0.6_term2` | sf_27c_3v30 | 2 | 0.6 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 1.351e-09 | PASS |
| `sf_27c_3v30__vic1.2_term0` | sf_27c_3v30 | 0 | 1.2 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 1.351e-09 | PASS |
| `sf_27c_3v30__vic1.2_term1` | sf_27c_3v30 | 1 | 1.2 | ok | 0 | 500.1 | 2 | 0 | 0 | 0 | 1.351e-09 | 1.35e-09 | PASS |
| `sf_27c_3v30__vic1.2_term2` | sf_27c_3v30 | 2 | 1.2 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 1.351e-09 | PASS |
| `sf_27c_3v30__vic1.8_term0` | sf_27c_3v30 | 0 | 1.8 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 1.351e-09 | PASS |
| `sf_27c_3v30__vic1.8_term1` | sf_27c_3v30 | 1 | 1.8 | ok | 0 | 500.2 | 2 | 0 | 0 | 0 | 1.351e-09 | 1.35e-09 | PASS |
| `sf_27c_3v30__vic1.8_term2` | sf_27c_3v30 | 2 | 1.8 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 1.351e-09 | PASS |
| `sf_27c_3v30__vic2.1_term0` | sf_27c_3v30 | 0 | 2.1 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 1.351e-09 | PASS |
| `sf_27c_3v30__vic2.1_term1` | sf_27c_3v30 | 1 | 2.1 | ok | 0 | 500.2 | 2 | 0 | 0 | 0 | 1.351e-09 | 1.35e-09 | PASS |
| `sf_27c_3v30__vic2.1_term2` | sf_27c_3v30 | 2 | 2.1 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 1.351e-09 | PASS |
| `sf_27c_3v30__vic2.35_term0` | sf_27c_3v30 | 0 | 2.35 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 1.351e-09 | PASS |
| `sf_27c_3v30__vic2.35_term1` | sf_27c_3v30 | 1 | 2.35 | ok | 0 | 500.1 | 2 | 0 | 0 | 0 | 1.351e-09 | 1.351e-09 | PASS |
| `sf_27c_3v30__vic2.35_term2` | sf_27c_3v30 | 2 | 2.35 | ok | 0 | 1e+09 | n/a | 0 | 0 | 0 | n/a | 1.351e-09 | PASS |
