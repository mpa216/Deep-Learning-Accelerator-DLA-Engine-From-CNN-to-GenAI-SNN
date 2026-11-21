# tbl_en_pexw_off

**Overall: PASS**

T11 iteration 2, evidence for gate TBL's TB8 checks: tb8_en on the extracted macro (core = sim/tbl/core_pexrc.spice) at the highest pre-layout vout_off_v (ss/-40C, 0.285-0.296 V against 0.33 V).  Not a gate.

Runs: **6** (ok 6); 0 reused from cache.

## Worst case per metric

| metric | limit | worst run | value | margin | verdict |
|---|---|---|---|---|---|
| min_pulse_s (ns) | 2 .. - | `ss_m40c_3v00__case0` | **1e+09** | 1e+09 | PASS |

## All runs

| run | corner | case | status | min_pulse_s (ns) | en1_valid_ok | end_a_v | end_b_v | final_ok | idd_en0_a | min_pulse_all_s | min_pulse_cross_s | min_runt_width_s | n_runt | vdd_at_peak_v | vdd_low_from_v | vout_en1_v | vout_off_all_v | vout_off_v | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `ss_m40c_3v00__case0` | ss_m40c_3v00 | 0 | ok | **1e+09** (worst) | n/a | 3.321e-09 | 3.321e-09 | 1 | 8.067e-08 | 1.1e-08 | 1 | 1 | 0 | 1.081 | 1.141 | n/a | 0.3521 | 2.003e-06 | PASS |
| `ss_m40c_3v00__case1` | ss_m40c_3v00 | 1 | ok | 1e+09 | 1 | 1.9 | 2.882e-09 | 1 | n/a | 1.6e-08 | 1 | 1 | 0 | 1.065 | 1.103 | 1.995 | 0.3462 | 1.324e-06 | PASS |
| `ss_m40c_3v30__case0` | ss_m40c_3v30 | 0 | ok | 1e+09 | n/a | 3.604e-09 | 3.608e-09 | 1 | 4.715e-08 | 1e-08 | 1 | 1 | 0 | 1.124 | 1.124 | n/a | 0.363 | 2.77e-07 | PASS |
| `ss_m40c_3v30__case1` | ss_m40c_3v30 | 1 | ok | 1e+09 | 1 | 1.9 | 2.882e-09 | 1 | n/a | 1.6e-08 | 1 | 1 | 0 | 1.065 | 1.103 | 1.993 | 0.3462 | 1.324e-06 | PASS |
| `ss_m40c_3v60__case0` | ss_m40c_3v60 | 0 | ok | 1e+09 | n/a | 4.124e-09 | 4.125e-09 | 1 | 5.459e-08 | 1e-08 | 1 | 1 | 0 | 1.082 | 1.154 | n/a | 0.3528 | 1.923e-07 | PASS |
| `ss_m40c_3v60__case1` | ss_m40c_3v60 | 1 | ok | 1e+09 | 1 | 1.9 | 2.882e-09 | 1 | n/a | 1.6e-08 | 1 | 1 | 0 | 1.065 | 1.103 | 1.993 | 0.3462 | 1.324e-06 | PASS |
