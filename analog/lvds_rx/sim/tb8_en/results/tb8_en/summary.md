# tb8_en

**Overall: FAIL**

TB8: EN 0 -> 1 -> 0, EN = 0 supply current, VDD held below 2.0 V, supply ramps of 1 us and 100 us, EN rising mid-ramp, three lanes on one bias (two copies: inputs HIGH / LOW)

Runs: **270** (ok 251, timeout 19); 0 reused from cache.

## Worst case per metric

| metric | limit | worst run | value | margin | verdict |
|---|---|---|---|---|---|
| min_pulse_s (ns) | 2 .. - | `fs_m40c_3v30__case1` | **1.986** | -0.01396 | FAIL |

## All runs

| run | corner | case | status | min_pulse_s (ns) | early_high_v | en1_valid_ok | end_a_v | end_b_v | final_ok | high_phase_ok | idd_en0_a | min_pulse_cross_s | min_runt_width_s | n_runt | t_high_s | valid_time_s | vdd_at_out_rise_v | vout_en1_v | vout_off_v | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `tt_m40c_3v00__case0` | tt_m40c_3v00 | 0 | ok | 7 | n/a | n/a | 5.614e-10 | 5.614e-10 | 1 | n/a | 3.117e-08 | 1 | 7e-09 | 6 | n/a | n/a | n/a | n/a | 0.2294 | PASS |
| `tt_m40c_3v00__case1` | tt_m40c_3v00 | 1 | ok | 3.521 | n/a | 1 | 1.9 | 4.205e-10 | 1 | n/a | n/a | 3.521e-09 | 1.1e-08 | 3 | n/a | n/a | n/a | 1.983 | 0.2251 | PASS |
| `tt_m40c_3v00__case2` | tt_m40c_3v00 | 2 | ok | 7 | n/a | n/a | 5.936e-10 | 5.613e-10 | 1 | 1 | n/a | 3.16e-08 | 7e-09 | 6 | n/a | 2.425e-08 | n/a | n/a | 3.085 | PASS |
| `tt_m40c_3v00__case3` | tt_m40c_3v00 | 3 | ok | 151.5 | n/a | n/a | 3 | 5.614e-10 | 1 | n/a | n/a | 1.515e-07 | 1 | 0 | 9e-07 | n/a | 0.9274 | n/a | 3 | PASS |
| `tt_m40c_3v00__case4` | tt_m40c_3v00 | 4 | ok | 1.104e+04 | n/a | n/a | 3 | 5.62e-10 | 1 | n/a | n/a | 1.104e-05 | 1 | 0 | 9e-05 | n/a | 0.7452 | n/a | 3 | PASS |
| `tt_m40c_3v00__case5` | tt_m40c_3v00 | 5 | ok | 63.79 | 0.1735 | n/a | 3 | -4.807e-10 | 1 | n/a | n/a | 6.379e-08 | 1.28e-06 | 6 | n/a | 4.663e-06 | n/a | n/a | 3.003 | PASS |
| `tt_m40c_3v30__case0` | tt_m40c_3v30 | 0 | ok | 7 | n/a | n/a | 7.266e-10 | 7.266e-10 | 1 | n/a | 1.694e-08 | 1 | 7e-09 | 6 | n/a | n/a | n/a | n/a | 0.2346 | PASS |
| `tt_m40c_3v30__case1` | tt_m40c_3v30 | 1 | ok | 3.522 | n/a | 1 | 1.9 | 4.205e-10 | 1 | n/a | n/a | 3.522e-09 | 1.1e-08 | 3 | n/a | n/a | n/a | 1.982 | 0.2251 | PASS |
| `tt_m40c_3v30__case2` | tt_m40c_3v30 | 2 | ok | 7 | n/a | n/a | 8.299e-10 | 7.268e-10 | 1 | 1 | n/a | 2.77e-08 | 7e-09 | 6 | n/a | 2.249e-08 | n/a | n/a | 3.39 | PASS |
| `tt_m40c_3v30__case3` | tt_m40c_3v30 | 3 | ok | 156.2 | n/a | n/a | 3.3 | 7.266e-10 | 1 | n/a | n/a | 1.562e-07 | 1 | 0 | 9e-07 | n/a | 0.932 | n/a | 3.3 | PASS |
| `tt_m40c_3v30__case4` | tt_m40c_3v30 | 4 | ok | 9537 | n/a | n/a | 3.3 | 7.27e-10 | 1 | n/a | n/a | 9.537e-06 | 1 | 0 | 9e-05 | n/a | 0.7479 | n/a | 3.3 | PASS |
| `tt_m40c_3v30__case5` | tt_m40c_3v30 | 5 | ok | 62.95 | 0.1744 | n/a | 3.3 | 1.097e-09 | 1 | n/a | n/a | 6.295e-08 | 1.2e-06 | 6 | n/a | 5.859e-06 | n/a | n/a | 3.3 | PASS |
| `tt_m40c_3v60__case0` | tt_m40c_3v60 | 0 | ok | 7 | n/a | n/a | 1.084e-09 | 1.084e-09 | 1 | n/a | 1.734e-08 | 1 | 7e-09 | 6 | n/a | n/a | n/a | n/a | 0.2378 | PASS |
| `tt_m40c_3v60__case1` | tt_m40c_3v60 | 1 | ok | 4.355 | n/a | 1 | 1.9 | 4.205e-10 | 1 | n/a | n/a | 4.355e-09 | 1.1e-08 | 3 | n/a | n/a | n/a | 1.954 | 0.2251 | PASS |
| `tt_m40c_3v60__case2` | tt_m40c_3v60 | 2 | ok | 7 | n/a | n/a | 1.186e-09 | 1.084e-09 | 1 | 1 | n/a | 2.462e-08 | 7e-09 | 6 | n/a | 2.131e-08 | n/a | n/a | 3.694 | PASS |
| `tt_m40c_3v60__case3` | tt_m40c_3v60 | 3 | ok | 158.4 | n/a | n/a | 3.6 | 1.084e-09 | 1 | n/a | n/a | 1.584e-07 | 1 | 0 | 9e-07 | n/a | 0.9368 | n/a | 3.6 | PASS |
| `tt_m40c_3v60__case4` | tt_m40c_3v60 | 4 | ok | 8314 | n/a | n/a | 3.6 | 1.084e-09 | 1 | n/a | n/a | 8.314e-06 | 1 | 0 | 9e-05 | n/a | 0.7504 | n/a | 3.6 | PASS |
| `tt_m40c_3v60__case5` | tt_m40c_3v60 | 5 | timeout | n/a FAIL | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | FAIL: status=timeout; min_pulse_s missing |
| `tt_27c_3v00__case0` | tt_27c_3v00 | 0 | ok | 6 | n/a | n/a | 7.154e-10 | 7.154e-10 | 1 | n/a | 1.814e-08 | 1 | 6e-09 | 6 | n/a | n/a | n/a | n/a | 0.2112 | PASS |
| `tt_27c_3v00__case1` | tt_27c_3v00 | 1 | ok | 4.046 | n/a | 1 | 1.9 | 5.549e-10 | 1 | n/a | n/a | 4.046e-09 | 9e-09 | 3 | n/a | n/a | n/a | 1.904 | 0.2017 | PASS |
| `tt_27c_3v00__case2` | tt_27c_3v00 | 2 | ok | 6 | n/a | n/a | 8.012e-10 | 7.156e-10 | 1 | 1 | n/a | 2.754e-08 | 6e-09 | 6 | n/a | 2.377e-08 | n/a | n/a | 3.097 | PASS |
| `tt_27c_3v00__case3` | tt_27c_3v00 | 3 | timeout | n/a FAIL | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | FAIL: status=timeout; min_pulse_s missing |
| `tt_27c_3v00__case4` | tt_27c_3v00 | 4 | ok | 1.291e+04 | n/a | n/a | 3 | 7.153e-10 | 1 | n/a | n/a | 1.291e-05 | 1 | 0 | 9e-05 | n/a | 0.5947 | n/a | 3 | PASS |
| `tt_27c_3v00__case5` | tt_27c_3v00 | 5 | ok | 50.91 | 0.1232 | n/a | 3 | 1.485e-08 | 1 | n/a | n/a | 5.091e-08 | 4e-07 | 6 | n/a | 4.647e-06 | n/a | n/a | 3 | PASS |
| `tt_27c_3v30__case0` | tt_27c_3v30 | 0 | ok | 6 | n/a | n/a | 9.141e-10 | 9.141e-10 | 1 | n/a | 1.808e-08 | 1 | 6e-09 | 6 | n/a | n/a | n/a | n/a | 0.213 | PASS |
| `tt_27c_3v30__case1` | tt_27c_3v30 | 1 | ok | 4.011 | n/a | 1 | 1.9 | 5.549e-10 | 1 | n/a | n/a | 4.011e-09 | 9e-09 | 3 | n/a | n/a | n/a | 1.903 | 0.2017 | PASS |
| `tt_27c_3v30__case2` | tt_27c_3v30 | 2 | ok | 6 | n/a | n/a | 9.632e-10 | 9.143e-10 | 1 | 1 | n/a | 2.443e-08 | 6e-09 | 6 | n/a | 2.228e-08 | n/a | n/a | 3.402 | PASS |
| `tt_27c_3v30__case3` | tt_27c_3v30 | 3 | ok | 138.1 | n/a | n/a | 3.3 | 9.141e-10 | 1 | n/a | n/a | 1.381e-07 | 1 | 0 | 9e-07 | n/a | 0.844 | n/a | 3.3 | PASS |
| `tt_27c_3v30__case4` | tt_27c_3v30 | 4 | ok | 1.122e+04 | n/a | n/a | 3.3 | 9.138e-10 | 1 | n/a | n/a | 1.122e-05 | 1 | 0 | 9e-05 | n/a | 0.5992 | n/a | 3.3 | PASS |
| `tt_27c_3v30__case5` | tt_27c_3v30 | 5 | ok | 48.42 | 0.1246 | n/a | 3.3 | 1.237e-08 | 1 | n/a | n/a | 4.842e-08 | 4e-07 | 6 | n/a | 5.868e-06 | n/a | n/a | 3.3 | PASS |
| `tt_27c_3v60__case0` | tt_27c_3v60 | 0 | ok | 6 | n/a | n/a | 1.343e-09 | 1.343e-09 | 1 | n/a | 1.832e-08 | 1 | 6e-09 | 6 | n/a | n/a | n/a | n/a | 0.2139 | PASS |
| `tt_27c_3v60__case1` | tt_27c_3v60 | 1 | ok | 4.006 | n/a | 1 | 1.9 | 5.549e-10 | 1 | n/a | n/a | 4.006e-09 | 9e-09 | 3 | n/a | n/a | n/a | 1.903 | 0.2017 | PASS |
| `tt_27c_3v60__case2` | tt_27c_3v60 | 2 | ok | 6 | n/a | n/a | 1.34e-09 | 1.344e-09 | 1 | 1 | n/a | 2.127e-08 | 6e-09 | 6 | n/a | 2.126e-08 | n/a | n/a | 3.708 | PASS |
| `tt_27c_3v60__case3` | tt_27c_3v60 | 3 | ok | 139.9 | n/a | n/a | 3.6 | 1.344e-09 | 1 | n/a | n/a | 1.399e-07 | 1 | 0 | 9e-07 | n/a | 0.8496 | n/a | 3.6 | PASS |
| `tt_27c_3v60__case4` | tt_27c_3v60 | 4 | ok | 9868 | n/a | n/a | 3.6 | 1.344e-09 | 1 | n/a | n/a | 9.868e-06 | 1 | 0 | 9e-05 | n/a | 0.6034 | n/a | 3.6 | PASS |
| `tt_27c_3v60__case5` | tt_27c_3v60 | 5 | timeout | n/a FAIL | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | FAIL: status=timeout; min_pulse_s missing |
| `tt_125c_3v00__case0` | tt_125c_3v00 | 0 | ok | 4 | n/a | n/a | 3.988e-08 | 3.988e-08 | 1 | n/a | 2.413e-08 | 1 | 4e-09 | 6 | n/a | n/a | n/a | n/a | 0.1653 | PASS |
| `tt_125c_3v00__case1` | tt_125c_3v00 | 1 | ok | 6 | n/a | 1 | 1.9 | 3.907e-08 | 1 | n/a | n/a | 7.127e-09 | 6e-09 | 3 | n/a | n/a | n/a | 1.92 | 0.1558 | PASS |
| `tt_125c_3v00__case2` | tt_125c_3v00 | 2 | ok | 4 | n/a | n/a | 3.897e-08 | 3.988e-08 | 1 | 1 | n/a | 2.249e-08 | 4e-09 | 6 | n/a | 2.426e-08 | n/a | n/a | 3.11 | PASS |
| `tt_125c_3v00__case3` | tt_125c_3v00 | 3 | ok | 115.8 | n/a | n/a | 3 | 3.988e-08 | 1 | n/a | n/a | 1.158e-07 | 1 | 0 | 9e-07 | n/a | 0.6776 | n/a | 3 | PASS |
| `tt_125c_3v00__case4` | tt_125c_3v00 | 4 | ok | 1.028e+04 | n/a | n/a | 3 | 3.988e-08 | 1 | n/a | n/a | 1.028e-05 | 1 | 0 | 9e-05 | n/a | 0.5001 | n/a | 3 | PASS |
| `tt_125c_3v00__case5` | tt_125c_3v00 | 5 | ok | 39.57 | 0.05212 | n/a | 3 | 5.178e-08 | 1 | n/a | n/a | 3.957e-08 | 1 | 0 | n/a | 4.659e-06 | n/a | n/a | 3 | PASS |
| `tt_125c_3v30__case0` | tt_125c_3v30 | 0 | ok | 4 | n/a | n/a | 4.195e-08 | 4.195e-08 | 1 | n/a | 2.469e-08 | 1 | 4e-09 | 6 | n/a | n/a | n/a | n/a | 0.1673 | PASS |
| `tt_125c_3v30__case1` | tt_125c_3v30 | 1 | ok | 6 | n/a | 1 | 1.9 | 3.907e-08 | 1 | n/a | n/a | 7.955e-09 | 6e-09 | 3 | n/a | n/a | n/a | 1.903 | 0.1561 | PASS |
| `tt_125c_3v30__case2` | tt_125c_3v30 | 2 | ok | 4 | n/a | n/a | 4.197e-08 | 4.195e-08 | 1 | 1 | n/a | 1.961e-08 | 4e-09 | 6 | n/a | 2.26e-08 | n/a | n/a | 3.414 | PASS |
| `tt_125c_3v30__case3` | tt_125c_3v30 | 3 | ok | 118.5 | n/a | n/a | 3.3 | 4.196e-08 | 1 | n/a | n/a | 1.185e-07 | 1 | 0 | 9e-07 | n/a | 0.6853 | n/a | 3.3 | PASS |
| `tt_125c_3v30__case4` | tt_125c_3v30 | 4 | ok | 9300 | n/a | n/a | 3.3 | 4.195e-08 | 1 | n/a | n/a | 9.3e-06 | 1 | 0 | 9e-05 | n/a | 0.5001 | n/a | 3.3 | PASS |
| `tt_125c_3v30__case5` | tt_125c_3v30 | 5 | ok | 39.95 | 0.05335 | n/a | 3.3 | 5.384e-08 | 1 | n/a | n/a | 3.995e-08 | 1 | 0 | n/a | 5.886e-06 | n/a | n/a | 3.3 | PASS |
| `tt_125c_3v60__case0` | tt_125c_3v60 | 0 | ok | 5 | n/a | n/a | 4.502e-08 | 4.502e-08 | 1 | n/a | 2.539e-08 | 1 | 5e-09 | 6 | n/a | n/a | n/a | n/a | 0.1696 | PASS |
| `tt_125c_3v60__case1` | tt_125c_3v60 | 1 | ok | 6 | n/a | 1 | 1.9 | 3.907e-08 | 1 | n/a | n/a | 7.953e-09 | 6e-09 | 3 | n/a | n/a | n/a | 1.903 | 0.1559 | PASS |
| `tt_125c_3v60__case2` | tt_125c_3v60 | 2 | ok | 5 | n/a | n/a | 4.494e-08 | 4.502e-08 | 1 | 1 | n/a | 1.692e-08 | 5e-09 | 6 | n/a | 2.123e-08 | n/a | n/a | 3.694 | PASS |
| `tt_125c_3v60__case3` | tt_125c_3v60 | 3 | ok | 119.7 | n/a | n/a | 3.6 | 4.502e-08 | 1 | n/a | n/a | 1.197e-07 | 1 | 0 | 9e-07 | n/a | 0.6924 | n/a | 3.6 | PASS |
| `tt_125c_3v60__case4` | tt_125c_3v60 | 4 | ok | 8456 | n/a | n/a | 3.6 | 4.502e-08 | 1 | n/a | n/a | 8.456e-06 | 1 | 0 | 9e-05 | n/a | 0.5001 | n/a | 3.6 | PASS |
| `tt_125c_3v60__case5` | tt_125c_3v60 | 5 | ok | 40.64 | 0.0545 | n/a | 3.6 | 4.826e-08 | 1 | n/a | n/a | 4.064e-08 | 1 | 0 | n/a | 6.891e-06 | n/a | n/a | 3.6 | PASS |
| `ff_m40c_3v00__case0` | ff_m40c_3v00 | 0 | timeout | n/a FAIL | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | FAIL: status=timeout; min_pulse_s missing |
| `ff_m40c_3v00__case1` | ff_m40c_3v00 | 1 | ok | 3.01 | n/a | 1 | 1.9 | 3.738e-10 | 1 | n/a | n/a | 3.01e-09 | 7e-09 | 3 | n/a | n/a | n/a | 1.943 | 0.1887 | PASS |
| `ff_m40c_3v00__case2` | ff_m40c_3v00 | 2 | ok | 5 | n/a | n/a | 5.029e-10 | 5.7e-10 | 1 | 1 | n/a | 2.049e-08 | 5e-09 | 6 | n/a | 1.877e-08 | n/a | n/a | 3.077 | PASS |
| `ff_m40c_3v00__case3` | ff_m40c_3v00 | 3 | ok | 129.5 | n/a | n/a | 3 | 5.702e-10 | 1 | n/a | n/a | 1.295e-07 | 1 | 0 | 9e-07 | n/a | 0.7932 | n/a | 3 | PASS |
| `ff_m40c_3v00__case4` | ff_m40c_3v00 | 4 | ok | 1.101e+04 | n/a | n/a | 3 | 5.695e-10 | 1 | n/a | n/a | 1.101e-05 | 1 | 0 | 9e-05 | n/a | 0.6085 | n/a | 3 | PASS |
| `ff_m40c_3v00__case5` | ff_m40c_3v00 | 5 | ok | 38.01 | 0.1326 | n/a | 3 | -1.674e-08 | 1 | n/a | n/a | 3.801e-08 | 4.2e-07 | 6 | n/a | 4.653e-06 | n/a | n/a | 3.002 | PASS |
| `ff_m40c_3v30__case0` | ff_m40c_3v30 | 0 | ok | 5 | n/a | n/a | 8.195e-10 | 8.195e-10 | 1 | n/a | 1.151e-08 | 1 | 5e-09 | 6 | n/a | n/a | n/a | n/a | 0.1961 | PASS |
| `ff_m40c_3v30__case1` | ff_m40c_3v30 | 1 | ok | 3.008 | n/a | 1 | 1.9 | 3.738e-10 | 1 | n/a | n/a | 3.008e-09 | 7e-09 | 3 | n/a | n/a | n/a | 1.946 | 0.1887 | PASS |
| `ff_m40c_3v30__case2` | ff_m40c_3v30 | 2 | ok | 5 | n/a | n/a | 7.408e-10 | 8.2e-10 | 1 | 1 | n/a | 1.769e-08 | 5e-09 | 6 | n/a | 1.698e-08 | n/a | n/a | 3.361 | PASS |
| `ff_m40c_3v30__case3` | ff_m40c_3v30 | 3 | timeout | n/a FAIL | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | FAIL: status=timeout; min_pulse_s missing |
| `ff_m40c_3v30__case4` | ff_m40c_3v30 | 4 | ok | 9514 | n/a | n/a | 3.3 | 8.194e-10 | 1 | n/a | n/a | 9.514e-06 | 1 | 0 | 9e-05 | n/a | 0.6117 | n/a | 3.3 | PASS |
| `ff_m40c_3v30__case5` | ff_m40c_3v30 | 5 | ok | 37.06 | 0.1335 | n/a | 3.3 | -1.383e-08 | 1 | n/a | n/a | 3.706e-08 | 4.2e-07 | 6 | n/a | 5.861e-06 | n/a | n/a | 3.3 | PASS |
| `ff_m40c_3v60__case0` | ff_m40c_3v60 | 0 | ok | 5 | n/a | n/a | 1.359e-09 | 1.359e-09 | 1 | n/a | 1.151e-08 | 1 | 5e-09 | 6 | n/a | n/a | n/a | n/a | 0.1966 | PASS |
| `ff_m40c_3v60__case1` | ff_m40c_3v60 | 1 | ok | 3.994 | n/a | 1 | 1.9 | 3.738e-10 | 1 | n/a | n/a | 3.994e-09 | 7e-09 | 3 | n/a | n/a | n/a | 1.901 | 0.1887 | PASS |
| `ff_m40c_3v60__case2` | ff_m40c_3v60 | 2 | ok | 5 | n/a | n/a | 1.526e-09 | 1.359e-09 | 1 | 1 | n/a | 1.628e-08 | 5e-09 | 6 | n/a | 1.641e-08 | n/a | n/a | 3.685 | PASS |
| `ff_m40c_3v60__case3` | ff_m40c_3v60 | 3 | ok | 134 | n/a | n/a | 3.6 | 1.359e-09 | 1 | n/a | n/a | 1.34e-07 | 1 | 0 | 9e-07 | n/a | 0.8021 | n/a | 3.6 | PASS |
| `ff_m40c_3v60__case4` | ff_m40c_3v60 | 4 | ok | 8334 | n/a | n/a | 3.6 | 1.359e-09 | 1 | n/a | n/a | 8.334e-06 | 1 | 0 | 9e-05 | n/a | 0.6146 | n/a | 3.6 | PASS |
| `ff_m40c_3v60__case5` | ff_m40c_3v60 | 5 | ok | 37.76 | 0.1345 | n/a | 3.6 | 1.631e-08 | 1 | n/a | n/a | 3.776e-08 | 3.8e-07 | 6 | n/a | 6.892e-06 | n/a | n/a | 3.603 | PASS |
| `ff_27c_3v00__case0` | ff_27c_3v00 | 0 | ok | 4 | n/a | n/a | 1.268e-09 | 1.268e-09 | 1 | n/a | 1.428e-08 | 1 | 4e-09 | 6 | n/a | n/a | n/a | n/a | 0.1649 | PASS |
| `ff_27c_3v00__case1` | ff_27c_3v00 | 1 | ok | 3.995 | n/a | 1 | 1.9 | 9.284e-10 | 1 | n/a | n/a | 3.995e-09 | 5e-09 | 3 | n/a | n/a | n/a | 1.901 | 0.1614 | PASS |
| `ff_27c_3v00__case2` | ff_27c_3v00 | 2 | ok | 4 | n/a | n/a | 1.375e-09 | 1.268e-09 | 1 | 1 | n/a | 1.778e-08 | 4e-09 | 6 | n/a | 1.859e-08 | n/a | n/a | 3.089 | PASS |
| `ff_27c_3v00__case3` | ff_27c_3v00 | 3 | ok | 115.3 | n/a | n/a | 3 | 1.268e-09 | 1 | n/a | n/a | 1.153e-07 | 1 | 0 | 9e-07 | n/a | 0.6938 | n/a | 3 | PASS |
| `ff_27c_3v00__case4` | ff_27c_3v00 | 4 | ok | 1.104e+04 | n/a | n/a | 3 | 1.268e-09 | 1 | n/a | n/a | 1.104e-05 | 1 | 0 | 9e-05 | n/a | 0.5001 | n/a | 3 | PASS |
| `ff_27c_3v00__case5` | ff_27c_3v00 | 5 | ok | 30.85 | 0.07901 | n/a | 3 | -1.802e-08 | 1 | n/a | n/a | 3.085e-08 | 1 | 0 | n/a | 4.649e-06 | n/a | n/a | 3 | PASS |
| `ff_27c_3v30__case0` | ff_27c_3v30 | 0 | ok | 4 | n/a | n/a | 1.625e-09 | 1.625e-09 | 1 | n/a | 1.425e-08 | 1 | 4e-09 | 6 | n/a | n/a | n/a | n/a | 0.1657 | PASS |
| `ff_27c_3v30__case1` | ff_27c_3v30 | 1 | ok | 3.995 | n/a | 1 | 1.9 | 9.284e-10 | 1 | n/a | n/a | 3.995e-09 | 5e-09 | 3 | n/a | n/a | n/a | 1.901 | 0.1614 | PASS |
| `ff_27c_3v30__case2` | ff_27c_3v30 | 2 | ok | 4 | n/a | n/a | 1.627e-09 | 1.624e-09 | 1 | 1 | n/a | 1.463e-08 | 4e-09 | 6 | n/a | 1.765e-08 | n/a | n/a | 3.368 | PASS |
| `ff_27c_3v30__case3` | ff_27c_3v30 | 3 | ok | 120.4 | n/a | n/a | 3.3 | 1.625e-09 | 1 | n/a | n/a | 1.204e-07 | 1 | 0 | 9e-07 | n/a | 0.6995 | n/a | 3.3 | PASS |
| `ff_27c_3v30__case4` | ff_27c_3v30 | 4 | ok | 9820 | n/a | n/a | 3.3 | 1.624e-09 | 1 | n/a | n/a | 9.82e-06 | 1 | 0 | 9e-05 | n/a | 0.5001 | n/a | 3.3 | PASS |
| `ff_27c_3v30__case5` | ff_27c_3v30 | 5 | ok | 32.29 | 0.08034 | n/a | 3.3 | 1.209e-08 | 1 | n/a | n/a | 3.229e-08 | 1 | 0 | n/a | 5.879e-06 | n/a | n/a | 3.302 | PASS |
| `ff_27c_3v60__case0` | ff_27c_3v60 | 0 | ok | 4 | n/a | n/a | 2.34e-09 | 2.34e-09 | 1 | n/a | 1.428e-08 | 1 | 4e-09 | 6 | n/a | n/a | n/a | n/a | 0.1693 | PASS |
| `ff_27c_3v60__case1` | ff_27c_3v60 | 1 | ok | 3.995 | n/a | 1 | 1.9 | 9.284e-10 | 1 | n/a | n/a | 3.995e-09 | 5e-09 | 3 | n/a | n/a | n/a | 1.901 | 0.1614 | PASS |
| `ff_27c_3v60__case2` | ff_27c_3v60 | 2 | ok | 4 | n/a | n/a | 2.422e-09 | 2.34e-09 | 1 | 1 | n/a | 1.327e-08 | 4e-09 | 6 | n/a | 1.679e-08 | n/a | n/a | 3.699 | PASS |
| `ff_27c_3v60__case3` | ff_27c_3v60 | 3 | ok | 122.5 | n/a | n/a | 3.6 | 2.34e-09 | 1 | n/a | n/a | 1.225e-07 | 1 | 0 | 9e-07 | n/a | 0.7048 | n/a | 3.6 | PASS |
| `ff_27c_3v60__case4` | ff_27c_3v60 | 4 | timeout | n/a FAIL | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | FAIL: status=timeout; min_pulse_s missing |
| `ff_27c_3v60__case5` | ff_27c_3v60 | 5 | ok | 31.21 | 0.08155 | n/a | 3.6 | 1.267e-08 | 1 | n/a | n/a | 3.121e-08 | 1 | 0 | n/a | 6.888e-06 | n/a | n/a | 3.602 | PASS |
| `ff_125c_3v00__case0` | ff_125c_3v00 | 0 | ok | 2 FAIL | n/a | n/a | 4.257e-07 | 4.257e-07 | 1 | n/a | 4.868e-08 | 1 | 2e-09 | 6 | n/a | n/a | n/a | n/a | 0.1203 | FAIL: min_pulse_s=2e-09 outside [2e-09, inf] |
| `ff_125c_3v00__case1` | ff_125c_3v00 | 1 | ok | 2 FAIL | n/a | 1 | 1.9 | 3.916e-07 | 1 | n/a | n/a | 7.009e-09 | 2e-09 | 3 | n/a | n/a | n/a | 1.901 | 0.1111 | FAIL: min_pulse_s=2e-09 outside [2e-09, inf] |
| `ff_125c_3v00__case2` | ff_125c_3v00 | 2 | ok | 2 FAIL | n/a | n/a | 4.257e-07 | 4.257e-07 | 1 | 1 | n/a | 1.381e-08 | 2e-09 | 6 | n/a | 1.925e-08 | n/a | n/a | 3.102 | FAIL: min_pulse_s=2e-09 outside [2e-09, inf] |
| `ff_125c_3v00__case3` | ff_125c_3v00 | 3 | ok | 107.3 | n/a | n/a | 3 | 4.257e-07 | 1 | n/a | n/a | 1.073e-07 | 1 | 0 | 9e-07 | n/a | 0.5224 | n/a | 3 | PASS |
| `ff_125c_3v00__case4` | ff_125c_3v00 | 4 | ok | 5320 | n/a | n/a | 3 | 4.257e-07 | 1 | n/a | n/a | 5.32e-06 | 1 | 0 | 9e-05 | n/a | 0.5 | n/a | 3 | PASS |
| `ff_125c_3v00__case5` | ff_125c_3v00 | 5 | ok | 19.77 | 0.03563 | n/a | 3 | 4.378e-07 | 1 | n/a | n/a | 1.977e-08 | 1 | 0 | n/a | 4.674e-06 | n/a | n/a | 3 | PASS |
| `ff_125c_3v30__case0` | ff_125c_3v30 | 0 | ok | 2 FAIL | n/a | n/a | 4.522e-07 | 4.522e-07 | 1 | n/a | 5.372e-08 | 1 | 2e-09 | 6 | n/a | n/a | n/a | n/a | 0.1219 | FAIL: min_pulse_s=2e-09 outside [2e-09, inf] |
| `ff_125c_3v30__case1` | ff_125c_3v30 | 1 | ok | 2 FAIL | n/a | 1 | 1.9 | 3.916e-07 | 1 | n/a | n/a | 7.02e-09 | 2e-09 | 3 | n/a | n/a | n/a | 1.901 | 0.1111 | FAIL: min_pulse_s=2e-09 outside [2e-09, inf] |
| `ff_125c_3v30__case2` | ff_125c_3v30 | 2 | ok | 2 FAIL | n/a | n/a | 4.522e-07 | 4.522e-07 | 1 | 1 | n/a | 1.175e-08 | 2e-09 | 6 | n/a | 1.794e-08 | n/a | n/a | 3.383 | FAIL: min_pulse_s=2e-09 outside [2e-09, inf] |
| `ff_125c_3v30__case3` | ff_125c_3v30 | 3 | ok | 107.8 | n/a | n/a | 3.3 | 4.522e-07 | 1 | n/a | n/a | 1.078e-07 | 1 | 0 | 9e-07 | n/a | 0.5297 | n/a | 3.3 | PASS |
| `ff_125c_3v30__case4` | ff_125c_3v30 | 4 | ok | 4940 | n/a | n/a | 3.3 | 4.522e-07 | 1 | n/a | n/a | 4.94e-06 | 1 | 0 | 9e-05 | n/a | 0.5 | n/a | 3.3 | PASS |
| `ff_125c_3v30__case5` | ff_125c_3v30 | 5 | ok | 20.55 | 0.03628 | n/a | 3.3 | 4.615e-07 | 1 | n/a | n/a | 2.055e-08 | 1 | 0 | n/a | 5.886e-06 | n/a | n/a | 3.3 | PASS |
| `ff_125c_3v60__case0` | ff_125c_3v60 | 0 | ok | 2 | n/a | n/a | 4.877e-07 | 4.877e-07 | 1 | n/a | 6.042e-08 | 1 | 2e-09 | 6 | n/a | n/a | n/a | n/a | 0.1231 | PASS |
| `ff_125c_3v60__case1` | ff_125c_3v60 | 1 | ok | 2 FAIL | n/a | 1 | 1.9 | 3.916e-07 | 1 | n/a | n/a | 7.994e-09 | 2e-09 | 3 | n/a | n/a | n/a | 1.905 | 0.1111 | FAIL: min_pulse_s=2e-09 outside [2e-09, inf] |
| `ff_125c_3v60__case2` | ff_125c_3v60 | 2 | ok | 2 | n/a | n/a | 4.877e-07 | 4.877e-07 | 1 | 1 | n/a | 9.903e-09 | 2e-09 | 6 | n/a | 1.735e-08 | n/a | n/a | 3.686 | PASS |
| `ff_125c_3v60__case3` | ff_125c_3v60 | 3 | timeout | n/a FAIL | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | FAIL: status=timeout; min_pulse_s missing |
| `ff_125c_3v60__case4` | ff_125c_3v60 | 4 | ok | 4580 | n/a | n/a | 3.6 | 4.877e-07 | 1 | n/a | n/a | 4.58e-06 | 1 | 0 | 9e-05 | n/a | 0.5 | n/a | 3.6 | PASS |
| `ff_125c_3v60__case5` | ff_125c_3v60 | 5 | ok | 21.42 | 0.03686 | n/a | 3.6 | 4.956e-07 | 1 | n/a | n/a | 2.142e-08 | 1 | 0 | n/a | 6.884e-06 | n/a | n/a | 3.6 | PASS |
| `ss_m40c_3v00__case0` | ss_m40c_3v00 | 0 | ok | 10 | n/a | n/a | 5.759e-10 | 5.759e-10 | 1 | n/a | 3.559e-08 | 1 | 1e-08 | 6 | n/a | n/a | n/a | n/a | 0.265 | PASS |
| `ss_m40c_3v00__case1` | ss_m40c_3v00 | 1 | ok | 3.999 | n/a | 1 | 1.9 | 4.792e-10 | 1 | n/a | n/a | 3.999e-09 | 1.5e-08 | 3 | n/a | n/a | n/a | 1.922 | 0.2641 | PASS |
| `ss_m40c_3v00__case2` | ss_m40c_3v00 | 2 | ok | 10 | n/a | n/a | 5.685e-10 | 5.767e-10 | 1 | 1 | n/a | 4.778e-08 | 1e-08 | 6 | n/a | 3.022e-08 | n/a | n/a | 3.092 | PASS |
| `ss_m40c_3v00__case3` | ss_m40c_3v00 | 3 | ok | 174.1 | n/a | n/a | 3 | 5.766e-10 | 1 | n/a | n/a | 1.741e-07 | 1 | 0 | 9e-07 | n/a | 1.06 | n/a | 3 | PASS |
| `ss_m40c_3v00__case4` | ss_m40c_3v00 | 4 | ok | 1.099e+04 | n/a | n/a | 3 | 5.772e-10 | 1 | n/a | n/a | 1.099e-05 | 1 | 0 | 9e-05 | n/a | 0.8797 | n/a | 3 | PASS |
| `ss_m40c_3v00__case5` | ss_m40c_3v00 | 5 | timeout | n/a FAIL | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | FAIL: status=timeout; min_pulse_s missing |
| `ss_m40c_3v30__case0` | ss_m40c_3v30 | 0 | ok | 9 | n/a | n/a | 6.885e-10 | 6.885e-10 | 1 | n/a | 4.892e-08 | 1 | 9e-09 | 6 | n/a | n/a | n/a | n/a | 0.2715 | PASS |
| `ss_m40c_3v30__case1` | ss_m40c_3v30 | 1 | ok | 5.026 | n/a | 1 | 1.9 | 4.792e-10 | 1 | n/a | n/a | 5.026e-09 | 1.5e-08 | 3 | n/a | n/a | n/a | 2.003 | 0.2641 | PASS |
| `ss_m40c_3v30__case2` | ss_m40c_3v30 | 2 | ok | 9 | n/a | n/a | 7.272e-10 | 6.892e-10 | 1 | 1 | n/a | 4.133e-08 | 9e-09 | 6 | n/a | 2.838e-08 | n/a | n/a | 3.398 | PASS |
| `ss_m40c_3v30__case3` | ss_m40c_3v30 | 3 | ok | 180.5 | n/a | n/a | 3.3 | 6.892e-10 | 1 | n/a | n/a | 1.805e-07 | 1 | 0 | 9e-07 | n/a | 1.066 | n/a | 3.3 | PASS |
| `ss_m40c_3v30__case4` | ss_m40c_3v30 | 4 | ok | 9543 | n/a | n/a | 3.3 | 6.896e-10 | 1 | n/a | n/a | 9.543e-06 | 1 | 0 | 9e-05 | n/a | 0.8819 | n/a | 3.3 | PASS |
| `ss_m40c_3v30__case5` | ss_m40c_3v30 | 5 | timeout | n/a FAIL | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | FAIL: status=timeout; min_pulse_s missing |
| `ss_m40c_3v60__case0` | ss_m40c_3v60 | 0 | ok | 9 | n/a | n/a | 9.3e-10 | 9.3e-10 | 1 | n/a | 4.31e-08 | 1 | 9e-09 | 6 | n/a | n/a | n/a | n/a | 0.2797 | PASS |
| `ss_m40c_3v60__case1` | ss_m40c_3v60 | 1 | ok | 6.003 | n/a | 1 | 1.9 | 4.792e-10 | 1 | n/a | n/a | 6.003e-09 | 1.5e-08 | 3 | n/a | n/a | n/a | 1.925 | 0.2641 | PASS |
| `ss_m40c_3v60__case2` | ss_m40c_3v60 | 2 | ok | 9 | n/a | n/a | 9.483e-10 | 9.303e-10 | 1 | 1 | n/a | 3.629e-08 | 9e-09 | 6 | n/a | 2.666e-08 | n/a | n/a | 3.702 | PASS |
| `ss_m40c_3v60__case3` | ss_m40c_3v60 | 3 | ok | 184.2 | n/a | n/a | 3.6 | 9.304e-10 | 1 | n/a | n/a | 1.842e-07 | 1 | 0 | 9e-07 | n/a | 1.07 | n/a | 3.6 | PASS |
| `ss_m40c_3v60__case4` | ss_m40c_3v60 | 4 | ok | 8350 | n/a | n/a | 3.6 | 9.306e-10 | 1 | n/a | n/a | 8.35e-06 | 1 | 0 | 9e-05 | n/a | 0.8841 | n/a | 3.6 | PASS |
| `ss_m40c_3v60__case5` | ss_m40c_3v60 | 5 | ok | 97.41 | 0.2156 | n/a | 3.6 | 8.372e-09 | 1 | n/a | n/a | 9.741e-08 | 1.8e-06 | 6 | n/a | 6.896e-06 | n/a | n/a | 3.6 | PASS |
| `ss_27c_3v00__case0` | ss_27c_3v00 | 0 | ok | 9 | n/a | n/a | 7.181e-10 | 7.181e-10 | 1 | n/a | 5.188e-08 | 1 | 9e-09 | 6 | n/a | n/a | n/a | n/a | 0.2502 | PASS |
| `ss_27c_3v00__case1` | ss_27c_3v00 | 1 | ok | 5.892 | n/a | 1 | 1.9 | 6.133e-10 | 1 | n/a | n/a | 5.892e-09 | 1.3e-08 | 3 | n/a | n/a | n/a | 1.923 | 0.2465 | PASS |
| `ss_27c_3v00__case2` | ss_27c_3v00 | 2 | ok | 9 | n/a | n/a | -3.646e-09 | 7.179e-10 | 1 | 1 | n/a | 4.148e-08 | 9e-09 | 6 | n/a | 2.974e-08 | n/a | n/a | 3.104 | PASS |
| `ss_27c_3v00__case3` | ss_27c_3v00 | 3 | ok | 152.7 | n/a | n/a | 3 | 7.179e-10 | 1 | n/a | n/a | 1.527e-07 | 1 | 0 | 9e-07 | n/a | 0.9773 | n/a | 3 | PASS |
| `ss_27c_3v00__case4` | ss_27c_3v00 | 4 | ok | 1.291e+04 | n/a | n/a | 3 | 7.177e-10 | 1 | n/a | n/a | 1.291e-05 | 1 | 0 | 9e-05 | n/a | 0.7377 | n/a | 3 | PASS |
| `ss_27c_3v00__case5` | ss_27c_3v00 | 5 | ok | 85.88 | 0.168 | n/a | 3 | 1.219e-09 | 1 | n/a | n/a | 8.588e-08 | 1.26e-06 | 6 | n/a | 4.663e-06 | n/a | n/a | 3.002 | PASS |
| `ss_27c_3v30__case0` | ss_27c_3v30 | 0 | ok | 8 | n/a | n/a | 8.518e-10 | 8.518e-10 | 1 | n/a | 3.39e-08 | 1 | 8e-09 | 6 | n/a | n/a | n/a | n/a | 0.2564 | PASS |
| `ss_27c_3v30__case1` | ss_27c_3v30 | 1 | ok | 5.893 | n/a | 1 | 1.9 | 6.133e-10 | 1 | n/a | n/a | 5.893e-09 | 1.3e-08 | 3 | n/a | n/a | n/a | 1.922 | 0.2465 | PASS |
| `ss_27c_3v30__case2` | ss_27c_3v30 | 2 | ok | 8 | n/a | n/a | 1.068e-09 | 8.518e-10 | 1 | 1 | n/a | 3.543e-08 | 8e-09 | 6 | n/a | 2.815e-08 | n/a | n/a | 3.41 | PASS |
| `ss_27c_3v30__case3` | ss_27c_3v30 | 3 | ok | 158.9 | n/a | n/a | 3.3 | 8.515e-10 | 1 | n/a | n/a | 1.589e-07 | 1 | 0 | 9e-07 | n/a | 0.9835 | n/a | 3.3 | PASS |
| `ss_27c_3v30__case4` | ss_27c_3v30 | 4 | timeout | n/a FAIL | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | FAIL: status=timeout; min_pulse_s missing |
| `ss_27c_3v30__case5` | ss_27c_3v30 | 5 | ok | 84.87 | 0.1696 | n/a | 3.3 | -7.861e-09 | 1 | n/a | n/a | 8.487e-08 | 1.2e-06 | 6 | n/a | 5.869e-06 | n/a | n/a | 3.3 | PASS |
| `ss_27c_3v60__case0` | ss_27c_3v60 | 0 | ok | 8 | n/a | n/a | 1.141e-09 | 1.141e-09 | 1 | n/a | 3.563e-08 | 1 | 8e-09 | 6 | n/a | n/a | n/a | n/a | 0.2585 | PASS |
| `ss_27c_3v60__case1` | ss_27c_3v60 | 1 | ok | 6.929 | n/a | 1 | 1.9 | 6.133e-10 | 1 | n/a | n/a | 6.929e-09 | 1.3e-08 | 3 | n/a | n/a | n/a | 2.014 | 0.2465 | PASS |
| `ss_27c_3v60__case2` | ss_27c_3v60 | 2 | ok | 8 | n/a | n/a | 1.53e-09 | 1.141e-09 | 1 | 1 | n/a | 3.103e-08 | 8e-09 | 6 | n/a | 2.601e-08 | n/a | n/a | 3.689 | PASS |
| `ss_27c_3v60__case3` | ss_27c_3v60 | 3 | ok | 161.9 | n/a | n/a | 3.6 | 1.141e-09 | 1 | n/a | n/a | 1.619e-07 | 1 | 0 | 9e-07 | n/a | 0.9887 | n/a | 3.6 | PASS |
| `ss_27c_3v60__case4` | ss_27c_3v60 | 4 | timeout | n/a FAIL | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | FAIL: status=timeout; min_pulse_s missing |
| `ss_27c_3v60__case5` | ss_27c_3v60 | 5 | ok | 82.48 | 0.171 | n/a | 3.6 | -6.989e-09 | 1 | n/a | n/a | 8.248e-08 | 1.1e-06 | 6 | n/a | 6.885e-06 | n/a | n/a | 3.601 | PASS |
| `ss_125c_3v00__case0` | ss_125c_3v00 | 0 | ok | 7 | n/a | n/a | 4.904e-09 | 4.904e-09 | 1 | n/a | 3.11e-08 | 1 | 7e-09 | 6 | n/a | n/a | n/a | n/a | 0.2117 | PASS |
| `ss_125c_3v00__case1` | ss_125c_3v00 | 1 | ok | 7.577 | n/a | 1 | 1.9 | 5.013e-09 | 1 | n/a | n/a | 7.577e-09 | 1e-08 | 3 | n/a | n/a | n/a | 1.993 | 0.2043 | PASS |
| `ss_125c_3v00__case2` | ss_125c_3v00 | 2 | ok | 7 | n/a | n/a | -8.037e-09 | 4.904e-09 | 1 | 1 | n/a | 3.314e-08 | 7e-09 | 6 | n/a | 2.958e-08 | n/a | n/a | 3.088 | PASS |
| `ss_125c_3v00__case3` | ss_125c_3v00 | 3 | ok | 128.8 | n/a | n/a | 3 | 4.904e-09 | 1 | n/a | n/a | 1.288e-07 | 1 | 0 | 9e-07 | n/a | 0.8321 | n/a | 3 | PASS |
| `ss_125c_3v00__case4` | ss_125c_3v00 | 4 | ok | 1.53e+04 | n/a | n/a | 3 | 4.904e-09 | 1 | n/a | n/a | 1.53e-05 | 1 | 0 | 9e-05 | n/a | 0.501 | n/a | 3 | PASS |
| `ss_125c_3v00__case5` | ss_125c_3v00 | 5 | ok | 64.13 | 0.08544 | n/a | 3 | 1.74e-08 | 1 | n/a | n/a | 6.413e-08 | 1 | 0 | n/a | 4.659e-06 | n/a | n/a | 3 | PASS |
| `ss_125c_3v30__case0` | ss_125c_3v30 | 0 | ok | 7 | n/a | n/a | 5.197e-09 | 5.197e-09 | 1 | n/a | 3.228e-08 | 1 | 7e-09 | 6 | n/a | n/a | n/a | n/a | 0.2145 | PASS |
| `ss_125c_3v30__case1` | ss_125c_3v30 | 1 | ok | 7.59 | n/a | 1 | 1.9 | 5.013e-09 | 1 | n/a | n/a | 7.59e-09 | 1e-08 | 3 | n/a | n/a | n/a | 1.985 | 0.2045 | PASS |
| `ss_125c_3v30__case2` | ss_125c_3v30 | 2 | ok | 7 | n/a | n/a | 1.741e-08 | 5.197e-09 | 1 | 1 | n/a | 2.972e-08 | 7e-09 | 6 | n/a | 2.812e-08 | n/a | n/a | 3.424 | PASS |
| `ss_125c_3v30__case3` | ss_125c_3v30 | 3 | ok | 132.9 | n/a | n/a | 3.3 | 5.197e-09 | 1 | n/a | n/a | 1.329e-07 | 1 | 0 | 9e-07 | n/a | 0.8398 | n/a | 3.3 | PASS |
| `ss_125c_3v30__case4` | ss_125c_3v30 | 4 | ok | 1.37e+04 | n/a | n/a | 3.3 | 5.196e-09 | 1 | n/a | n/a | 1.37e-05 | 1 | 0 | 9e-05 | n/a | 0.5044 | n/a | 3.3 | PASS |
| `ss_125c_3v30__case5` | ss_125c_3v30 | 5 | timeout | n/a FAIL | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | FAIL: status=timeout; min_pulse_s missing |
| `ss_125c_3v60__case0` | ss_125c_3v60 | 0 | ok | 7 | n/a | n/a | 5.752e-09 | 5.752e-09 | 1 | n/a | 3.365e-08 | 1 | 7e-09 | 6 | n/a | n/a | n/a | n/a | 0.2164 | PASS |
| `ss_125c_3v60__case1` | ss_125c_3v60 | 1 | ok | 8.465 | n/a | 1 | 1.9 | 5.013e-09 | 1 | n/a | n/a | 8.465e-09 | 1e-08 | 3 | n/a | n/a | n/a | 1.978 | 0.2043 | PASS |
| `ss_125c_3v60__case2` | ss_125c_3v60 | 2 | ok | 7 | n/a | n/a | 1.222e-08 | 5.752e-09 | 1 | 1 | n/a | 2.611e-08 | 7e-09 | 6 | n/a | 2.684e-08 | n/a | n/a | 3.723 | PASS |
| `ss_125c_3v60__case3` | ss_125c_3v60 | 3 | ok | 135.6 | n/a | n/a | 3.6 | 5.752e-09 | 1 | n/a | n/a | 1.356e-07 | 1 | 0 | 9e-07 | n/a | 0.847 | n/a | 3.6 | PASS |
| `ss_125c_3v60__case4` | ss_125c_3v60 | 4 | ok | 1.237e+04 | n/a | n/a | 3.6 | 5.752e-09 | 1 | n/a | n/a | 1.237e-05 | 1 | 0 | 9e-05 | n/a | 0.5093 | n/a | 3.6 | PASS |
| `ss_125c_3v60__case5` | ss_125c_3v60 | 5 | ok | 63.13 | 0.08893 | n/a | 3.6 | -2.579e-09 | 1 | n/a | n/a | 6.313e-08 | 1 | 0 | n/a | 6.888e-06 | n/a | n/a | 3.601 | PASS |
| `fs_m40c_3v00__case0` | fs_m40c_3v00 | 0 | ok | 8 | n/a | n/a | 5.188e-10 | 5.188e-10 | 1 | n/a | 1.921e-08 | 1 | 8e-09 | 6 | n/a | n/a | n/a | n/a | 0.216 | PASS |
| `fs_m40c_3v00__case1` | fs_m40c_3v00 | 1 | ok | 1.988 FAIL | n/a | 1 | 1.9 | 3.876e-10 | 1 | n/a | n/a | 1.988e-09 | 1.3e-08 | 3 | n/a | n/a | n/a | 1.902 | 0.2106 | FAIL: min_pulse_s=1.988e-09 outside [2e-09, inf] |
| `fs_m40c_3v00__case2` | fs_m40c_3v00 | 2 | ok | 8 | n/a | n/a | 5.674e-10 | 5.187e-10 | 1 | 1 | n/a | 3.152e-08 | 8e-09 | 6 | n/a | 2.253e-08 | n/a | n/a | 3.091 | PASS |
| `fs_m40c_3v00__case3` | fs_m40c_3v00 | 3 | ok | 186.3 | n/a | n/a | 3 | 5.187e-10 | 1 | n/a | n/a | 1.863e-07 | 1 | 0 | 9e-07 | n/a | 0.9025 | n/a | 3 | PASS |
| `fs_m40c_3v00__case4` | fs_m40c_3v00 | 4 | ok | 1.641e+04 | n/a | n/a | 3 | 5.152e-10 | 1 | n/a | n/a | 1.641e-05 | 1 | 0 | 9e-05 | n/a | 0.7329 | n/a | 3 | PASS |
| `fs_m40c_3v00__case5` | fs_m40c_3v00 | 5 | ok | 59.73 | 0.1437 | n/a | 3 | 1.589e-09 | 1 | n/a | n/a | 5.973e-08 | 1.68e-06 | 6 | n/a | 4.654e-06 | n/a | n/a | 3 | PASS |
| `fs_m40c_3v30__case0` | fs_m40c_3v30 | 0 | ok | 8 | n/a | n/a | 6.479e-10 | 6.479e-10 | 1 | n/a | 1.708e-08 | 1 | 8e-09 | 6 | n/a | n/a | n/a | n/a | 0.2164 | PASS |
| `fs_m40c_3v30__case1` | fs_m40c_3v30 | 1 | ok | **1.986** (worst) FAIL | n/a | 1 | 1.9 | 3.876e-10 | 1 | n/a | n/a | 1.986e-09 | 1.3e-08 | 3 | n/a | n/a | n/a | 1.901 | 0.2106 | FAIL: min_pulse_s=1.986e-09 outside [2e-09, inf] |
| `fs_m40c_3v30__case2` | fs_m40c_3v30 | 2 | ok | 8 | n/a | n/a | 3.339e-10 | 6.478e-10 | 1 | 1 | n/a | 2.663e-08 | 8e-09 | 6 | n/a | 2.152e-08 | n/a | n/a | 3.396 | PASS |
| `fs_m40c_3v30__case3` | fs_m40c_3v30 | 3 | timeout | n/a FAIL | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | FAIL: status=timeout; min_pulse_s missing |
| `fs_m40c_3v30__case4` | fs_m40c_3v30 | 4 | timeout | n/a FAIL | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | FAIL: status=timeout; min_pulse_s missing |
| `fs_m40c_3v30__case5` | fs_m40c_3v30 | 5 | ok | 57.69 | 0.1448 | n/a | 3.3 | 2.061e-09 | 1 | n/a | n/a | 5.769e-08 | 1.56e-06 | 6 | n/a | 5.87e-06 | n/a | n/a | 3.3 | PASS |
| `fs_m40c_3v60__case0` | fs_m40c_3v60 | 0 | ok | 8 | n/a | n/a | 9.237e-10 | 9.237e-10 | 1 | n/a | 1.707e-08 | 1 | 8e-09 | 6 | n/a | n/a | n/a | n/a | 0.2176 | PASS |
| `fs_m40c_3v60__case1` | fs_m40c_3v60 | 1 | ok | 1.987 FAIL | n/a | 1 | 1.9 | 3.876e-10 | 1 | n/a | n/a | 1.987e-09 | 1.3e-08 | 3 | n/a | n/a | n/a | 1.902 | 0.2106 | FAIL: min_pulse_s=1.987e-09 outside [2e-09, inf] |
| `fs_m40c_3v60__case2` | fs_m40c_3v60 | 2 | ok | 8 | n/a | n/a | 8.677e-10 | 9.234e-10 | 1 | 1 | n/a | 2.257e-08 | 8e-09 | 6 | n/a | 2.037e-08 | n/a | n/a | 3.672 | PASS |
| `fs_m40c_3v60__case3` | fs_m40c_3v60 | 3 | ok | 168.9 | n/a | n/a | 3.6 | 9.237e-10 | 1 | n/a | n/a | 1.689e-07 | 1 | 0 | 9e-07 | n/a | 0.9112 | n/a | 3.6 | PASS |
| `fs_m40c_3v60__case4` | fs_m40c_3v60 | 4 | timeout | n/a FAIL | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | FAIL: status=timeout; min_pulse_s missing |
| `fs_m40c_3v60__case5` | fs_m40c_3v60 | 5 | ok | 57.2 | 0.1459 | n/a | 3.6 | 8.83e-09 | 1 | n/a | n/a | 5.72e-08 | 1.44e-06 | 6 | n/a | 6.88e-06 | n/a | n/a | 3.6 | PASS |
| `fs_27c_3v00__case0` | fs_27c_3v00 | 0 | ok | 7 | n/a | n/a | 6.357e-10 | 6.357e-10 | 1 | n/a | 2.773e-08 | 1 | 7e-09 | 6 | n/a | n/a | n/a | n/a | 0.1824 | PASS |
| `fs_27c_3v00__case1` | fs_27c_3v00 | 1 | ok | 2.205 | n/a | 1 | 1.9 | 4.893e-10 | 1 | n/a | n/a | 2.205e-09 | 1e-08 | 3 | n/a | n/a | n/a | 1.904 | 0.1749 | PASS |
| `fs_27c_3v00__case2` | fs_27c_3v00 | 2 | ok | 7 | n/a | n/a | 7.32e-10 | 6.353e-10 | 1 | 1 | n/a | 2.674e-08 | 7e-09 | 6 | n/a | 2.251e-08 | n/a | n/a | 3.104 | PASS |
| `fs_27c_3v00__case3` | fs_27c_3v00 | 3 | ok | 180.1 | n/a | n/a | 3 | 6.354e-10 | 1 | n/a | n/a | 1.801e-07 | 1 | 0 | 9e-07 | n/a | 0.8153 | n/a | 3 | PASS |
| `fs_27c_3v00__case4` | fs_27c_3v00 | 4 | ok | 1.78e+04 | n/a | n/a | 3 | 6.348e-10 | 1 | n/a | n/a | 1.78e-05 | 1 | 0 | 9e-05 | n/a | 0.5937 | n/a | 3 | PASS |
| `fs_27c_3v00__case5` | fs_27c_3v00 | 5 | ok | 46.76 | 0.08864 | n/a | 3 | 4.047e-09 | 1 | n/a | n/a | 4.676e-08 | 5.4e-07 | 6 | n/a | 4.669e-06 | n/a | n/a | 3.001 | PASS |
| `fs_27c_3v30__case0` | fs_27c_3v30 | 0 | ok | 7 | n/a | n/a | 7.873e-10 | 7.873e-10 | 1 | n/a | 1.79e-08 | 1 | 7e-09 | 6 | n/a | n/a | n/a | n/a | 0.1841 | PASS |
| `fs_27c_3v30__case1` | fs_27c_3v30 | 1 | ok | 3.034 | n/a | 1 | 1.9 | 4.893e-10 | 1 | n/a | n/a | 3.034e-09 | 1e-08 | 3 | n/a | n/a | n/a | 1.984 | 0.1749 | PASS |
| `fs_27c_3v30__case2` | fs_27c_3v30 | 2 | ok | 7 | n/a | n/a | 8.12e-10 | 7.878e-10 | 1 | 1 | n/a | 2.338e-08 | 7e-09 | 6 | n/a | 2.129e-08 | n/a | n/a | 3.409 | PASS |
| `fs_27c_3v30__case3` | fs_27c_3v30 | 3 | ok | 171.2 | n/a | n/a | 3.3 | 7.876e-10 | 1 | n/a | n/a | 1.712e-07 | 1 | 0 | 9e-07 | n/a | 0.8209 | n/a | 3.3 | PASS |
| `fs_27c_3v30__case4` | fs_27c_3v30 | 4 | ok | 1.627e+04 | n/a | n/a | 3.3 | 7.871e-10 | 1 | n/a | n/a | 1.627e-05 | 1 | 0 | 9e-05 | n/a | 0.5976 | n/a | 3.3 | PASS |
| `fs_27c_3v30__case5` | fs_27c_3v30 | 5 | ok | 47.49 | 0.09003 | n/a | 3.3 | -9.539e-10 | 1 | n/a | n/a | 4.749e-08 | 5.4e-07 | 6 | n/a | 5.869e-06 | n/a | n/a | 3.3 | PASS |
| `fs_27c_3v60__case0` | fs_27c_3v60 | 0 | ok | 7 | n/a | n/a | 1.115e-09 | 1.115e-09 | 1 | n/a | 1.814e-08 | 1 | 7e-09 | 6 | n/a | n/a | n/a | n/a | 0.1855 | PASS |
| `fs_27c_3v60__case1` | fs_27c_3v60 | 1 | ok | 3.041 | n/a | 1 | 1.9 | 4.893e-10 | 1 | n/a | n/a | 3.041e-09 | 1e-08 | 3 | n/a | n/a | n/a | 1.983 | 0.1749 | PASS |
| `fs_27c_3v60__case2` | fs_27c_3v60 | 2 | ok | 7 | n/a | n/a | 1.064e-09 | 1.114e-09 | 1 | 1 | n/a | 2.006e-08 | 7e-09 | 6 | n/a | 2.037e-08 | n/a | n/a | 3.685 | PASS |
| `fs_27c_3v60__case3` | fs_27c_3v60 | 3 | ok | 163.1 | n/a | n/a | 3.6 | 1.115e-09 | 1 | n/a | n/a | 1.631e-07 | 1 | 0 | 9e-07 | n/a | 0.8261 | n/a | 3.6 | PASS |
| `fs_27c_3v60__case4` | fs_27c_3v60 | 4 | ok | 1.463e+04 | n/a | n/a | 3.6 | 1.114e-09 | 1 | n/a | n/a | 1.463e-05 | 1 | 0 | 9e-05 | n/a | 0.6012 | n/a | 3.6 | PASS |
| `fs_27c_3v60__case5` | fs_27c_3v60 | 5 | ok | 46.84 | 0.0913 | n/a | 3.6 | 3.151e-09 | 1 | n/a | n/a | 4.684e-08 | 5.2e-07 | 6 | n/a | 6.887e-06 | n/a | n/a | 3.601 | PASS |
| `fs_125c_3v00__case0` | fs_125c_3v00 | 0 | ok | 5 | n/a | n/a | 6.685e-09 | 6.685e-09 | 1 | n/a | 3.398e-08 | 1 | 5e-09 | 6 | n/a | n/a | n/a | n/a | 0.1327 | PASS |
| `fs_125c_3v00__case1` | fs_125c_3v00 | 1 | ok | 5.051 | n/a | 1 | 1.9 | 6.375e-09 | 1 | n/a | n/a | 5.051e-09 | 6e-09 | 3 | n/a | n/a | n/a | 1.904 | 0.1227 | PASS |
| `fs_125c_3v00__case2` | fs_125c_3v00 | 2 | ok | 5 | n/a | n/a | 2.19e-08 | 6.685e-09 | 1 | 1 | n/a | 2.15e-08 | 5e-09 | 6 | n/a | 2.331e-08 | n/a | n/a | 3.118 | PASS |
| `fs_125c_3v00__case3` | fs_125c_3v00 | 3 | ok | 15 | n/a | n/a | 3 | 6.685e-09 | 1 | n/a | n/a | 1.718e-07 | 1.5e-08 | 6 | 9e-07 | n/a | 0.6675 | n/a | 3 | PASS |
| `fs_125c_3v00__case4` | fs_125c_3v00 | 4 | ok | 1.379e+04 | n/a | n/a | 3 | 6.685e-09 | 1 | n/a | n/a | 1.379e-05 | 1 | 0 | 9e-05 | n/a | 0.5451 | n/a | 3 | PASS |
| `fs_125c_3v00__case5` | fs_125c_3v00 | 5 | ok | 36.5 | 0.02519 | n/a | 3 | -5.275e-09 | 1 | n/a | n/a | 3.65e-08 | 1 | 0 | n/a | 4.662e-06 | n/a | n/a | 3.001 | PASS |
| `fs_125c_3v30__case0` | fs_125c_3v30 | 0 | ok | 5 | n/a | n/a | 7.138e-09 | 7.138e-09 | 1 | n/a | 3.644e-08 | 1 | 5e-09 | 6 | n/a | n/a | n/a | n/a | 0.135 | PASS |
| `fs_125c_3v30__case1` | fs_125c_3v30 | 1 | ok | 5.052 | n/a | 1 | 1.9 | 6.375e-09 | 1 | n/a | n/a | 5.052e-09 | 6e-09 | 3 | n/a | n/a | n/a | 1.905 | 0.1227 | PASS |
| `fs_125c_3v30__case2` | fs_125c_3v30 | 2 | ok | 5 | n/a | n/a | 1.209e-08 | 7.138e-09 | 1 | 1 | n/a | 1.851e-08 | 5e-09 | 6 | n/a | 2.157e-08 | n/a | n/a | 3.396 | PASS |
| `fs_125c_3v30__case3` | fs_125c_3v30 | 3 | ok | 20 | n/a | n/a | 3.3 | 7.138e-09 | 1 | n/a | n/a | 1.725e-07 | 2e-08 | 6 | 9e-07 | n/a | 0.6746 | n/a | 3.3 | PASS |
| `fs_125c_3v30__case4` | fs_125c_3v30 | 4 | ok | 1.266e+04 | n/a | n/a | 3.3 | 7.138e-09 | 1 | n/a | n/a | 1.266e-05 | 1 | 0 | 9e-05 | n/a | 0.5509 | n/a | 3.3 | PASS |
| `fs_125c_3v30__case5` | fs_125c_3v30 | 5 | ok | 36.16 | 0.02629 | n/a | 3.3 | 1.693e-08 | 1 | n/a | n/a | 3.616e-08 | 1 | 0 | n/a | 5.872e-06 | n/a | n/a | 3.3 | PASS |
| `fs_125c_3v60__case0` | fs_125c_3v60 | 0 | ok | 5 | n/a | n/a | 7.903e-09 | 7.903e-09 | 1 | n/a | 3.977e-08 | 1 | 5e-09 | 6 | n/a | n/a | n/a | n/a | 0.1366 | PASS |
| `fs_125c_3v60__case1` | fs_125c_3v60 | 1 | ok | 5.995 | n/a | 1 | 1.9 | 6.375e-09 | 1 | n/a | n/a | 5.995e-09 | 6e-09 | 3 | n/a | n/a | n/a | 1.912 | 0.1227 | PASS |
| `fs_125c_3v60__case2` | fs_125c_3v60 | 2 | ok | 5 | n/a | n/a | 7.876e-09 | 7.903e-09 | 1 | 1 | n/a | 1.618e-08 | 5e-09 | 6 | n/a | 2.055e-08 | n/a | n/a | 3.7 | PASS |
| `fs_125c_3v60__case3` | fs_125c_3v60 | 3 | ok | 164.3 | n/a | n/a | 3.6 | 7.903e-09 | 1 | n/a | n/a | 1.643e-07 | 1 | 0 | 9e-07 | n/a | 0.6811 | n/a | 3.6 | PASS |
| `fs_125c_3v60__case4` | fs_125c_3v60 | 4 | ok | 1.154e+04 | n/a | n/a | 3.6 | 7.903e-09 | 1 | n/a | n/a | 1.154e-05 | 1 | 0 | 9e-05 | n/a | 0.5562 | n/a | 3.6 | PASS |
| `fs_125c_3v60__case5` | fs_125c_3v60 | 5 | ok | 37.46 | 0.02732 | n/a | 3.6 | 1.36e-08 | 1 | n/a | n/a | 3.746e-08 | 1 | 0 | n/a | 6.891e-06 | n/a | n/a | 3.6 | PASS |
| `sf_m40c_3v00__case0` | sf_m40c_3v00 | 0 | ok | 7 | n/a | n/a | 6.148e-10 | 6.148e-10 | 1 | n/a | 1.977e-08 | 1 | 7e-09 | 6 | n/a | n/a | n/a | n/a | 0.2336 | PASS |
| `sf_m40c_3v00__case1` | sf_m40c_3v00 | 1 | ok | 6.358 | n/a | 1 | 1.9 | 4.598e-10 | 1 | n/a | n/a | 6.358e-09 | 1.1e-08 | 3 | n/a | n/a | n/a | 1.949 | 0.2271 | PASS |
| `sf_m40c_3v00__case2` | sf_m40c_3v00 | 2 | ok | 7 | n/a | n/a | 6.348e-10 | 6.147e-10 | 1 | 1 | n/a | 3.285e-08 | 7e-09 | 6 | n/a | 2.561e-08 | n/a | n/a | 3.08 | PASS |
| `sf_m40c_3v00__case3` | sf_m40c_3v00 | 3 | ok | 86.97 | n/a | n/a | 3 | 6.146e-10 | 1 | n/a | n/a | 8.697e-08 | 1 | 0 | 9e-07 | n/a | 0.9816 | n/a | 3 | PASS |
| `sf_m40c_3v00__case4` | sf_m40c_3v00 | 4 | timeout | n/a FAIL | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | FAIL: status=timeout; min_pulse_s missing |
| `sf_m40c_3v00__case5` | sf_m40c_3v00 | 5 | ok | 63.87 | 0.1821 | n/a | 3 | -1.18e-09 | 1 | n/a | n/a | 6.387e-08 | 1.08e-06 | 6 | n/a | 4.652e-06 | n/a | n/a | 3 | PASS |
| `sf_m40c_3v30__case0` | sf_m40c_3v30 | 0 | ok | 7 | n/a | n/a | 8.295e-10 | 8.295e-10 | 1 | n/a | 1.712e-08 | 1 | 7e-09 | 6 | n/a | n/a | n/a | n/a | 0.2324 | PASS |
| `sf_m40c_3v30__case1` | sf_m40c_3v30 | 1 | ok | 6.354 | n/a | 1 | 1.9 | 4.598e-10 | 1 | n/a | n/a | 6.354e-09 | 1.1e-08 | 3 | n/a | n/a | n/a | 1.95 | 0.2271 | PASS |
| `sf_m40c_3v30__case2` | sf_m40c_3v30 | 2 | ok | 7 | n/a | n/a | 8.506e-10 | 8.292e-10 | 1 | 1 | n/a | 2.819e-08 | 7e-09 | 6 | n/a | 2.356e-08 | n/a | n/a | 3.363 | PASS |
| `sf_m40c_3v30__case3` | sf_m40c_3v30 | 3 | ok | 84.97 | n/a | n/a | 3.3 | 8.296e-10 | 1 | n/a | n/a | 8.497e-08 | 1 | 0 | 9e-07 | n/a | 0.986 | n/a | 3.3 | PASS |
| `sf_m40c_3v30__case4` | sf_m40c_3v30 | 4 | ok | 2480 | n/a | n/a | 3.3 | 8.293e-10 | 1 | n/a | n/a | 2.48e-06 | 1 | 0 | 9e-05 | n/a | 0.7312 | n/a | 3.3 | PASS |
| `sf_m40c_3v30__case5` | sf_m40c_3v30 | 5 | ok | 66.36 | 0.1825 | n/a | 3.3 | 1.717e-08 | 1 | n/a | n/a | 6.636e-08 | 1.02e-06 | 6 | n/a | 5.885e-06 | n/a | n/a | 3.303 | PASS |
| `sf_m40c_3v60__case0` | sf_m40c_3v60 | 0 | ok | 7 | n/a | n/a | 1.297e-09 | 1.297e-09 | 1 | n/a | 1.762e-08 | 1 | 7e-09 | 6 | n/a | n/a | n/a | n/a | 0.2227 | PASS |
| `sf_m40c_3v60__case1` | sf_m40c_3v60 | 1 | ok | 7.36 | n/a | 1 | 1.9 | 4.598e-10 | 1 | n/a | n/a | 7.36e-09 | 1.1e-08 | 3 | n/a | n/a | n/a | 1.953 | 0.2271 | PASS |
| `sf_m40c_3v60__case2` | sf_m40c_3v60 | 2 | ok | 7 | n/a | n/a | 1.349e-09 | 1.297e-09 | 1 | 1 | n/a | 2.499e-08 | 7e-09 | 6 | n/a | 2.205e-08 | n/a | n/a | 3.666 | PASS |
| `sf_m40c_3v60__case3` | sf_m40c_3v60 | 3 | ok | 81.96 | n/a | n/a | 3.6 | 1.297e-09 | 1 | n/a | n/a | 8.196e-08 | 1 | 0 | 9e-07 | n/a | 0.991 | n/a | 3.6 | PASS |
| `sf_m40c_3v60__case4` | sf_m40c_3v60 | 4 | ok | 2345 | n/a | n/a | 3.6 | 1.297e-09 | 1 | n/a | n/a | 2.345e-06 | 1 | 0 | 9e-05 | n/a | 0.7345 | n/a | 3.6 | PASS |
| `sf_m40c_3v60__case5` | sf_m40c_3v60 | 5 | timeout | n/a FAIL | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | FAIL: status=timeout; min_pulse_s missing |
| `sf_27c_3v00__case0` | sf_27c_3v00 | 0 | ok | 6 | n/a | n/a | 1.065e-09 | 1.065e-09 | 1 | n/a | 1.807e-08 | 1 | 6e-09 | 6 | n/a | n/a | n/a | n/a | 0.2256 | PASS |
| `sf_27c_3v00__case1` | sf_27c_3v00 | 1 | ok | 6.985 | n/a | 1 | 1.9 | 8.506e-10 | 1 | n/a | n/a | 6.985e-09 | 9e-09 | 3 | n/a | n/a | n/a | 1.914 | 0.2115 | PASS |
| `sf_27c_3v00__case2` | sf_27c_3v00 | 2 | ok | 6 | n/a | n/a | 1.072e-09 | 1.065e-09 | 1 | 1 | n/a | 2.798e-08 | 6e-09 | 6 | n/a | 2.475e-08 | n/a | n/a | 3.069 | PASS |
| `sf_27c_3v00__case3` | sf_27c_3v00 | 3 | ok | 90.53 | n/a | n/a | 3 | 1.065e-09 | 1 | n/a | n/a | 9.053e-08 | 1 | 0 | 9e-07 | n/a | 0.8797 | n/a | 3 | PASS |
| `sf_27c_3v00__case4` | sf_27c_3v00 | 4 | ok | 3336 | n/a | n/a | 3 | 1.065e-09 | 1 | n/a | n/a | 3.336e-06 | 1 | 0 | 9e-05 | n/a | 0.6164 | n/a | 3 | PASS |
| `sf_27c_3v00__case5` | sf_27c_3v00 | 5 | ok | 55.1 | 0.1495 | n/a | 3 | -1.214e-09 | 1 | n/a | n/a | 5.51e-08 | 3.2e-07 | 6 | n/a | 4.661e-06 | n/a | n/a | 3.003 | PASS |
| `sf_27c_3v30__case0` | sf_27c_3v30 | 0 | ok | 6 | n/a | n/a | 1.351e-09 | 1.351e-09 | 1 | n/a | 1.83e-08 | 1 | 6e-09 | 6 | n/a | n/a | n/a | n/a | 0.2159 | PASS |
| `sf_27c_3v30__case1` | sf_27c_3v30 | 1 | ok | 7.98 | n/a | 1 | 1.9 | 8.504e-10 | 1 | n/a | n/a | 7.98e-09 | 9e-09 | 3 | n/a | n/a | n/a | 2.01 | 0.2114 | PASS |
| `sf_27c_3v30__case2` | sf_27c_3v30 | 2 | ok | 6 | n/a | n/a | 1.359e-09 | 1.351e-09 | 1 | 1 | n/a | 2.528e-08 | 6e-09 | 6 | n/a | 2.365e-08 | n/a | n/a | 3.396 | PASS |
| `sf_27c_3v30__case3` | sf_27c_3v30 | 3 | ok | 97.38 | n/a | n/a | 3.3 | 1.351e-09 | 1 | n/a | n/a | 9.738e-08 | 1 | 0 | 9e-07 | n/a | 0.8855 | n/a | 3.3 | PASS |
| `sf_27c_3v30__case4` | sf_27c_3v30 | 4 | ok | 3044 | n/a | n/a | 3.3 | 1.35e-09 | 1 | n/a | n/a | 3.044e-06 | 1 | 0 | 9e-05 | n/a | 0.6209 | n/a | 3.3 | PASS |
| `sf_27c_3v30__case5` | sf_27c_3v30 | 5 | ok | 55.03 | 0.1501 | n/a | 3.3 | 3.364e-09 | 1 | n/a | n/a | 5.503e-08 | 3.4e-07 | 6 | n/a | 5.886e-06 | n/a | n/a | 3.3 | PASS |
| `sf_27c_3v60__case0` | sf_27c_3v60 | 0 | ok | 6 | n/a | n/a | 1.949e-09 | 1.949e-09 | 1 | n/a | 1.859e-08 | 1 | 6e-09 | 6 | n/a | n/a | n/a | n/a | 0.2159 | PASS |
| `sf_27c_3v60__case1` | sf_27c_3v60 | 1 | ok | 8.57 | n/a | 1 | 1.9 | 8.506e-10 | 1 | n/a | n/a | 8.57e-09 | 9e-09 | 3 | n/a | n/a | n/a | 1.969 | 0.2115 | PASS |
| `sf_27c_3v60__case2` | sf_27c_3v60 | 2 | ok | 6 | n/a | n/a | 1.93e-09 | 1.949e-09 | 1 | 1 | n/a | 2.138e-08 | 6e-09 | 6 | n/a | 2.207e-08 | n/a | n/a | 3.676 | PASS |
| `sf_27c_3v60__case3` | sf_27c_3v60 | 3 | ok | 59.03 | n/a | n/a | 3.6 | 1.949e-09 | 1 | n/a | n/a | 5.903e-08 | 1 | 0 | 9e-07 | n/a | 0.8908 | n/a | 3.6 | PASS |
| `sf_27c_3v60__case4` | sf_27c_3v60 | 4 | ok | 2798 | n/a | n/a | 3.6 | 1.949e-09 | 1 | n/a | n/a | 2.798e-06 | 1 | 0 | 9e-05 | n/a | 0.625 | n/a | 3.6 | PASS |
| `sf_27c_3v60__case5` | sf_27c_3v60 | 5 | timeout | n/a FAIL | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | FAIL: status=timeout; min_pulse_s missing |
| `sf_125c_3v00__case0` | sf_125c_3v00 | 0 | ok | 5 | n/a | n/a | 2.711e-07 | 2.711e-07 | 1 | n/a | 2.597e-08 | 1 | 5e-09 | 6 | n/a | n/a | n/a | n/a | 0.1929 | PASS |
| `sf_125c_3v00__case1` | sf_125c_3v00 | 1 | ok | 6 | n/a | 1 | 1.9 | 2.695e-07 | 1 | n/a | n/a | 9.967e-09 | 6e-09 | 3 | n/a | n/a | n/a | 1.904 | 0.184 | PASS |
| `sf_125c_3v00__case2` | sf_125c_3v00 | 2 | ok | 5 | n/a | n/a | 2.711e-07 | 2.711e-07 | 1 | 1 | n/a | 2.328e-08 | 5e-09 | 6 | n/a | 2.534e-08 | n/a | n/a | 3.103 | PASS |
| `sf_125c_3v00__case3` | sf_125c_3v00 | 3 | ok | 85.78 | n/a | n/a | 3 | 2.711e-07 | 1 | n/a | n/a | 8.578e-08 | 1 | 0 | 9e-07 | n/a | 0.7021 | n/a | 3 | PASS |
| `sf_125c_3v00__case4` | sf_125c_3v00 | 4 | ok | 2231 | n/a | n/a | 3 | 2.711e-07 | 1 | n/a | n/a | 2.231e-06 | 1 | 0 | 9e-05 | n/a | 0.5 | n/a | 3 | PASS |
| `sf_125c_3v00__case5` | sf_125c_3v00 | 5 | ok | 37.99 | 0.1129 | n/a | 3 | 2.857e-07 | 1 | n/a | n/a | 3.799e-08 | 1 | 0 | n/a | 4.647e-06 | n/a | n/a | 3 | PASS |
| `sf_125c_3v30__case0` | sf_125c_3v30 | 0 | timeout | n/a FAIL | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | FAIL: status=timeout; min_pulse_s missing |
| `sf_125c_3v30__case1` | sf_125c_3v30 | 1 | ok | 6 | n/a | 1 | 1.9 | 2.695e-07 | 1 | n/a | n/a | 1.097e-08 | 6e-09 | 3 | n/a | n/a | n/a | 1.956 | 0.1842 | PASS |
| `sf_125c_3v30__case2` | sf_125c_3v30 | 2 | ok | 5 | n/a | n/a | 2.844e-07 | 2.845e-07 | 1 | 1 | n/a | 2.039e-08 | 5e-09 | 6 | n/a | 2.38e-08 | n/a | n/a | 3.41 | PASS |
| `sf_125c_3v30__case3` | sf_125c_3v30 | 3 | ok | 87.81 | n/a | n/a | 3.3 | 2.845e-07 | 1 | n/a | n/a | 8.781e-08 | 1 | 0 | 9e-07 | n/a | 0.71 | n/a | 3.3 | PASS |
| `sf_125c_3v30__case4` | sf_125c_3v30 | 4 | ok | 2215 | n/a | n/a | 3.3 | 2.845e-07 | 1 | n/a | n/a | 2.215e-06 | 1 | 0 | 9e-05 | n/a | 0.5 | n/a | 3.3 | PASS |
| `sf_125c_3v30__case5` | sf_125c_3v30 | 5 | ok | 42.42 | 0.1137 | n/a | 3.3 | 2.717e-07 | 1 | n/a | n/a | 4.242e-08 | 1 | 0 | n/a | 5.884e-06 | n/a | n/a | 3.302 | PASS |
| `sf_125c_3v60__case0` | sf_125c_3v60 | 0 | ok | 5 | n/a | n/a | 3.036e-07 | 3.036e-07 | 1 | n/a | 2.723e-08 | 1 | 5e-09 | 6 | n/a | n/a | n/a | n/a | 0.1928 | PASS |
| `sf_125c_3v60__case1` | sf_125c_3v60 | 1 | ok | 6 | n/a | 1 | 1.9 | 2.695e-07 | 1 | n/a | n/a | 1.124e-08 | 6e-09 | 3 | n/a | n/a | n/a | 1.918 | 0.184 | PASS |
| `sf_125c_3v60__case2` | sf_125c_3v60 | 2 | ok | 5 | n/a | n/a | 3.036e-07 | 3.036e-07 | 1 | 1 | n/a | 1.774e-08 | 5e-09 | 6 | n/a | 2.203e-08 | n/a | n/a | 3.688 | PASS |
| `sf_125c_3v60__case3` | sf_125c_3v60 | 3 | ok | 89 | n/a | n/a | 3.6 | 3.036e-07 | 1 | n/a | n/a | 8.9e-08 | 1 | 0 | 9e-07 | n/a | 0.7173 | n/a | 3.6 | PASS |
| `sf_125c_3v60__case4` | sf_125c_3v60 | 4 | ok | 2184 | n/a | n/a | 3.6 | 3.036e-07 | 1 | n/a | n/a | 2.184e-06 | 1 | 0 | 9e-05 | n/a | 0.5 | n/a | 3.6 | PASS |
| `sf_125c_3v60__case5` | sf_125c_3v60 | 5 | ok | 39.63 | 0.1144 | n/a | 3.6 | 3.014e-07 | 1 | n/a | n/a | 3.963e-08 | 1 | 0 | n/a | 6.897e-06 | n/a | n/a | 3.6 | PASS |

## Failed runs (explicit, not dropped)

| run | status | first error |
|---|---|---|
| `tt_m40c_3v60__case5` | timeout | killed after 1800 s timeout |
| `tt_27c_3v00__case3` | timeout | killed after 1800 s timeout |
| `tt_27c_3v60__case5` | timeout | killed after 1800 s timeout |
| `ff_m40c_3v00__case0` | timeout | killed after 1800 s timeout |
| `ff_m40c_3v30__case3` | timeout | killed after 1800 s timeout |
| `ff_27c_3v60__case4` | timeout | killed after 1800 s timeout |
| `ff_125c_3v60__case3` | timeout | killed after 1800 s timeout |
| `ss_m40c_3v00__case5` | timeout | killed after 1800 s timeout |
| `ss_m40c_3v30__case5` | timeout | killed after 1800 s timeout |
| `ss_27c_3v30__case4` | timeout | killed after 1800 s timeout |
| `ss_27c_3v60__case4` | timeout | killed after 1800 s timeout |
| `ss_125c_3v30__case5` | timeout | killed after 1800 s timeout |
| `fs_m40c_3v30__case3` | timeout | killed after 1800 s timeout |
| `fs_m40c_3v30__case4` | timeout | killed after 1800 s timeout |
| `fs_m40c_3v60__case4` | timeout | killed after 1800 s timeout |
| `sf_m40c_3v00__case4` | timeout | killed after 1800 s timeout |
| `sf_m40c_3v60__case5` | timeout | killed after 1800 s timeout |
| `sf_27c_3v60__case5` | timeout | killed after 1800 s timeout |
| `sf_125c_3v30__case0` | timeout | killed after 1800 s timeout |
