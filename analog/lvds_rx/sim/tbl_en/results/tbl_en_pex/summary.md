# tbl_en_pex

**Overall: PASS**

post-layout gate TBL (pex): tb8_en with core = sim/tbl/core_pexrc.spice

Runs: **18** (ok 18); 0 reused from cache.

## Worst case per metric

| metric | limit | worst run | value | margin | verdict |
|---|---|---|---|---|---|
| min_pulse_s (ns) | 2 .. - | `ff_125c_3v60__case3` | **13** | 11 | PASS |

## All runs

| run | corner | case | status | min_pulse_s (ns) | early_high_v | en1_valid_ok | end_a_v | end_b_v | final_ok | high_phase_ok | idd_en0_a | min_pulse_all_s | min_pulse_cross_s | min_runt_width_s | n_runt | t_high_s | valid_time_s | vdd_at_out_rise_v | vout_en1_v | vout_off_v | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `ff_125c_3v60__case0` | ff_125c_3v60 | 0 | ok | 1e+09 | n/a | n/a | 7.399e-07 | 7.399e-07 | 1 | n/a | 1.225e-07 | 3e-09 | 1 | 1 | 0 | n/a | n/a | n/a | n/a | 0.1718 | PASS |
| `ff_125c_3v60__case1` | ff_125c_3v60 | 1 | ok | 1e+09 | n/a | 1 | 1.9 | 5.929e-07 | 1 | n/a | n/a | 4e-09 | 1 | 1 | 0 | n/a | n/a | n/a | 1.916 | 0.1556 | PASS |
| `ff_125c_3v60__case2` | ff_125c_3v60 | 2 | ok | 18.64 | n/a | n/a | 7.839e-07 | 7.4e-07 | 1 | 1 | n/a | 3e-09 | 1.864e-08 | 1 | 0 | n/a | 1.673e-08 | n/a | n/a | 3.729 | PASS |
| `ff_125c_3v60__case3` | ff_125c_3v60 | 3 | ok | **13** (worst) | n/a | n/a | 3.6 | 7.398e-07 | 1 | n/a | n/a | 1.3e-08 | 3.498e-08 | 1.3e-08 | 6 | 9e-07 | n/a | 0.791 | n/a | 3.6 | PASS |
| `ff_125c_3v60__case4` | ff_125c_3v60 | 4 | ok | 4801 | n/a | n/a | 3.6 | 7.399e-07 | 1 | n/a | n/a | 4.801e-06 | 4.801e-06 | 1 | 0 | 9e-05 | n/a | 0.5001 | n/a | 3.6 | PASS |
| `ff_125c_3v60__case5` | ff_125c_3v60 | 5 | ok | 37.74 | 0.04467 | n/a | 3.6 | 7.413e-07 | 1 | n/a | n/a | 3.774e-08 | 3.774e-08 | 1 | 0 | n/a | 6.887e-06 | n/a | n/a | 3.601 | PASS |
| `ss_125c_3v00__case0` | ss_125c_3v00 | 0 | ok | 1e+09 | n/a | n/a | 1.147e-08 | 1.147e-08 | 1 | n/a | 4.836e-08 | 8e-09 | 1 | 1 | 0 | n/a | n/a | n/a | n/a | 0.2793 | PASS |
| `ss_125c_3v00__case1` | ss_125c_3v00 | 1 | ok | 1e+09 | n/a | 1 | 1.9 | 1.139e-08 | 1 | n/a | n/a | 1.1e-08 | 1 | 1 | 0 | n/a | n/a | n/a | 1.989 | 0.2666 | PASS |
| `ss_125c_3v00__case2` | ss_125c_3v00 | 2 | ok | 51.06 | n/a | n/a | 5.958e-07 | 1.149e-08 | 1 | 1 | n/a | 8e-09 | 5.106e-08 | 1 | 0 | n/a | 3.325e-08 | n/a | n/a | 3.132 | PASS |
| `ss_125c_3v00__case3` | ss_125c_3v00 | 3 | ok | 43.43 | n/a | n/a | 3 | 1.144e-08 | 1 | n/a | n/a | 4.343e-08 | 4.343e-08 | 1.35e-07 | 6 | 9e-07 | n/a | 1.09 | n/a | 3 | PASS |
| `ss_125c_3v00__case4` | ss_125c_3v00 | 4 | ok | 280 | n/a | n/a | 3 | 1.148e-08 | 1 | n/a | n/a | 2.8e-07 | 1.13e-05 | 2.8e-07 | 6 | 9e-05 | n/a | 0.6313 | n/a | 3 | PASS |
| `ss_125c_3v00__case5` | ss_125c_3v00 | 5 | ok | 93.86 | 0.1208 | n/a | 3 | 1.793e-08 | 1 | n/a | n/a | 9.386e-08 | 9.386e-08 | 1.8e-07 | 6 | n/a | 4.666e-06 | n/a | n/a | 3.001 | PASS |
| `tt_27c_3v30__case0` | tt_27c_3v30 | 0 | ok | 1e+09 | n/a | n/a | 4.317e-09 | 4.318e-09 | 1 | n/a | 5.157e-08 | 7e-09 | 1 | 1 | 0 | n/a | n/a | n/a | n/a | 0.2764 | PASS |
| `tt_27c_3v30__case1` | tt_27c_3v30 | 1 | ok | 1e+09 | n/a | 1 | 1.9 | 3.245e-09 | 1 | n/a | n/a | 1.1e-08 | 1 | 1 | 0 | n/a | n/a | n/a | 1.993 | 0.2695 | PASS |
| `tt_27c_3v30__case2` | tt_27c_3v30 | 2 | ok | 38.42 | n/a | n/a | -2.306e-07 | 4.384e-09 | 1 | 1 | n/a | 7e-09 | 3.842e-08 | 1 | 0 | n/a | 2.514e-08 | n/a | n/a | 3.472 | PASS |
| `tt_27c_3v30__case3` | tt_27c_3v30 | 3 | ok | 73.32 | n/a | n/a | 3.3 | 4.268e-09 | 1 | n/a | n/a | 7.332e-08 | 7.332e-08 | 1.32e-07 | 6 | 9e-07 | n/a | 1.077 | n/a | 3.3 | PASS |
| `tt_27c_3v30__case4` | tt_27c_3v30 | 4 | ok | 4780 | n/a | n/a | 3.3 | 4.314e-09 | 1 | n/a | n/a | 4.78e-06 | 8.915e-06 | 4.78e-06 | 6 | 9e-05 | n/a | 0.6824 | n/a | 3.3 | PASS |
| `tt_27c_3v30__case5` | tt_27c_3v30 | 5 | ok | 72.9 | 0.1654 | n/a | 3.3 | 1.29e-08 | 1 | n/a | n/a | 7.29e-08 | 7.29e-08 | 6e-07 | 6 | n/a | 5.871e-06 | n/a | n/a | 3.3 | PASS |
