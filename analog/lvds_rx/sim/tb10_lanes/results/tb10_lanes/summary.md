# tb10_lanes

**Overall: PASS**

TB10: lvds_rx_x3 with CLK (1010), D0 (PRBS7), D1 (PRBS7 shifted) at 100 Mb/s, VID 100 mV, full input network per lane; mc3s = 0: nominal lane skew and crosstalk jitter (lane k active alone as reference); mc3s = 1: additionally 4 mismatch copies (12 lane samples) for the 3-sigma lane-to-lane delay spread

Runs: **10** (ok 10); 0 reused from cache.

## Worst case per metric

| metric | limit | worst run | value | margin | verdict |
|---|---|---|---|---|---|
| xtalk_jitter_ui (% UI) | - .. 5 | `sf_27c_3v30__mc3s0` | **0.09015** | 4.91 | PASS |

## All runs

| run | corner | mc3s | status | xtalk_jitter_ui (% UI) | delay_lane0_ps | delay_lane1_ps | delay_lane2_ps | mc_range_ps | n_missed_a0 | n_missed_a1 | n_missed_a2 | sigma_lane_delay_ps | skew_3sigma_s | skew_3sigma_ucl_s | skew_s | xtalk_lane0_ui | xtalk_lane1_ui | xtalk_lane2_ui | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `tt_27c_3v30__mc3s0` | tt_27c_3v30 | 0 | ok | 0.06263 | 3659 | 3641 | 3652 | n/a | 0 | 0 | 0 | n/a | n/a | n/a | 1.742e-11 | 0.0006263 | 0.0004551 | 0.0005278 | PASS |
| `tt_27c_3v30__mc3s1` | tt_27c_3v30 | 1 | ok | 0.06178 | 3659 | 3639 | 3649 | 176.1 | 0 | 0 | 0 | 47.74 | 2.026e-10 | 3.333e-10 | 2.028e-11 | 0.0006178 | 0.0004125 | 0.0005074 | PASS |
| `ss_125c_3v00__mc3s0` | ss_125c_3v00 | 0 | ok | 0.0409 | 5276 | 5275 | 5274 | n/a | 0 | 0 | 0 | n/a | n/a | n/a | 1.967e-12 | 0.000409 | 0.0002307 | 0.0002838 | PASS |
| `ss_125c_3v00__mc3s1` | ss_125c_3v00 | 1 | ok | 0.04598 | 5273 | 5272 | 5272 | 125.2 | 0 | 0 | 0 | 34.27 | 1.454e-10 | 2.392e-10 | 1.638e-12 | 0.0004598 | 0.0002871 | 0.0003147 | PASS |
| `ff_m40c_3v60__mc3s0` | ff_m40c_3v60 | 0 | ok | 0.03932 | 2590 | 2592 | 2591 | n/a | 0 | 0 | 0 | n/a | n/a | n/a | 1.201e-12 | 0.0003932 | 0.0002739 | 0.0003075 | PASS |
| `ff_m40c_3v60__mc3s1` | ff_m40c_3v60 | 1 | ok | 0.03829 | 2586 | 2588 | 2588 | 122.8 | 0 | 0 | 0 | 33.04 | 1.402e-10 | 2.306e-10 | 2.432e-12 | 0.0003829 | 0.0002583 | 0.0002618 | PASS |
| `fs_27c_3v30__mc3s0` | fs_27c_3v30 | 0 | ok | 0.06796 | 3711 | 3663 | 3687 | n/a | 0 | 0 | 0 | n/a | n/a | n/a | 4.745e-11 | 0.0006796 | 0.0004077 | 0.0004416 | PASS |
| `fs_27c_3v30__mc3s1` | fs_27c_3v30 | 1 | ok | 0.07469 | 3707 | 3664 | 3687 | 185.7 | 0 | 0 | 0 | 50.27 | 2.133e-10 | 3.509e-10 | 4.324e-11 | 0.0007469 | 0.0004164 | 0.0003589 | PASS |
| `sf_27c_3v30__mc3s0` | sf_27c_3v30 | 0 | ok | **0.09015** (worst) | 3618 | 3618 | 3617 | n/a | 0 | 0 | 0 | n/a | n/a | n/a | 1.214e-12 | 0.0009015 | 0.0005687 | 0.0006436 | PASS |
| `sf_27c_3v30__mc3s1` | sf_27c_3v30 | 1 | ok | 0.08581 | 3616 | 3616 | 3615 | 165.7 | 0 | 0 | 0 | 44.86 | 1.903e-10 | 3.131e-10 | 7.914e-13 | 0.0008581 | 0.0005232 | 0.0004951 | PASS |
