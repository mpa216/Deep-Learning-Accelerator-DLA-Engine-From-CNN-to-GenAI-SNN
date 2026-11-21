# tb10_lanes

**Overall: PASS**

TB10: lvds_rx_x3 with CLK (1010), D0 (PRBS7), D1 (PRBS7 shifted) at 100 Mb/s, VID 100 mV, full input network per lane; mc3s = 0: nominal lane skew and crosstalk jitter (lane k active alone as reference); mc3s = 1: additionally 4 mismatch copies (12 lane samples) for the 3-sigma lane-to-lane delay spread

Runs: **10** (ok 10); 0 reused from cache.

## Worst case per metric

| metric | limit | worst run | value | margin | verdict |
|---|---|---|---|---|---|
| xtalk_jitter_ui (% UI) | - .. 5 | `sf_27c_3v30__mc3s0` | **0.1296** | 4.87 | PASS |

## All runs

| run | corner | mc3s | status | xtalk_jitter_ui (% UI) | delay_lane0_ps | delay_lane1_ps | delay_lane2_ps | mc_range_ps | n_missed_a0 | n_missed_a1 | n_missed_a2 | sigma_lane_delay_ps | skew_3sigma_s | skew_3sigma_ucl_s | skew_s | xtalk_lane0_ui | xtalk_lane1_ui | xtalk_lane2_ui | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `tt_27c_3v30__mc3s0` | tt_27c_3v30 | 0 | ok | 0.1188 | 3502 | 3475 | 3490 | n/a | 0 | 0 | 0 | n/a | n/a | n/a | 2.7e-11 | 0.001188 | 0.00063 | 0.0007725 | PASS |
| `tt_27c_3v30__mc3s1` | tt_27c_3v30 | 1 | ok | 0.1191 | 3501 | 3474 | 3489 | 147.1 | 0 | 0 | 0 | 40.33 | 1.711e-10 | 2.815e-10 | 2.717e-11 | 0.001191 | 0.0005964 | 0.0005874 | PASS |
| `ss_125c_3v00__mc3s0` | ss_125c_3v00 | 0 | ok | 0.1101 | 4954 | 4955 | 4956 | n/a | 0 | 0 | 0 | n/a | n/a | n/a | 1.998e-12 | 0.001101 | 0.0005609 | 0.0005294 | PASS |
| `ss_125c_3v00__mc3s1` | ss_125c_3v00 | 1 | ok | 0.1044 | 4954 | 4955 | 4954 | 88.9 | 0 | 0 | 0 | 25.11 | 1.065e-10 | 1.753e-10 | 1.027e-13 | 0.001044 | 0.0005754 | 0.0005214 | PASS |
| `ff_m40c_3v60__mc3s0` | ff_m40c_3v60 | 0 | ok | 0.03212 | 2524 | 2523 | 2524 | n/a | 0 | 0 | 0 | n/a | n/a | n/a | 1.227e-12 | 0.0003212 | 0.000265 | 0.0003097 | PASS |
| `ff_m40c_3v60__mc3s1` | ff_m40c_3v60 | 1 | ok | 0.02916 | 2524 | 2522 | 2523 | 111.3 | 0 | 0 | 0 | 30.42 | 1.29e-10 | 2.123e-10 | 2.065e-12 | 0.0002622 | 0.0002468 | 0.0002916 | PASS |
| `fs_27c_3v30__mc3s0` | fs_27c_3v30 | 0 | ok | 0.1047 | 3525 | 3478 | 3502 | n/a | 0 | 0 | 0 | n/a | n/a | n/a | 4.64e-11 | 0.001047 | 0.0007259 | 0.0006371 | PASS |
| `fs_27c_3v30__mc3s1` | fs_27c_3v30 | 1 | ok | 0.09799 | 3524 | 3476 | 3501 | 154.5 | 0 | 0 | 0 | 42.39 | 1.799e-10 | 2.959e-10 | 4.794e-11 | 0.0009799 | 0.0006394 | 0.0005398 | PASS |
| `sf_27c_3v30__mc3s0` | sf_27c_3v30 | 0 | ok | **0.1296** (worst) | 3482 | 3480 | 3482 | n/a | 0 | 0 | 0 | n/a | n/a | n/a | 2.066e-12 | 0.001296 | 0.0008637 | 0.0009479 | PASS |
| `sf_27c_3v30__mc3s1` | sf_27c_3v30 | 1 | ok | 0.1277 | 3481 | 3477 | 3480 | 141.9 | 0 | 0 | 0 | 39.36 | 1.67e-10 | 2.748e-10 | 4.264e-12 | 0.001277 | 0.0006679 | 0.0007806 | PASS |
