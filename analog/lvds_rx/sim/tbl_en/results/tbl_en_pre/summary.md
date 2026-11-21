# tbl_en_pre

**Overall: PASS**

post-layout gate TBL (pre): tb8_en with core = netlist/lvds_rx_core.spice

Runs: **18** (ok 18); 0 reused from cache.

## Worst case per metric

| metric | limit | worst run | value | margin | verdict |
|---|---|---|---|---|---|
| min_pulse_s (ns) | 2 .. - | `ff_125c_3v60__case3` | **16** | 14 | PASS |

## All runs

| run | corner | case | status | min_pulse_s (ns) | early_high_v | en1_valid_ok | end_a_v | end_b_v | final_ok | high_phase_ok | idd_en0_a | min_pulse_all_s | min_pulse_cross_s | min_runt_width_s | n_runt | t_high_s | valid_time_s | vdd_at_out_rise_v | vout_en1_v | vout_off_v | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `ff_125c_3v60__case0` | ff_125c_3v60 | 0 | ok | 1e+09 | n/a | n/a | 4.877e-07 | 4.877e-07 | 1 | n/a | 1.095e-07 | 3e-09 | 1 | 1 | 0 | n/a | n/a | n/a | n/a | 0.1439 | PASS |
| `ff_125c_3v60__case1` | ff_125c_3v60 | 1 | ok | 1e+09 | n/a | 1 | 1.9 | 3.917e-07 | 1 | n/a | n/a | 3e-09 | 1 | 1 | 0 | n/a | n/a | n/a | 1.902 | 0.1328 | PASS |
| `ff_125c_3v60__case2` | ff_125c_3v60 | 2 | ok | 20.94 | n/a | n/a | 4.928e-07 | 4.877e-07 | 1 | 1 | n/a | 3e-09 | 2.094e-08 | 1 | 0 | n/a | 1.28e-08 | n/a | n/a | 3.728 | PASS |
| `ff_125c_3v60__case3` | ff_125c_3v60 | 3 | ok | **16** (worst) | n/a | n/a | 3.6 | 4.877e-07 | 1 | n/a | n/a | 1.6e-08 | 1 | 1.6e-08 | 6 | 9e-07 | n/a | 0.773 | n/a | 3.6 | PASS |
| `ff_125c_3v60__case4` | ff_125c_3v60 | 4 | ok | 1362 | n/a | n/a | 3.6 | 4.877e-07 | 1 | n/a | n/a | 1.362e-06 | 1.362e-06 | 1 | 0 | 9e-05 | n/a | 0.5 | n/a | 3.6 | PASS |
| `ff_125c_3v60__case5` | ff_125c_3v60 | 5 | ok | 39.92 | 0.04375 | n/a | 3.6 | 4.901e-07 | 1 | n/a | n/a | 3.992e-08 | 3.992e-08 | 1 | 0 | n/a | 6.887e-06 | n/a | n/a | 3.6 | PASS |
| `ss_125c_3v00__case0` | ss_125c_3v00 | 0 | ok | 1e+09 | n/a | n/a | 4.979e-09 | 4.979e-09 | 1 | n/a | 1.026e-07 | 8e-09 | 1 | 1 | 0 | n/a | n/a | n/a | n/a | 0.2359 | PASS |
| `ss_125c_3v00__case1` | ss_125c_3v00 | 1 | ok | 1e+09 | n/a | 1 | 1.9 | 5.123e-09 | 1 | n/a | n/a | 1.1e-08 | 1 | 1 | 0 | n/a | n/a | n/a | 1.997 | 0.2263 | PASS |
| `ss_125c_3v00__case2` | ss_125c_3v00 | 2 | ok | 53.45 | n/a | n/a | 5.898e-09 | 4.979e-09 | 1 | 1 | n/a | 8e-09 | 5.345e-08 | 1 | 0 | n/a | 2.547e-08 | n/a | n/a | 3.138 | PASS |
| `ss_125c_3v00__case3` | ss_125c_3v00 | 3 | ok | 148 | n/a | n/a | 3 | 4.979e-09 | 1 | n/a | n/a | 1.48e-07 | 1 | 1.48e-07 | 6 | 9e-07 | n/a | 1.064 | n/a | 3 | PASS |
| `ss_125c_3v00__case4` | ss_125c_3v00 | 4 | ok | 540 | n/a | n/a | 3 | 4.979e-09 | 1 | n/a | n/a | 5.4e-07 | 8.132e-06 | 5.4e-07 | 6 | 9e-05 | n/a | 0.6284 | n/a | 3 | PASS |
| `ss_125c_3v00__case5` | ss_125c_3v00 | 5 | ok | 93.23 | 0.1024 | n/a | 3 | 8.157e-09 | 1 | n/a | n/a | 9.323e-08 | 9.323e-08 | 1.6e-07 | 6 | n/a | 4.667e-06 | n/a | n/a | 3 | PASS |
| `tt_27c_3v30__case0` | tt_27c_3v30 | 0 | ok | 1e+09 | n/a | n/a | 9.141e-10 | 9.141e-10 | 1 | n/a | 4.638e-08 | 7e-09 | 1 | 1 | 0 | n/a | n/a | n/a | n/a | 0.2344 | PASS |
| `tt_27c_3v30__case1` | tt_27c_3v30 | 1 | ok | 1e+09 | n/a | 1 | 1.9 | 5.548e-10 | 1 | n/a | n/a | 1e-08 | 1 | 1 | 0 | n/a | n/a | n/a | 1.985 | 0.2281 | PASS |
| `tt_27c_3v30__case2` | tt_27c_3v30 | 2 | ok | 38.61 | n/a | n/a | 7.977e-09 | 9.144e-10 | 1 | 1 | n/a | 7e-09 | 3.861e-08 | 1 | 0 | n/a | 1.813e-08 | n/a | n/a | 3.404 | PASS |
| `tt_27c_3v30__case3` | tt_27c_3v30 | 3 | ok | 39.63 | n/a | n/a | 3.3 | 9.144e-10 | 1 | n/a | n/a | 3.963e-08 | 3.963e-08 | 1.51e-07 | 6 | 9e-07 | n/a | 1.051 | n/a | 3.3 | PASS |
| `tt_27c_3v30__case4` | tt_27c_3v30 | 4 | ok | 5420 | n/a | n/a | 3.3 | 9.14e-10 | 1 | n/a | n/a | 5.42e-06 | 6.328e-06 | 5.42e-06 | 6 | 9e-05 | n/a | 0.6799 | n/a | 3.3 | PASS |
| `tt_27c_3v30__case5` | tt_27c_3v30 | 5 | ok | 71.09 | 0.1426 | n/a | 3.3 | 1.226e-08 | 1 | n/a | n/a | 7.109e-08 | 7.109e-08 | 5.8e-07 | 6 | n/a | 5.888e-06 | n/a | n/a | 3.3 | PASS |
