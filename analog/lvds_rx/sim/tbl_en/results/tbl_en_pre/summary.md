# tbl_en_pre

**Overall: PASS**

post-layout gate TBL (pre): tb8_en with core = netlist/lvds_rx_core.spice

Runs: **18** (ok 18); 0 reused from cache.

## Worst case per metric

| metric | limit | worst run | value | margin | verdict |
|---|---|---|---|---|---|
| min_pulse_s (ns) | 2 .. - | `ff_125c_3v60__case2` | **9.907** | 7.907 | PASS |

## All runs

| run | corner | case | status | min_pulse_s (ns) | early_high_v | en1_valid_ok | end_a_v | end_b_v | final_ok | high_phase_ok | idd_en0_a | min_pulse_all_s | min_pulse_cross_s | min_runt_width_s | n_runt | t_high_s | valid_time_s | vdd_at_out_rise_v | vout_en1_v | vout_off_v | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `ff_125c_3v60__case0` | ff_125c_3v60 | 0 | ok | 1e+09 | n/a | n/a | 4.877e-07 | 4.877e-07 | 1 | n/a | 6.041e-08 | 2e-09 | 1 | 1 | 0 | n/a | n/a | n/a | n/a | 0.1231 | PASS |
| `ff_125c_3v60__case1` | ff_125c_3v60 | 1 | ok | 1e+09 | n/a | 1 | 1.9 | 3.916e-07 | 1 | n/a | n/a | 2e-09 | 1 | 1 | 0 | n/a | n/a | n/a | 1.905 | 0.1111 | PASS |
| `ff_125c_3v60__case2` | ff_125c_3v60 | 2 | ok | **9.907** (worst) | n/a | n/a | 4.877e-07 | 4.877e-07 | 1 | 1 | n/a | 2e-09 | 9.907e-09 | 1 | 0 | n/a | 1.735e-08 | n/a | n/a | 3.686 | PASS |
| `ff_125c_3v60__case3` | ff_125c_3v60 | 3 | ok | 109.5 | n/a | n/a | 3.6 | 4.877e-07 | 1 | n/a | n/a | 1.095e-07 | 1.095e-07 | 1 | 0 | 9e-07 | n/a | 0.5361 | n/a | 3.6 | PASS |
| `ff_125c_3v60__case4` | ff_125c_3v60 | 4 | ok | 4740 | n/a | n/a | 3.6 | 4.877e-07 | 1 | n/a | n/a | 4.74e-06 | 4.74e-06 | 1 | 0 | 9e-05 | n/a | 0.5 | n/a | 3.6 | PASS |
| `ff_125c_3v60__case5` | ff_125c_3v60 | 5 | ok | 21.34 | 0.03686 | n/a | 3.6 | 4.956e-07 | 1 | n/a | n/a | 2.134e-08 | 2.134e-08 | 1 | 0 | n/a | 6.884e-06 | n/a | n/a | 3.6 | PASS |
| `ss_125c_3v00__case0` | ss_125c_3v00 | 0 | ok | 1e+09 | n/a | n/a | 4.904e-09 | 4.904e-09 | 1 | n/a | 3.114e-08 | 7e-09 | 1 | 1 | 0 | n/a | n/a | n/a | n/a | 0.2117 | PASS |
| `ss_125c_3v00__case1` | ss_125c_3v00 | 1 | ok | 1e+09 | n/a | 1 | 1.9 | 5.013e-09 | 1 | n/a | n/a | 7.577e-09 | 1 | 1 | 0 | n/a | n/a | n/a | 1.993 | 0.2043 | PASS |
| `ss_125c_3v00__case2` | ss_125c_3v00 | 2 | ok | 33.33 | n/a | n/a | -8.125e-09 | 4.904e-09 | 1 | 1 | n/a | 7e-09 | 3.333e-08 | 1 | 0 | n/a | 2.958e-08 | n/a | n/a | 3.09 | PASS |
| `ss_125c_3v00__case3` | ss_125c_3v00 | 3 | ok | 130 | n/a | n/a | 3 | 4.904e-09 | 1 | n/a | n/a | 1.3e-07 | 1.3e-07 | 1 | 0 | 9e-07 | n/a | 0.8321 | n/a | 3 | PASS |
| `ss_125c_3v00__case4` | ss_125c_3v00 | 4 | ok | 1.554e+04 | n/a | n/a | 3 | 4.904e-09 | 1 | n/a | n/a | 1.554e-05 | 1.554e-05 | 1 | 0 | 9e-05 | n/a | 0.501 | n/a | 3 | PASS |
| `ss_125c_3v00__case5` | ss_125c_3v00 | 5 | ok | 64.5 | 0.08544 | n/a | 3 | 1.738e-08 | 1 | n/a | n/a | 6.45e-08 | 6.45e-08 | 1 | 0 | n/a | 4.656e-06 | n/a | n/a | 3 | PASS |
| `tt_27c_3v30__case0` | tt_27c_3v30 | 0 | ok | 1e+09 | n/a | n/a | 9.144e-10 | 9.144e-10 | 1 | n/a | 1.804e-08 | 6e-09 | 1 | 1 | 0 | n/a | n/a | n/a | n/a | 0.213 | PASS |
| `tt_27c_3v30__case1` | tt_27c_3v30 | 1 | ok | 1e+09 | n/a | 1 | 1.9 | 5.549e-10 | 1 | n/a | n/a | 4.011e-09 | 1 | 1 | 0 | n/a | n/a | n/a | 1.903 | 0.2017 | PASS |
| `tt_27c_3v30__case2` | tt_27c_3v30 | 2 | ok | 24.43 | n/a | n/a | 9.55e-10 | 9.142e-10 | 1 | 1 | n/a | 6e-09 | 2.443e-08 | 1 | 0 | n/a | 2.228e-08 | n/a | n/a | 3.402 | PASS |
| `tt_27c_3v30__case3` | tt_27c_3v30 | 3 | ok | 139.1 | n/a | n/a | 3.3 | 9.14e-10 | 1 | n/a | n/a | 1.391e-07 | 1.391e-07 | 1 | 0 | 9e-07 | n/a | 0.844 | n/a | 3.3 | PASS |
| `tt_27c_3v30__case4` | tt_27c_3v30 | 4 | ok | 1.14e+04 | n/a | n/a | 3.3 | 9.139e-10 | 1 | n/a | n/a | 1.14e-05 | 1.14e-05 | 1 | 0 | 9e-05 | n/a | 0.5992 | n/a | 3.3 | PASS |
| `tt_27c_3v30__case5` | tt_27c_3v30 | 5 | ok | 48.55 | 0.1246 | n/a | 3.3 | 1.246e-08 | 1 | n/a | n/a | 4.855e-08 | 4.855e-08 | 4e-07 | 6 | n/a | 5.868e-06 | n/a | n/a | 3.3 | PASS |
