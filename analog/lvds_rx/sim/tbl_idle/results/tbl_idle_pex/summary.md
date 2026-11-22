# tbl_idle_pex

**Overall: PASS**

post-layout gate TBL (pex): tb7_idle with core = sim/tbl/core_pexrc.spice

Runs: **15** (ok 15); 15 reused from cache.

## Worst case per metric

| metric | limit | worst run | value | margin | verdict |
|---|---|---|---|---|---|
| osc_flag | - .. 0 | `ff_m40c_3v60__vic1.2_term0` | **0** | 0 | PASS |
| min_pulse_s (ns) | 2 .. - | `ff_m40c_3v60__vic1.2_term0` | **1e+09** | 1e+09 | PASS |

## All runs

| run | corner | term | vic | status | osc_flag | min_pulse_s (ns) | drift_toggles | held_state | n_high | n_mid | n_settle_flip | out_end_v | out_final_v | t_last_flip_s | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `tt_27c_3v30__vic1.2_term0` | tt_27c_3v30 | 0 | 1.2 | ok | 0 | 1e+09 | n/a | 1 | 3 | 0 | 0 | n/a | 3.3 | 0 | PASS |
| `tt_27c_3v30__vic1.2_term1` | tt_27c_3v30 | 1 | 1.2 | ok | 0 | 1e+09 | 1 | 1 | 3 | 0 | 0 | 4.315e-09 | 3.3 | 0 | PASS |
| `tt_27c_3v30__vic1.2_term2` | tt_27c_3v30 | 2 | 1.2 | ok | 0 | 1e+09 | n/a | 1 | 3 | 0 | 0 | n/a | 3.3 | 0 | PASS |
| `ss_125c_3v00__vic1.2_term0` | ss_125c_3v00 | 0 | 1.2 | ok | 0 | 1e+09 | n/a | 1 | 3 | 0 | 0 | n/a | 3 | 0 | PASS |
| `ss_125c_3v00__vic1.2_term1` | ss_125c_3v00 | 1 | 1.2 | ok | 0 | 1e+09 | 1 | 1 | 3 | 0 | 0 | 1.148e-08 | 3 | 0 | PASS |
| `ss_125c_3v00__vic1.2_term2` | ss_125c_3v00 | 2 | 1.2 | ok | 0 | 1e+09 | n/a | 1 | 3 | 0 | 0 | n/a | 3 | 0 | PASS |
| `ff_m40c_3v60__vic1.2_term0` | ff_m40c_3v60 | 0 | 1.2 | ok | **0** (worst) | **1e+09** (worst) | n/a | 1 | 3 | 0 | 0 | n/a | 3.6 | 0 | PASS |
| `ff_m40c_3v60__vic1.2_term1` | ff_m40c_3v60 | 1 | 1.2 | ok | 0 | 1e+09 | 1 | 1 | 3 | 0 | 0 | 4.467e-09 | 3.6 | 0 | PASS |
| `ff_m40c_3v60__vic1.2_term2` | ff_m40c_3v60 | 2 | 1.2 | ok | 0 | 1e+09 | n/a | 1 | 3 | 0 | 0 | n/a | 3.6 | 0 | PASS |
| `fs_27c_3v30__vic1.2_term0` | fs_27c_3v30 | 0 | 1.2 | ok | 0 | 1e+09 | n/a | 1 | 3 | 0 | 0 | n/a | 3.3 | 0 | PASS |
| `fs_27c_3v30__vic1.2_term1` | fs_27c_3v30 | 1 | 1.2 | ok | 0 | 1e+09 | 1 | 1 | 3 | 0 | 0 | 3.973e-09 | 3.3 | 0 | PASS |
| `fs_27c_3v30__vic1.2_term2` | fs_27c_3v30 | 2 | 1.2 | ok | 0 | 1e+09 | n/a | 1 | 3 | 0 | 0 | n/a | 3.3 | 0 | PASS |
| `sf_27c_3v30__vic1.2_term0` | sf_27c_3v30 | 0 | 1.2 | ok | 0 | 1e+09 | n/a | 1 | 3 | 0 | 0 | n/a | 3.3 | 0 | PASS |
| `sf_27c_3v30__vic1.2_term1` | sf_27c_3v30 | 1 | 1.2 | ok | 0 | 1e+09 | 1 | 1 | 3 | 0 | 0 | 5.136e-09 | 3.3 | 0 | PASS |
| `sf_27c_3v30__vic1.2_term2` | sf_27c_3v30 | 2 | 1.2 | ok | 0 | 1e+09 | n/a | 1 | 3 | 0 | 0 | n/a | 3.3 | 0 | PASS |
