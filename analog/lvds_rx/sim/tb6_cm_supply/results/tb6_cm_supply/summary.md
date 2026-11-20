# tb6_cm_supply

**Overall: PASS**

TB6: PRBS7 on lane 0 (100 Mb/s, VID 100 mV) with (0) a common-mode step 0.05 <-> 2.35 V in 2 ns, (1) 100 mVpp 25 MHz supply ripple, (2) 25 MHz 20 mA current-spike train on the local rails behind 1 ohm + 2 nH per rail, (3) nothing; disturbed copy vs a quiet reference copy of the macro

Runs: **20** (ok 20); 0 reused from cache.

## Worst case per metric

| metric | limit | worst run | value | margin | verdict |
|---|---|---|---|---|---|
| false_toggles | - .. 0 | `ff_m40c_3v60__case0` | **0** | 0 | PASS |
| added_jitter_ui (% UI) | - .. 10 | `ff_m40c_3v60__case2` | **1.365** | 8.635 | PASS |

## All runs

| run | corner | case | status | false_toggles | added_jitter_ui (% UI) | added_jitter_all_ui | delta_max_ps | dev_step0_up_ps | dev_step1_dn_ps | dev_step2_up_ps | dev_step3_dn_ps | dev_step4_up_ps | dev_step5_dn_ps | dev_step6_up_ps | dev_step7_dn_ps | hit_dev_max_ps | n_clear_edges | n_in | n_out_d | n_out_r | rail_dev_v | unmatched | vrail_pp_v | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `tt_27c_3v30__case0` | tt_27c_3v30 | 0 | ok | 0 | 0.3041 | 0.5285 | 4273 | 397.2 | 2590 | 707.7 | 3538 | 55.5 | 4577 | 561.1 | 2028 | 4577 | 33 | 42 | 42 | 42 | 3.321 | 0 | 0.03831 | PASS |
| `tt_27c_3v30__case1` | tt_27c_3v30 | 1 | ok | 0 | 0.5715 | 0.005715 | 33.96 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.05386 | 0 | 0.115 | PASS |
| `tt_27c_3v30__case2` | tt_27c_3v30 | 2 | ok | 0 | 0.4644 | 0.004644 | 41 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.09867 | 0 | 0.3615 | PASS |
| `tt_27c_3v30__case3` | tt_27c_3v30 | 3 | ok | 0 | 0.02232 | 0.0002232 | 3.621 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.005085 | 0 | 0.02548 | PASS |
| `ss_125c_3v00__case0` | ss_125c_3v00 | 0 | ok | 0 | 0.9461 | 0.6258 | 4543 | 566.2 | 3081 | 1166 | 4066 | 698.4 | 5092 | 182.9 | 0.05365 | 5092 | 33 | 42 | 42 | 42 | 3.049 | 2 | 0.03138 | PASS |
| `ss_125c_3v00__case1` | ss_125c_3v00 | 1 | ok | 0 | 0.8539 | 0.008539 | 46.67 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.05269 | 0 | 0.1125 | PASS |
| `ss_125c_3v00__case2` | ss_125c_3v00 | 2 | ok | 0 | 0.259 | 0.00259 | 29.59 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.08901 | 0 | 0.3266 | PASS |
| `ss_125c_3v00__case3` | ss_125c_3v00 | 3 | ok | 0 | 0.02432 | 0.0002432 | 4.88 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.004473 | 0 | 0.01731 | PASS |
| `ff_m40c_3v60__case0` | ff_m40c_3v60 | 0 | ok | **0** (worst) | 0.1892 | 0.426 | 3689 | 331 | 1920 | 380.3 | 2840 | 450.2 | 3880 | 952.9 | 408.1 | 3880 | 33 | 42 | 42 | 42 | 0.03795 | 0 | 0.04358 | PASS |
| `ff_m40c_3v60__case1` | ff_m40c_3v60 | 1 | ok | 0 | 0.3788 | 0.003788 | 21.01 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.05388 | 0 | 0.1142 | PASS |
| `ff_m40c_3v60__case2` | ff_m40c_3v60 | 2 | ok | 0 | **1.365** (worst) | 0.01365 | 110.5 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.1079 | 0 | 0.3979 | PASS |
| `ff_m40c_3v60__case3` | ff_m40c_3v60 | 3 | ok | 0 | 0.02719 | 0.0002719 | 3.425 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.005907 | 0 | 0.03006 | PASS |
| `fs_27c_3v30__case0` | fs_27c_3v30 | 0 | ok | 0 | 0.6021 | 0.5164 | 4117 | 417.5 | 2456 | 724.1 | 3410 | 37.29 | 4439 | 556.3 | 2319 | 4439 | 33 | 42 | 42 | 42 | 3.338 | 0 | 0.03821 | PASS |
| `fs_27c_3v30__case1` | fs_27c_3v30 | 1 | ok | 0 | 0.5793 | 0.005793 | 30.95 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.05393 | 0 | 0.1152 | PASS |
| `fs_27c_3v30__case2` | fs_27c_3v30 | 2 | ok | 0 | 0.4117 | 0.004117 | 38.07 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.09892 | 0 | 0.3625 | PASS |
| `fs_27c_3v30__case3` | fs_27c_3v30 | 3 | ok | 0 | 0.01132 | 0.0001132 | 2.724 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.0051 | 0 | 0.0254 | PASS |
| `sf_27c_3v30__case0` | sf_27c_3v30 | 0 | ok | 0 | 0.4035 | 0.5433 | 4451 | 380.4 | 2748 | 696.3 | 3696 | 58.18 | 4737 | 562.2 | 1766 | 4737 | 33 | 42 | 42 | 42 | 3.338 | 0 | 0.03829 | PASS |
| `sf_27c_3v30__case1` | sf_27c_3v30 | 1 | ok | 0 | 0.5695 | 0.005695 | 31.36 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.05378 | 0 | 0.1149 | PASS |
| `sf_27c_3v30__case2` | sf_27c_3v30 | 2 | ok | 0 | 0.4764 | 0.004764 | 44.56 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.09837 | 0 | 0.3611 | PASS |
| `sf_27c_3v30__case3` | sf_27c_3v30 | 3 | ok | 0 | 0.0298 | 0.000298 | 4.574 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 42 | 42 | 42 | 0.005074 | 0 | 0.02554 | PASS |
