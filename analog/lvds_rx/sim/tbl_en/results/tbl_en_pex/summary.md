# tbl_en_pex

**Overall: PASS**

post-layout gate TBL (pex): tb8_en with core = sim/tbl/core_pexrc.spice

Runs: **24** (ok 24); 18 reused from cache.

## Worst case per metric

| metric | limit | worst run | value | margin | verdict |
|---|---|---|---|---|---|
| min_pulse_s (ns) | 2 .. - | `ff_125c_3v60__case3` | **8** | 6 | PASS |

## All runs

| run | corner | case | status | min_pulse_s (ns) | early_high_v | en1_valid_ok | end_a_v | end_b_v | final_ok | high_phase_ok | idd_en0_a | min_pulse_all_s | min_pulse_cross_s | min_runt_width_s | n_runt | t_high_s | valid_time_s | vdd_at_out_rise_v | vdd_at_peak_v | vdd_low_from_v | vout_en1_v | vout_off_all_v | vout_off_v | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `ff_125c_3v60__case0` | ff_125c_3v60 | 0 | ok | 1e+09 | n/a | n/a | 7.399e-07 | 7.399e-07 | 1 | n/a | 1.349e-07 | 3e-09 | 1 | 1 | 0 | n/a | n/a | n/a | 0.5777 | 0.6497 | n/a | 0.1717 | 1.41e-06 | PASS |
| `ff_125c_3v60__case1` | ff_125c_3v60 | 1 | ok | 1e+09 | n/a | 1 | 1.9 | 5.929e-07 | 1 | n/a | n/a | 4e-09 | 1 | 1 | 0 | n/a | n/a | n/a | 0.5329 | 0.6469 | 1.902 | 0.1556 | 6.382e-07 | PASS |
| `ff_125c_3v60__case2` | ff_125c_3v60 | 2 | ok | 21.11 | n/a | n/a | 7.652e-07 | 7.4e-07 | 1 | 1 | n/a | 3e-09 | 2.111e-08 | 1 | 0 | n/a | 1.176e-08 | n/a | n/a | n/a | n/a | 3.729 | 3.729 | PASS |
| `ff_125c_3v60__case3` | ff_125c_3v60 | 3 | ok | **8** (worst) | n/a | n/a | 3.6 | 7.399e-07 | 1 | n/a | n/a | 8e-09 | 2.175e-08 | 8e-09 | 6 | 9e-07 | n/a | 0.7472 | n/a | n/a | n/a | 3.6 | 3.6 | PASS |
| `ff_125c_3v60__case4` | ff_125c_3v60 | 4 | ok | 1381 | n/a | n/a | 3.6 | 7.399e-07 | 1 | n/a | n/a | 1.381e-06 | 1.381e-06 | 1 | 0 | 9e-05 | n/a | 0.5001 | n/a | n/a | n/a | 3.6 | 3.6 | PASS |
| `ff_125c_3v60__case5` | ff_125c_3v60 | 5 | ok | 41.91 | 0.0446 | n/a | 3.6 | 7.322e-07 | 1 | n/a | n/a | 4.191e-08 | 4.191e-08 | 1 | 0 | n/a | 6.892e-06 | n/a | n/a | n/a | n/a | 3.601 | 3.601 | PASS |
| `ff_125c_3v60__case6` | ff_125c_3v60 | 6 | ok | 1e+09 | n/a | n/a | 7.399e-07 | 7.399e-07 | 1 | n/a | n/a | 1 | 1 | 1 | 0 | n/a | n/a | n/a | 0.3745 | 0 | n/a | 0.09818 | 0.09818 | PASS |
| `ff_125c_3v60__case7` | ff_125c_3v60 | 7 | ok | 1e+09 | n/a | n/a | 7.399e-07 | 7.399e-07 | 1 | n/a | n/a | 1 | 1 | 1 | 0 | n/a | n/a | n/a | 0.1387 | 0 | n/a | 0.03042 | 0.03042 | PASS |
| `ss_125c_3v00__case0` | ss_125c_3v00 | 0 | ok | 1e+09 | n/a | n/a | 1.147e-08 | 1.147e-08 | 1 | n/a | 4.847e-08 | 8e-09 | 1 | 1 | 0 | n/a | n/a | n/a | 0.9014 | 0.9614 | n/a | 0.2793 | 2.694e-07 | PASS |
| `ss_125c_3v00__case1` | ss_125c_3v00 | 1 | ok | 1e+09 | n/a | 1 | 1.9 | 1.139e-08 | 1 | n/a | n/a | 1.1e-08 | 1 | 1 | 0 | n/a | n/a | n/a | 0.8749 | 0.9129 | 1.985 | 0.2666 | 1.068e-07 | PASS |
| `ss_125c_3v00__case2` | ss_125c_3v00 | 2 | ok | 56.33 | n/a | n/a | -2.146e-07 | 1.145e-08 | 1 | 1 | n/a | 8e-09 | 5.633e-08 | 1 | 0 | n/a | 2.57e-08 | n/a | n/a | n/a | n/a | 3.152 | 3.152 | PASS |
| `ss_125c_3v00__case3` | ss_125c_3v00 | 3 | ok | 28.24 | n/a | n/a | 3 | 1.153e-08 | 1 | n/a | n/a | 2.824e-08 | 2.824e-08 | 1.28e-07 | 6 | 9e-07 | n/a | 1.045 | n/a | n/a | n/a | 3 | 3 | PASS |
| `ss_125c_3v00__case4` | ss_125c_3v00 | 4 | ok | 8386 | n/a | n/a | 3 | 1.148e-08 | 1 | n/a | n/a | 8.386e-06 | 8.386e-06 | 1 | 0 | 9e-05 | n/a | 0.6215 | n/a | n/a | n/a | 3 | 3 | PASS |
| `ss_125c_3v00__case5` | ss_125c_3v00 | 5 | ok | 91.85 | 0.1208 | n/a | 3 | 1.392e-08 | 1 | n/a | n/a | 9.185e-08 | 9.185e-08 | 1.8e-07 | 6 | n/a | 4.667e-06 | n/a | n/a | n/a | n/a | 3 | 3 | PASS |
| `ss_125c_3v00__case6` | ss_125c_3v00 | 6 | ok | 74 | n/a | n/a | 1.148e-08 | 1.148e-08 | 1 | n/a | n/a | 7.4e-08 | 1 | 7.4e-08 | 6 | n/a | n/a | n/a | 0.6961 | 0.7201 | n/a | 0.1972 | 0.1972 | PASS |
| `ss_125c_3v00__case7` | ss_125c_3v00 | 7 | ok | 1e+09 | n/a | n/a | 1.146e-08 | 1.146e-08 | 1 | n/a | n/a | 1 | 1 | 1 | 0 | n/a | n/a | n/a | 0.337 | 0 | n/a | 0.08307 | 0.08307 | PASS |
| `tt_27c_3v30__case0` | tt_27c_3v30 | 0 | ok | 1e+09 | n/a | n/a | 4.317e-09 | 4.318e-09 | 1 | n/a | 5.146e-08 | 7e-09 | 1 | 1 | 0 | n/a | n/a | n/a | 0.8596 | 0.9256 | n/a | 0.2764 | 1.186e-06 | PASS |
| `tt_27c_3v30__case1` | tt_27c_3v30 | 1 | ok | 1e+09 | n/a | 1 | 1.9 | 3.245e-09 | 1 | n/a | n/a | 1.1e-08 | 1 | 1 | 0 | n/a | n/a | n/a | 0.8749 | 0.9129 | 1.993 | 0.2696 | 2.847e-07 | PASS |
| `tt_27c_3v30__case2` | tt_27c_3v30 | 2 | ok | 41.46 | n/a | n/a | 4.65e-08 | 4.402e-09 | 1 | 1 | n/a | 7e-09 | 4.146e-08 | 1 | 0 | n/a | 1.83e-08 | n/a | n/a | n/a | n/a | 3.417 | 3.417 | PASS |
| `tt_27c_3v30__case3` | tt_27c_3v30 | 3 | ok | 49.45 | n/a | n/a | 3.3 | 4.383e-09 | 1 | n/a | n/a | 4.945e-08 | 4.945e-08 | 1.28e-07 | 6 | 9e-07 | n/a | 1.029 | n/a | n/a | n/a | 3.3 | 3.3 | PASS |
| `tt_27c_3v30__case4` | tt_27c_3v30 | 4 | ok | 4360 | n/a | n/a | 3.3 | 4.314e-09 | 1 | n/a | n/a | 4.36e-06 | 6.471e-06 | 4.36e-06 | 6 | 9e-05 | n/a | 0.6752 | n/a | n/a | n/a | 3.3 | 3.3 | PASS |
| `tt_27c_3v30__case5` | tt_27c_3v30 | 5 | ok | 69.62 | 0.1654 | n/a | 3.3 | 8.95e-10 | 1 | n/a | n/a | 6.962e-08 | 6.962e-08 | 5.8e-07 | 6 | n/a | 5.879e-06 | n/a | n/a | n/a | n/a | 3.3 | 3.3 | PASS |
| `tt_27c_3v30__case6` | tt_27c_3v30 | 6 | ok | 73 | n/a | n/a | 4.313e-09 | 4.314e-09 | 1 | n/a | n/a | 7.3e-08 | 1 | 7.3e-08 | 6 | n/a | n/a | n/a | 0.7228 | 0.7393 | n/a | 0.2235 | 0.2235 | PASS |
| `tt_27c_3v30__case7` | tt_27c_3v30 | 7 | ok | 860 | n/a | n/a | 4.308e-09 | 4.309e-09 | 1 | n/a | n/a | 8.6e-07 | 1 | 8.6e-07 | 6 | n/a | n/a | n/a | 0.4809 | 0.5278 | n/a | 0.1361 | 0.1361 | PASS |
