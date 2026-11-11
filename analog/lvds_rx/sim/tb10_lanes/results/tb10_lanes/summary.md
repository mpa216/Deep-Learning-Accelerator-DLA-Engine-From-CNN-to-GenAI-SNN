# tb10_lanes

**Overall: PASS**

TB10: lvds_rx_x3 with CLK (1010), D0 (PRBS7), D1 (PRBS7 shifted) at 100 Mb/s, VID 100 mV, full input network per lane; mc3s = 0: nominal lane skew and crosstalk jitter (lane k active alone as reference); mc3s = 1: additionally 4 mismatch copies (12 lane samples) for the 3-sigma lane-to-lane delay spread

Runs: **10** (ok 10); 10 reused from cache.

## Worst case per metric

| metric | limit | worst run | value | margin | verdict |
|---|---|---|---|---|---|
| xtalk_jitter_ui (% UI) | - .. 5 | `sf_27c_3v30__mc3s1` | **0.08148** | 4.919 | PASS |

## All runs

| run | corner | mc3s | status | xtalk_jitter_ui (% UI) | delay_lane0_ps | delay_lane1_ps | delay_lane2_ps | mc_range_ps | n_missed_a0 | n_missed_a1 | n_missed_a2 | sigma_lane_delay_ps | skew_3sigma_s | skew_3sigma_ucl_s | skew_s | xtalk_lane0_ui | xtalk_lane1_ui | xtalk_lane2_ui | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `tt_27c_3v30__mc3s0` | tt_27c_3v30 | 0 | ok | 0.07896 | 3700 | 3679 | 3690 | n/a | 0 | 0 | 0 | n/a | n/a | n/a | 2.058e-11 | 0.0007896 | 0.0004007 | 0.0005543 | PASS |
| `tt_27c_3v30__mc3s1` | tt_27c_3v30 | 1 | ok | 0.05823 | 3699 | 3679 | 3688 | 179.6 | 0 | 0 | 0 | 48.3 | 2.049e-10 | 3.372e-10 | 1.958e-11 | 0.0005823 | 0.0004274 | 0.0004729 | PASS |
| `ss_125c_3v00__mc3s0` | ss_125c_3v00 | 0 | ok | 0.03986 | 5313 | 5313 | 5312 | n/a | 0 | 0 | 0 | n/a | n/a | n/a | 1.387e-12 | 0.0003986 | 0.0002361 | 0.0002841 | PASS |
| `ss_125c_3v00__mc3s1` | ss_125c_3v00 | 1 | ok | 0.04444 | 5310 | 5308 | 5309 | 126.5 | 0 | 0 | 0 | 34.4 | 1.46e-10 | 2.401e-10 | 1.745e-12 | 0.0004444 | 0.000304 | 0.0002862 | PASS |
| `ff_m40c_3v60__mc3s0` | ff_m40c_3v60 | 0 | ok | 0.03584 | 2623 | 2624 | 2624 | n/a | 0 | 0 | 0 | n/a | n/a | n/a | 8.747e-13 | 0.0003584 | 0.0002573 | 0.0002652 | PASS |
| `ff_m40c_3v60__mc3s1` | ff_m40c_3v60 | 1 | ok | 0.03776 | 2619 | 2621 | 2620 | 125.4 | 0 | 0 | 0 | 33.56 | 1.424e-10 | 2.343e-10 | 1.986e-12 | 0.0003776 | 0.0002328 | 0.0002369 | PASS |
| `fs_27c_3v30__mc3s0` | fs_27c_3v30 | 0 | ok | 0.07025 | 3748 | 3704 | 3729 | n/a | 0 | 0 | 0 | n/a | n/a | n/a | 4.403e-11 | 0.0007025 | 0.0004246 | 0.0004416 | PASS |
| `fs_27c_3v30__mc3s1` | fs_27c_3v30 | 1 | ok | 0.06313 | 3747 | 3702 | 3725 | 187.9 | 0 | 0 | 0 | 50.78 | 2.155e-10 | 3.545e-10 | 4.468e-11 | 0.0006313 | 0.0003207 | 0.0003536 | PASS |
| `sf_27c_3v30__mc3s0` | sf_27c_3v30 | 0 | ok | 0.07935 | 3659 | 3659 | 3658 | n/a | 0 | 0 | 0 | n/a | n/a | n/a | 9.358e-13 | 0.0007935 | 0.0005578 | 0.0006566 | PASS |
| `sf_27c_3v30__mc3s1` | sf_27c_3v30 | 1 | ok | **0.08148** (worst) | 3656 | 3656 | 3656 | 170.7 | 0 | 0 | 0 | 45.96 | 1.95e-10 | 3.208e-10 | 2.704e-13 | 0.0008148 | 0.0005809 | 0.0005808 | PASS |
