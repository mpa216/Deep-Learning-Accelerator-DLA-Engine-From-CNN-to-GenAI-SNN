# tbl_eye_pre

**Overall: PASS**

post-layout gate TBL (pre): tb5_eye with core = netlist/lvds_rx_core.spice

Runs: **4** (ok 4); 0 reused from cache.

## Worst case per metric

| metric | limit | worst run | value | margin | verdict |
|---|---|---|---|---|---|
| ber_errors | - .. 0 | `ff_125c_3v60__vic0.05_vid0.1_rate100000000.0` | **0** | 0 | PASS |
| toggle_diff | 0 .. 0 | `ff_125c_3v60__vic0.05_vid0.1_rate100000000.0` | **0** | 0 | PASS |
| eye_open_ui | 0.5 .. - | `ff_125c_3v60__vic0.05_vid0.1_rate200000000.0` | **0.9943** | 0.4943 | PASS |

## All runs

| run | corner | rate | vic | vid | status | ber_errors | toggle_diff | eye_open_ui | dcd_ui | delay_s | jitter_pp_ps | n_in_toggles | n_out_toggles | tr_s | v_open_v | vic_eff_v | vid_pin_pp_v | vid_set_v | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `ff_125c_3v60__vic0.05_vid0.1_rate100000000.0` | ff_125c_3v60 | 100000000.0 | 0.05 | 0.1 | ok | **0** (worst) | **0** (worst) | 0.998 | 0.001637 | 3.138e-09 | 19.62 | 66 | 66 | 2e-09 | 3.6 | 0.05 | 0.2063 | 0.1 | PASS |
| `ff_125c_3v60__vic0.05_vid0.1_rate200000000.0` | ff_125c_3v60 | 200000000.0 | 0.05 | 0.1 | ok | 0 | 0 | **0.9943** (worst) | 0.003767 | 3.028e-09 | 28.52 | 66 | 66 | 1e-09 | 3.6 | 0.05 | 0.2127 | 0.1 | PASS |
| `ff_125c_3v60__vic0.05_vid0.35_rate100000000.0` | ff_125c_3v60 | 100000000.0 | 0.05 | 0.35 | ok | 0 | 0 | 0.9978 | 0.001508 | 2.502e-09 | 21.57 | 66 | 66 | 1e-09 | 3.6 | 0.175 | 0.7446 | 0.35 | PASS |
| `ff_125c_3v60__vic0.05_vid0.35_rate200000000.0` | ff_125c_3v60 | 200000000.0 | 0.05 | 0.35 | ok | 0 | 0 | 0.9948 | 0.002529 | 2.512e-09 | 25.96 | 66 | 66 | 5e-10 | 3.6 | 0.175 | 0.7846 | 0.35 | PASS |
