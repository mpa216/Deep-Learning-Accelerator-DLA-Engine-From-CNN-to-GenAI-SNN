# tb10_lanes

**Overall: PASS**

TB10: lvds_rx_x3 with CLK (1010), D0 (PRBS7), D1 (PRBS7 shifted) at 100 Mb/s, VID 100 mV, full input network per lane; mc3s = 0: nominal lane skew and crosstalk jitter (lane k active alone as reference); mc3s = 1: additionally 4 mismatch copies (12 lane samples) for the 3-sigma lane-to-lane delay spread

Runs: **10** (ok 10); 0 reused from cache.

## Worst case per metric

| metric | limit | worst run | value | margin | verdict |
|---|---|---|---|---|---|
| xtalk_jitter_ui (% UI) | - .. 5 | `tt_27c_3v30__mc3s0` | **0.1273** | 4.873 | PASS |

## All runs

| run | corner | mc3s | status | xtalk_jitter_ui (% UI) | delay_lane0_ps | delay_lane1_ps | delay_lane2_ps | mc_range_ps | n_missed_a0 | n_missed_a1 | n_missed_a2 | sigma_lane_delay_ps | skew_3sigma_s | skew_3sigma_ucl_s | skew_s | xtalk_lane0_ui | xtalk_lane1_ui | xtalk_lane2_ui | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `tt_27c_3v30__mc3s0` | tt_27c_3v30 | 0 | ok | **0.1273** (worst) | 3711 | 3711 | 3711 | n/a | 0 | 0 | 0 | n/a | n/a | n/a | 4.326e-13 | 0.001273 | 0.0008767 | 0.0006774 | PASS |
| `tt_27c_3v30__mc3s1` | tt_27c_3v30 | 1 | ok | 0.1093 | 3709 | 3708 | 3710 | 166.1 | 0 | 0 | 0 | 48.19 | 2.044e-10 | 3.364e-10 | 2.28e-12 | 0.001093 | 0.0005948 | 0.0007278 | PASS |
| `ss_125c_3v00__mc3s0` | ss_125c_3v00 | 0 | ok | 0.1015 | 5283 | 5284 | 5283 | n/a | 0 | 0 | 0 | n/a | n/a | n/a | 1.376e-12 | 0.001015 | 0.0005604 | 0.0007184 | PASS |
| `ss_125c_3v00__mc3s1` | ss_125c_3v00 | 1 | ok | 0.09883 | 5282 | 5282 | 5282 | 90.52 | 0 | 0 | 0 | 27 | 1.145e-10 | 1.884e-10 | 8.509e-13 | 0.0009883 | 0.000572 | 0.0006803 | PASS |
| `ff_m40c_3v60__mc3s0` | ff_m40c_3v60 | 0 | ok | 0.02648 | 2673 | 2681 | 2680 | n/a | 0 | 0 | 0 | n/a | n/a | n/a | 7.924e-12 | 0.0002458 | 0.0001891 | 0.0002648 | PASS |
| `ff_m40c_3v60__mc3s1` | ff_m40c_3v60 | 1 | ok | 0.02388 | 2670 | 2680 | 2677 | 124.6 | 0 | 0 | 0 | 35.52 | 1.507e-10 | 2.479e-10 | 1.045e-11 | 0.0002382 | 0.0001914 | 0.0002388 | PASS |
| `fs_27c_3v30__mc3s0` | fs_27c_3v30 | 0 | ok | 0.1124 | 3746 | 3724 | 3736 | n/a | 0 | 0 | 0 | n/a | n/a | n/a | 2.165e-11 | 0.001124 | 0.0007166 | 0.0009176 | PASS |
| `fs_27c_3v30__mc3s1` | fs_27c_3v30 | 1 | ok | 0.1076 | 3744 | 3721 | 3734 | 175 | 0 | 0 | 0 | 50.3 | 2.134e-10 | 3.511e-10 | 2.335e-11 | 0.001076 | 0.0005564 | 0.0005978 | PASS |
| `sf_27c_3v30__mc3s0` | sf_27c_3v30 | 0 | ok | 0.127 | 3690 | 3694 | 3691 | n/a | 0 | 0 | 0 | n/a | n/a | n/a | 3.665e-12 | 0.00127 | 0.0008239 | 0.0007794 | PASS |
| `sf_27c_3v30__mc3s1` | sf_27c_3v30 | 1 | ok | 0.1127 | 3688 | 3692 | 3689 | 158.5 | 0 | 0 | 0 | 46.64 | 1.979e-10 | 3.256e-10 | 4.456e-12 | 0.001127 | 0.0005492 | 0.0006107 | PASS |
