# tbl_eye_pex

**Overall: PASS**

post-layout gate TBL (pex): tb5_eye with core = sim/tbl/core_pexrc.spice

Runs: **4** (ok 4); 0 reused from cache.

## Worst case per metric

| metric | limit | worst run | value | margin | verdict |
|---|---|---|---|---|---|
| ber_errors | - .. 0 | `ff_125c_3v60__vic0.05_vid0.1_rate100000000.0` | **0** | 0 | PASS |
| toggle_diff | 0 .. 0 | `ff_125c_3v60__vic0.05_vid0.1_rate100000000.0` | **0** | 0 | PASS |
| eye_open_ui | 0.5 .. - | `ff_125c_3v60__vic0.05_vid0.1_rate200000000.0` | **0.9911** | 0.4911 | PASS |

## All runs

| run | corner | rate | vic | vid | status | ber_errors | toggle_diff | eye_open_ui | dcd_ui | delay_s | jitter_pp_ps | n_in_toggles | n_out_toggles | tr_s | v_open_v | vic_eff_v | vid_pin_pp_v | vid_set_v | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `ff_125c_3v60__vic0.05_vid0.1_rate100000000.0` | ff_125c_3v60 | 100000000.0 | 0.05 | 0.1 | ok | **0** (worst) | **0** (worst) | 0.9964 | 0.00318 | 3.151e-09 | 35.85 | 66 | 66 | 2e-09 | 3.6 | 0.05 | 0.2063 | 0.1 | PASS |
| `ff_125c_3v60__vic0.05_vid0.1_rate200000000.0` | ff_125c_3v60 | 200000000.0 | 0.05 | 0.1 | ok | 0 | 0 | **0.9911** (worst) | 0.006911 | 3.041e-09 | 44.31 | 66 | 66 | 1e-09 | 3.6 | 0.05 | 0.2127 | 0.1 | PASS |
| `ff_125c_3v60__vic0.05_vid0.35_rate100000000.0` | ff_125c_3v60 | 100000000.0 | 0.05 | 0.35 | ok | 0 | 0 | 0.999 | 0.0003093 | 2.514e-09 | 10.2 | 66 | 66 | 1e-09 | 3.6 | 0.175 | 0.7444 | 0.35 | PASS |
| `ff_125c_3v60__vic0.05_vid0.35_rate200000000.0` | ff_125c_3v60 | 200000000.0 | 0.05 | 0.35 | ok | 0 | 0 | 0.9971 | 0.0002673 | 2.527e-09 | 14.53 | 66 | 66 | 5e-10 | 3.6 | 0.175 | 0.7847 | 0.35 | PASS |
