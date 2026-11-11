# tb8_en

**Overall: PASS**

TB8: EN 0 -> 1 -> 0, EN = 0 supply current, VDD held below 2.0 V, supply ramps of 1 us and 100 us, EN rising mid-ramp, three lanes on one bias (two copies: inputs HIGH / LOW)

Runs: **30** (ok 30); 6 reused from cache.

## Worst case per metric

| metric | limit | worst run | value | margin | verdict |
|---|---|---|---|---|---|
| min_pulse_s (ns) | 2 .. - | `fs_27c_3v30__case1` | **3.034** | 1.034 | PASS |

## All runs

| run | corner | case | status | min_pulse_s (ns) | early_high_v | end_a_v | end_b_v | final_ok | high_phase_ok | idd_en0_a | min_pulse_cross_s | min_runt_width_s | n_runt | t_high_s | valid_time_s | vdd_at_out_rise_v | vout_off_v | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `tt_27c_3v30__case0` | tt_27c_3v30 | 0 | ok | 6 | n/a | 9.141e-10 | 9.141e-10 | 1 | n/a | 1.808e-08 | 1 | 6e-09 | 6 | n/a | n/a | n/a | 0.213 | PASS |
| `tt_27c_3v30__case1` | tt_27c_3v30 | 1 | ok | 4.01 | n/a | 1.9 | 5.271e-10 | 0 | n/a | n/a | 4.01e-09 | 1 | 0 | n/a | n/a | n/a | 1.903 | PASS |
| `tt_27c_3v30__case2` | tt_27c_3v30 | 2 | ok | 6 | n/a | 9.632e-10 | 9.143e-10 | 1 | 1 | n/a | 2.443e-08 | 6e-09 | 6 | n/a | 2.228e-08 | n/a | 3.402 | PASS |
| `tt_27c_3v30__case3` | tt_27c_3v30 | 3 | ok | 138.1 | n/a | 3.3 | 9.141e-10 | 1 | n/a | n/a | 1.381e-07 | 1 | 0 | 9e-07 | n/a | 0.844 | 3.3 | PASS |
| `tt_27c_3v30__case4` | tt_27c_3v30 | 4 | ok | 1.122e+04 | n/a | 3.3 | 9.138e-10 | 1 | n/a | n/a | 1.122e-05 | 1 | 0 | 9e-05 | n/a | 0.5992 | 3.3 | PASS |
| `tt_27c_3v30__case5` | tt_27c_3v30 | 5 | ok | 48.42 | 0.1246 | 3.3 | 1.237e-08 | 1 | n/a | n/a | 4.842e-08 | 4e-07 | 6 | n/a | 5.868e-06 | n/a | 3.3 | PASS |
| `ss_125c_3v00__case0` | ss_125c_3v00 | 0 | ok | 7 | n/a | 4.904e-09 | 4.904e-09 | 1 | n/a | 3.11e-08 | 1 | 7e-09 | 6 | n/a | n/a | n/a | 0.2117 | PASS |
| `ss_125c_3v00__case1` | ss_125c_3v00 | 1 | ok | 7.577 | n/a | 1.9 | 4.995e-09 | 0 | n/a | n/a | 7.577e-09 | 1 | 0 | n/a | n/a | n/a | 1.993 | PASS |
| `ss_125c_3v00__case2` | ss_125c_3v00 | 2 | ok | 7 | n/a | -8.037e-09 | 4.904e-09 | 1 | 1 | n/a | 3.314e-08 | 7e-09 | 6 | n/a | 2.958e-08 | n/a | 3.088 | PASS |
| `ss_125c_3v00__case3` | ss_125c_3v00 | 3 | ok | 128.8 | n/a | 3 | 4.904e-09 | 1 | n/a | n/a | 1.288e-07 | 1 | 0 | 9e-07 | n/a | 0.8321 | 3 | PASS |
| `ss_125c_3v00__case4` | ss_125c_3v00 | 4 | ok | 1.53e+04 | n/a | 3 | 4.904e-09 | 1 | n/a | n/a | 1.53e-05 | 1 | 0 | 9e-05 | n/a | 0.501 | 3 | PASS |
| `ss_125c_3v00__case5` | ss_125c_3v00 | 5 | ok | 64.13 | 0.08544 | 3 | 1.74e-08 | 1 | n/a | n/a | 6.413e-08 | 1 | 0 | n/a | 4.659e-06 | n/a | 3 | PASS |
| `ff_m40c_3v60__case0` | ff_m40c_3v60 | 0 | ok | 5 | n/a | 1.359e-09 | 1.359e-09 | 1 | n/a | 1.151e-08 | 1 | 5e-09 | 6 | n/a | n/a | n/a | 0.1966 | PASS |
| `ff_m40c_3v60__case1` | ff_m40c_3v60 | 1 | ok | 3.994 | n/a | 1.9 | 3.533e-10 | 0 | n/a | n/a | 3.994e-09 | 1 | 0 | n/a | n/a | n/a | 1.901 | PASS |
| `ff_m40c_3v60__case2` | ff_m40c_3v60 | 2 | ok | 5 | n/a | 1.526e-09 | 1.359e-09 | 1 | 1 | n/a | 1.628e-08 | 5e-09 | 6 | n/a | 1.641e-08 | n/a | 3.685 | PASS |
| `ff_m40c_3v60__case3` | ff_m40c_3v60 | 3 | ok | 134 | n/a | 3.6 | 1.359e-09 | 1 | n/a | n/a | 1.34e-07 | 1 | 0 | 9e-07 | n/a | 0.8021 | 3.6 | PASS |
| `ff_m40c_3v60__case4` | ff_m40c_3v60 | 4 | ok | 8334 | n/a | 3.6 | 1.359e-09 | 1 | n/a | n/a | 8.334e-06 | 1 | 0 | 9e-05 | n/a | 0.6146 | 3.6 | PASS |
| `ff_m40c_3v60__case5` | ff_m40c_3v60 | 5 | ok | 37.76 | 0.1345 | 3.6 | 1.631e-08 | 1 | n/a | n/a | 3.776e-08 | 3.8e-07 | 6 | n/a | 6.892e-06 | n/a | 3.603 | PASS |
| `fs_27c_3v30__case0` | fs_27c_3v30 | 0 | ok | 7 | n/a | 7.873e-10 | 7.873e-10 | 1 | n/a | 1.79e-08 | 1 | 7e-09 | 6 | n/a | n/a | n/a | 0.1841 | PASS |
| `fs_27c_3v30__case1` | fs_27c_3v30 | 1 | ok | **3.034** (worst) | n/a | 1.9 | 4.632e-10 | 0 | n/a | n/a | 3.034e-09 | 1 | 0 | n/a | n/a | n/a | 1.984 | PASS |
| `fs_27c_3v30__case2` | fs_27c_3v30 | 2 | ok | 7 | n/a | 8.12e-10 | 7.878e-10 | 1 | 1 | n/a | 2.338e-08 | 7e-09 | 6 | n/a | 2.129e-08 | n/a | 3.409 | PASS |
| `fs_27c_3v30__case3` | fs_27c_3v30 | 3 | ok | 171.2 | n/a | 3.3 | 7.876e-10 | 1 | n/a | n/a | 1.712e-07 | 1 | 0 | 9e-07 | n/a | 0.8209 | 3.3 | PASS |
| `fs_27c_3v30__case4` | fs_27c_3v30 | 4 | ok | 1.627e+04 | n/a | 3.3 | 7.871e-10 | 1 | n/a | n/a | 1.627e-05 | 1 | 0 | 9e-05 | n/a | 0.5976 | 3.3 | PASS |
| `fs_27c_3v30__case5` | fs_27c_3v30 | 5 | ok | 47.49 | 0.09003 | 3.3 | -9.539e-10 | 1 | n/a | n/a | 4.749e-08 | 5.4e-07 | 6 | n/a | 5.869e-06 | n/a | 3.3 | PASS |
| `sf_27c_3v30__case0` | sf_27c_3v30 | 0 | ok | 6 | n/a | 1.351e-09 | 1.351e-09 | 1 | n/a | 1.83e-08 | 1 | 6e-09 | 6 | n/a | n/a | n/a | 0.2159 | PASS |
| `sf_27c_3v30__case1` | sf_27c_3v30 | 1 | ok | 7.98 | n/a | 1.9 | 8.841e-10 | 0 | n/a | n/a | 7.98e-09 | 1 | 0 | n/a | n/a | n/a | 2.01 | PASS |
| `sf_27c_3v30__case2` | sf_27c_3v30 | 2 | ok | 6 | n/a | 1.359e-09 | 1.351e-09 | 1 | 1 | n/a | 2.528e-08 | 6e-09 | 6 | n/a | 2.365e-08 | n/a | 3.396 | PASS |
| `sf_27c_3v30__case3` | sf_27c_3v30 | 3 | ok | 97.38 | n/a | 3.3 | 1.351e-09 | 1 | n/a | n/a | 9.738e-08 | 1 | 0 | 9e-07 | n/a | 0.8855 | 3.3 | PASS |
| `sf_27c_3v30__case4` | sf_27c_3v30 | 4 | ok | 3044 | n/a | 3.3 | 1.35e-09 | 1 | n/a | n/a | 3.044e-06 | 1 | 0 | 9e-05 | n/a | 0.6209 | 3.3 | PASS |
| `sf_27c_3v30__case5` | sf_27c_3v30 | 5 | ok | 55.03 | 0.1501 | 3.3 | 3.364e-09 | 1 | n/a | n/a | 5.503e-08 | 3.4e-07 | 6 | n/a | 5.886e-06 | n/a | 3.3 | PASS |
