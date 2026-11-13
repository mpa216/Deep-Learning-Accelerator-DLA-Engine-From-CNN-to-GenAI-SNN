# tb6_cm_supply

**Overall: PASS**

TB6: PRBS7 on lane 0 (100 Mb/s, VID 100 mV) with (0) a common-mode step 0.05 <-> 2.35 V in 2 ns, (1) 100 mVpp 25 MHz supply ripple, (2) 25 MHz 20 mA current-spike train on the local rails behind 1 ohm + 2 nH per rail, (3) nothing; disturbed copy vs a quiet reference copy of the macro

Runs: **20** (ok 20); 0 reused from cache.

## Worst case per metric

| metric | limit | worst run | value | margin | verdict |
|---|---|---|---|---|---|
| false_toggles | - .. 0 | `ff_m40c_3v60__case0` | **0** | 0 | PASS |
| added_jitter_ui (% UI) | - .. 10 | `ff_m40c_3v60__case2` | **1.186** | 8.814 | PASS |

## All runs

| run | corner | case | status | false_toggles | added_jitter_ui (% UI) | added_jitter_all_ui | delta_max_ps | dev_step0_up_ps | dev_step1_dn_ps | dev_step2_up_ps | dev_step3_dn_ps | dev_step4_up_ps | dev_step5_dn_ps | dev_step6_up_ps | dev_step7_dn_ps | hit_dev_max_ps | n_clear_edges | n_in | n_out_d | n_out_r | rail_dev_v | unmatched | vrail_pp_v | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `tt_27c_3v30__case0` | tt_27c_3v30 | 0 | ok | 0 | 0.123 | 0.1676 | 1046 | 277.2 | 515.9 | 420.4 | 1082 | 324.3 | 1255 | 795.2 | 525.9 | 1255 | 33 | 42 | 42 | 42 | 0.03546 | 0 | 0.03214 | PASS |
| `tt_27c_3v30__case1` | tt_27c_3v30 | 1 | ok | 0 | 0.7247 | 0.007247 | 41.51 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.05277 | 0 | 0.1103 | PASS |
| `tt_27c_3v30__case2` | tt_27c_3v30 | 2 | ok | 0 | 0.622 | 0.00622 | 56.37 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.09984 | 0 | 0.3667 | PASS |
| `tt_27c_3v30__case3` | tt_27c_3v30 | 3 | ok | 0 | 0.02183 | 0.0002183 | 3.725 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.003777 | 0 | 0.0188 | PASS |
| `ss_125c_3v00__case0` | ss_125c_3v00 | 0 | ok | 0 | 0.2991 | 0.2532 | 1305 | 422.2 | 746 | 812.8 | 1129 | 287.2 | 1484 | 192.5 | 1719 | 1719 | 33 | 42 | 42 | 42 | 0.03443 | 0 | 0.02748 | PASS |
| `ss_125c_3v00__case1` | ss_125c_3v00 | 1 | ok | 0 | 1.02 | 0.0102 | 53.92 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.05197 | 0 | 0.1103 | PASS |
| `ss_125c_3v00__case2` | ss_125c_3v00 | 2 | ok | 0 | 0.1623 | 0.001623 | 8.832 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.09088 | 0 | 0.3339 | PASS |
| `ss_125c_3v00__case3` | ss_125c_3v00 | 3 | ok | 0 | 0.02462 | 0.0002462 | 4.328 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.003671 | 0 | 0.0146 | PASS |
| `ff_m40c_3v60__case0` | ff_m40c_3v60 | 0 | ok | **0** (worst) | 0.2986 | 0.1242 | 1011 | 230 | 317.1 | 118.5 | 776.4 | 756.1 | 131.8 | 1012 | 260.6 | 1012 | 33 | 42 | 42 | 42 | 0.03434 | 0 | 0.03381 | PASS |
| `ff_m40c_3v60__case1` | ff_m40c_3v60 | 1 | ok | 0 | 0.4465 | 0.004465 | 23.12 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.05313 | 0 | 0.1097 | PASS |
| `ff_m40c_3v60__case2` | ff_m40c_3v60 | 2 | ok | 0 | **1.186** (worst) | 0.01186 | 91.72 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.1096 | 0 | 0.4043 | PASS |
| `ff_m40c_3v60__case3` | ff_m40c_3v60 | 3 | ok | 0 | 0.01495 | 0.0001495 | 2.063 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.004345 | 0 | 0.02223 | PASS |
| `fs_27c_3v30__case0` | fs_27c_3v30 | 0 | ok | 0 | 0.0794 | 0.159 | 915.9 | 296.5 | 535.1 | 435 | 972 | 322.6 | 1155 | 793.3 | 532.5 | 1155 | 33 | 42 | 42 | 42 | 0.036 | 0 | 0.03251 | PASS |
| `fs_27c_3v30__case1` | fs_27c_3v30 | 1 | ok | 0 | 0.6985 | 0.006985 | 38.19 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.05282 | 0 | 0.1103 | PASS |
| `fs_27c_3v30__case2` | fs_27c_3v30 | 2 | ok | 0 | 0.5416 | 0.005416 | 47.56 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.1001 | 0 | 0.3679 | PASS |
| `fs_27c_3v30__case3` | fs_27c_3v30 | 3 | ok | 0 | 0.0161 | 0.000161 | 3.346 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.003783 | 0 | 0.01864 | PASS |
| `sf_27c_3v30__case0` | sf_27c_3v30 | 0 | ok | 0 | 0.1043 | 0.1701 | 1111 | 252.2 | 543.9 | 407.2 | 1213 | 327.5 | 1294 | 795.6 | 519.2 | 1294 | 33 | 42 | 42 | 42 | 0.03545 | 0 | 0.03163 | PASS |
| `sf_27c_3v30__case1` | sf_27c_3v30 | 1 | ok | 0 | 0.7034 | 0.007034 | 37.85 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.05274 | 0 | 0.1104 | PASS |
| `sf_27c_3v30__case2` | sf_27c_3v30 | 2 | ok | 0 | 0.705 | 0.00705 | 64.34 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.09954 | 0 | 0.3656 | PASS |
| `sf_27c_3v30__case3` | sf_27c_3v30 | 3 | ok | 0 | 0.02073 | 0.0002073 | 4.019 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.003779 | 0 | 0.01903 | PASS |
