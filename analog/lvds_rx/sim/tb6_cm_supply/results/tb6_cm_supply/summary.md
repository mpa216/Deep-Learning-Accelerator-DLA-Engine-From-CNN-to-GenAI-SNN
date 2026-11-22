# tb6_cm_supply

**Overall: PASS**

TB6: PRBS7 on lane 0 (100 Mb/s, VID 100 mV) with (0) a common-mode step 0.05 <-> 2.35 V in 2 ns, (1) 100 mVpp 25 MHz supply ripple, (2) 25 MHz 20 mA current-spike train on the local rails behind 1 ohm + 2 nH per rail, (3) nothing; disturbed copy vs a quiet reference copy of the macro

Runs: **20** (ok 20); 20 reused from cache.

## Worst case per metric

| metric | limit | worst run | value | margin | verdict |
|---|---|---|---|---|---|
| false_toggles | - .. 0 | `ff_m40c_3v60__case0` | **0** | 0 | PASS |
| added_jitter_ui (% UI) | - .. 10 | `ff_m40c_3v60__case2` | **1.174** | 8.826 | PASS |

## All runs

| run | corner | case | status | false_toggles | added_jitter_ui (% UI) | added_jitter_all_ui | delta_max_ps | dev_step0_up_ps | dev_step1_dn_ps | dev_step2_up_ps | dev_step3_dn_ps | dev_step4_up_ps | dev_step5_dn_ps | dev_step6_up_ps | dev_step7_dn_ps | hit_dev_max_ps | n_clear_edges | n_in | n_out_d | n_out_r | rail_dev_v | unmatched | vrail_pp_v | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `tt_27c_3v30__case0` | tt_27c_3v30 | 0 | ok | 0 | 0.35 | 0.5341 | 4371 | 402.5 | 2686 | 667 | 3619 | 91.27 | 4674 | 730.1 | 817.9 | 4674 | 33 | 42 | 42 | 42 | 3.337 | 0 | 0.03857 | PASS |
| `tt_27c_3v30__case1` | tt_27c_3v30 | 1 | ok | 0 | 0.5827 | 0.005827 | 32.31 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.05379 | 0 | 0.1147 | PASS |
| `tt_27c_3v30__case2` | tt_27c_3v30 | 2 | ok | 0 | 0.7229 | 0.007229 | 67.93 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.09716 | 0 | 0.3574 | PASS |
| `tt_27c_3v30__case3` | tt_27c_3v30 | 3 | ok | 0 | 0.02174 | 0.0002174 | 4.159 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.005099 | 0 | 0.02626 | PASS |
| `ss_125c_3v00__case0` | ss_125c_3v00 | 0 | ok | 0 | 1.069 | 0.6372 | 4697 | 557 | 3208 | 1140 | 4187 | 581.7 | 5232 | 50.91 | 0.6362 | 5232 | 33 | 42 | 42 | 42 | 3.047 | 2 | 0.03242 | PASS |
| `ss_125c_3v00__case1` | ss_125c_3v00 | 1 | ok | 0 | 0.8604 | 0.008604 | 47.21 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.05234 | 0 | 0.1124 | PASS |
| `ss_125c_3v00__case2` | ss_125c_3v00 | 2 | ok | 0 | 0.4335 | 0.004335 | 46.48 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.08898 | 0 | 0.3266 | PASS |
| `ss_125c_3v00__case3` | ss_125c_3v00 | 3 | ok | 0 | 0.02148 | 0.0002148 | 4.6 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.004627 | 0 | 0.01759 | PASS |
| `ff_m40c_3v60__case0` | ff_m40c_3v60 | 0 | ok | **0** (worst) | 0.1871 | 0.4265 | 3728 | 340.8 | 1966 | 326.5 | 2878 | 535.7 | 3924 | 823.4 | 290.9 | 3924 | 33 | 42 | 42 | 42 | 0.03809 | 0 | 0.04169 | PASS |
| `ff_m40c_3v60__case1` | ff_m40c_3v60 | 1 | ok | 0 | 0.3873 | 0.003873 | 22.04 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.05388 | 0 | 0.1149 | PASS |
| `ff_m40c_3v60__case2` | ff_m40c_3v60 | 2 | ok | 0 | **1.174** (worst) | 0.01174 | 102.4 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.1079 | 0 | 0.3978 | PASS |
| `ff_m40c_3v60__case3` | ff_m40c_3v60 | 3 | ok | 0 | 0.02189 | 0.0002189 | 2.637 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.005896 | 0 | 0.02986 | PASS |
| `fs_27c_3v30__case0` | fs_27c_3v30 | 0 | ok | 0 | 0.7301 | 0.5218 | 4237 | 417.5 | 2563 | 663.4 | 3503 | 105.8 | 4555 | 731.9 | 815.4 | 4555 | 33 | 42 | 42 | 42 | 3.333 | 0 | 0.03822 | PASS |
| `fs_27c_3v30__case1` | fs_27c_3v30 | 1 | ok | 0 | 0.5734 | 0.005734 | 33.22 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.05386 | 0 | 0.1149 | PASS |
| `fs_27c_3v30__case2` | fs_27c_3v30 | 2 | ok | 0 | 0.749 | 0.00749 | 70.07 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.09714 | 0 | 0.3574 | PASS |
| `fs_27c_3v30__case3` | fs_27c_3v30 | 3 | ok | 0 | 0.02792 | 0.0002792 | 4.796 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.005179 | 0 | 0.02673 | PASS |
| `sf_27c_3v30__case0` | sf_27c_3v30 | 0 | ok | 0 | 0.4467 | 0.549 | 4524 | 389.4 | 2835 | 671.5 | 3770 | 76.69 | 4818 | 715.3 | 810.5 | 4818 | 33 | 42 | 42 | 42 | 3.336 | 0 | 0.03912 | PASS |
| `sf_27c_3v30__case1` | sf_27c_3v30 | 1 | ok | 0 | 0.5518 | 0.005518 | 31.53 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.05373 | 0 | 0.1146 | PASS |
| `sf_27c_3v30__case2` | sf_27c_3v30 | 2 | ok | 0 | 0.7581 | 0.007581 | 72.16 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.09718 | 0 | 0.3574 | PASS |
| `sf_27c_3v30__case3` | sf_27c_3v30 | 3 | ok | 0 | 0.02378 | 0.0002378 | 4.493 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.005081 | 0 | 0.02582 | PASS |
