# tb6_cm_supply

**Overall: PASS**

TB6: PRBS7 on lane 0 (100 Mb/s, VID 100 mV) with (0) a common-mode step 0.05 <-> 2.35 V in 2 ns, (1) 100 mVpp 25 MHz supply ripple, (2) 25 MHz 20 mA current-spike train on the local rails behind 1 ohm + 2 nH per rail, (3) nothing; disturbed copy vs a quiet reference copy of the macro

Runs: **20** (ok 20); 0 reused from cache.

## Worst case per metric

| metric | limit | worst run | value | margin | verdict |
|---|---|---|---|---|---|
| false_toggles | - .. 0 | `ff_m40c_3v60__case0` | **0** | 0 | PASS |
| added_jitter_ui (% UI) | - .. 10 | `ff_m40c_3v60__case2` | **1.085** | 8.915 | PASS |

## All runs

| run | corner | case | status | false_toggles | added_jitter_ui (% UI) | added_jitter_all_ui | delta_max_ps | dev_step0_up_ps | dev_step1_dn_ps | dev_step2_up_ps | dev_step3_dn_ps | dev_step4_up_ps | dev_step5_dn_ps | dev_step6_up_ps | dev_step7_dn_ps | hit_dev_max_ps | n_clear_edges | n_in | n_out_d | n_out_r | rail_dev_v | unmatched | vrail_pp_v | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `tt_27c_3v30__case0` | tt_27c_3v30 | 0 | ok | 0 | 0.09883 | 0.166 | 1044 | 274.6 | 490.1 | 413.8 | 1050 | 321.2 | 1246 | 800.6 | 535.7 | 1246 | 33 | 42 | 42 | 42 | 0.03555 | 0 | 0.03219 | PASS |
| `tt_27c_3v30__case1` | tt_27c_3v30 | 1 | ok | 0 | 0.7105 | 0.007105 | 38.5 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.0528 | 0 | 0.1103 | PASS |
| `tt_27c_3v30__case2` | tt_27c_3v30 | 2 | ok | 0 | 0.5886 | 0.005886 | 52 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.1001 | 0 | 0.3678 | PASS |
| `tt_27c_3v30__case3` | tt_27c_3v30 | 3 | ok | 0 | 0.01953 | 0.0001953 | 3.522 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.003758 | 0 | 0.01877 | PASS |
| `ss_125c_3v00__case0` | ss_125c_3v00 | 0 | ok | 0 | 0.2985 | 0.2466 | 1264 | 405.5 | 719.9 | 798.2 | 1089 | 282.2 | 1454 | 190 | 1668 | 1668 | 33 | 42 | 42 | 42 | 0.03447 | 0 | 0.0278 | PASS |
| `ss_125c_3v00__case1` | ss_125c_3v00 | 1 | ok | 0 | 1.051 | 0.01051 | 56.31 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.05204 | 0 | 0.1104 | PASS |
| `ss_125c_3v00__case2` | ss_125c_3v00 | 2 | ok | 0 | 0.1785 | 0.001785 | 10.47 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.09091 | 0 | 0.3341 | PASS |
| `ss_125c_3v00__case3` | ss_125c_3v00 | 3 | ok | 0 | 0.0128 | 0.000128 | 3.047 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.003677 | 0 | 0.01458 | PASS |
| `ff_m40c_3v60__case0` | ff_m40c_3v60 | 0 | ok | **0** (worst) | 0.2214 | 0.1255 | 1020 | 234.2 | 298.2 | 126.2 | 754.3 | 747.2 | 138 | 1021 | 253.4 | 1021 | 33 | 42 | 42 | 42 | 0.03446 | 0 | 0.03372 | PASS |
| `ff_m40c_3v60__case1` | ff_m40c_3v60 | 1 | ok | 0 | 0.4668 | 0.004668 | 26.22 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.05311 | 0 | 0.1096 | PASS |
| `ff_m40c_3v60__case2` | ff_m40c_3v60 | 2 | ok | 0 | **1.085** (worst) | 0.01085 | 86.33 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.1097 | 0 | 0.4047 | PASS |
| `ff_m40c_3v60__case3` | ff_m40c_3v60 | 3 | ok | 0 | 0.008344 | 8.344e-05 | 1.361 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.004414 | 0 | 0.0226 | PASS |
| `fs_27c_3v30__case0` | fs_27c_3v30 | 0 | ok | 0 | 0.1213 | 0.1567 | 908.9 | 261.4 | 504.9 | 424.4 | 941.2 | 321 | 1143 | 798.5 | 539.1 | 1143 | 33 | 42 | 42 | 42 | 0.0361 | 0 | 0.03284 | PASS |
| `fs_27c_3v30__case1` | fs_27c_3v30 | 1 | ok | 0 | 0.7401 | 0.007401 | 40.42 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.05286 | 0 | 0.1105 | PASS |
| `fs_27c_3v30__case2` | fs_27c_3v30 | 2 | ok | 0 | 0.4974 | 0.004974 | 43.18 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.1004 | 0 | 0.369 | PASS |
| `fs_27c_3v30__case3` | fs_27c_3v30 | 3 | ok | 0 | 0.01231 | 0.0001231 | 2.918 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.00377 | 0 | 0.01872 | PASS |
| `sf_27c_3v30__case0` | sf_27c_3v30 | 0 | ok | 0 | 0.1264 | 0.17 | 1120 | 255.5 | 514 | 402.6 | 1178 | 317.5 | 1297 | 800.3 | 532.6 | 1297 | 33 | 42 | 42 | 42 | 0.03553 | 0 | 0.03162 | PASS |
| `sf_27c_3v30__case1` | sf_27c_3v30 | 1 | ok | 0 | 0.7383 | 0.007383 | 42.06 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.05276 | 0 | 0.1104 | PASS |
| `sf_27c_3v30__case2` | sf_27c_3v30 | 2 | ok | 0 | 0.6618 | 0.006618 | 59.01 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.09984 | 0 | 0.3667 | PASS |
| `sf_27c_3v30__case3` | sf_27c_3v30 | 3 | ok | 0 | 0.01499 | 0.0001499 | 3.46 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.003771 | 0 | 0.019 | PASS |
