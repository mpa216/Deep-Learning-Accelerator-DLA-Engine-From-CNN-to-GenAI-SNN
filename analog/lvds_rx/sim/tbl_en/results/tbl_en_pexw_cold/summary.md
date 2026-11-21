# tbl_en_pexw_cold

**Overall: PASS**

T11 iteration 2, evidence for gate TBL's TB8 checks: tb8_en on the extracted macro (core = sim/tbl/core_pexrc.spice) at the -40 C spec-rate ramps (cases 3 / 5: pre-layout EN = 0 ramp peak early_high_v up to 0.228 V at ss/-40C, narrowest case-5 runt 6.2 ns at tt/-40C).  Not a gate.

Runs: **12** (ok 12); 0 reused from cache.

## Worst case per metric

| metric | limit | worst run | value | margin | verdict |
|---|---|---|---|---|---|
| min_pulse_s (ns) | 2 .. - | `ss_m40c_3v00__case3` | **70.98** | 68.98 | PASS |

## All runs

| run | corner | case | status | min_pulse_s (ns) | early_high_v | end_a_v | end_b_v | final_ok | min_pulse_all_s | min_pulse_cross_s | min_runt_width_s | n_runt | t_high_s | valid_time_s | vdd_at_out_rise_v | vout_off_all_v | vout_off_v | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `ss_m40c_3v00__case3` | ss_m40c_3v00 | 3 | ok | **70.98** (worst) | n/a | 3 | 3.481e-09 | 1 | 7.098e-08 | 7.098e-08 | 2.42e-07 | 6 | 9e-07 | n/a | 1.273 | 3 | 3 | PASS |
| `ss_m40c_3v00__case5` | ss_m40c_3v00 | 5 | ok | 2300 | 0.2727 | 3 | 3.319e-09 | 1 | 2.3e-06 | 1 | 2.3e-06 | 6 | n/a | 4.67e-06 | n/a | 3 | 3 | PASS |
| `ss_m40c_3v30__case3` | ss_m40c_3v30 | 3 | ok | 163.6 | n/a | 3.3 | 3.697e-09 | 1 | 1.636e-07 | 1.636e-07 | 2.22e-07 | 6 | 9e-07 | n/a | 1.293 | 3.3 | 3.3 | PASS |
| `ss_m40c_3v30__case5` | ss_m40c_3v30 | 5 | ok | 2120 | 0.2735 | 3.3 | 3.623e-09 | 1 | 2.12e-06 | 1 | 2.12e-06 | 6 | n/a | 5.879e-06 | n/a | 3.301 | 3.301 | PASS |
| `ss_m40c_3v60__case3` | ss_m40c_3v60 | 3 | ok | 154.9 | n/a | 3.6 | 4.136e-09 | 1 | 1.549e-07 | 1.549e-07 | 2.05e-07 | 6 | 9e-07 | n/a | 1.312 | 3.6 | 3.6 | PASS |
| `ss_m40c_3v60__case5` | ss_m40c_3v60 | 5 | ok | 1940 | 0.2751 | 3.6 | 4.134e-09 | 1 | 1.94e-06 | 1 | 1.94e-06 | 6 | n/a | 6.888e-06 | n/a | 3.601 | 3.601 | PASS |
| `tt_m40c_3v30__case3` | tt_m40c_3v30 | 3 | ok | 73.31 | n/a | 3.3 | 3.608e-09 | 1 | 7.331e-08 | 7.331e-08 | 1.69e-07 | 6 | 9e-07 | n/a | 1.123 | 3.3 | 3.3 | PASS |
| `tt_m40c_3v30__case5` | tt_m40c_3v30 | 5 | ok | 1340 | 0.2263 | 3.3 | 3.508e-09 | 1 | 1.34e-06 | 1 | 1.34e-06 | 6 | n/a | 5.877e-06 | n/a | 3.3 | 3.3 | PASS |
| `tt_m40c_3v60__case3` | tt_m40c_3v60 | 3 | ok | 136 | n/a | 3.6 | 4.274e-09 | 1 | 1.36e-07 | 1.36e-07 | 1.57e-07 | 6 | 9e-07 | n/a | 1.139 | 3.6 | 3.6 | PASS |
| `tt_m40c_3v60__case5` | tt_m40c_3v60 | 5 | ok | 1240 | 0.2273 | 3.6 | 4.199e-09 | 1 | 1.24e-06 | 1 | 1.24e-06 | 6 | n/a | 6.893e-06 | n/a | 3.601 | 3.601 | PASS |
| `sf_m40c_3v30__case3` | sf_m40c_3v30 | 3 | ok | 149.1 | n/a | 3.3 | 3.788e-09 | 1 | 1.491e-07 | 1.491e-07 | 1 | 0 | 9e-07 | n/a | 1.14 | 3.3 | 3.3 | PASS |
| `sf_m40c_3v30__case5` | sf_m40c_3v30 | 5 | ok | 1120 | 0.2265 | 3.3 | 3.78e-09 | 1 | 1.12e-06 | 1 | 1.12e-06 | 6 | n/a | 5.868e-06 | n/a | 3.3 | 3.3 | PASS |
