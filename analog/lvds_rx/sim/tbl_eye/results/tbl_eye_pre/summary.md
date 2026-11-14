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
| `ff_125c_3v60__vic0.05_vid0.1_rate100000000.0` | ff_125c_3v60 | 100000000.0 | 0.05 | 0.1 | ok | **0** (worst) | **0** (worst) | 0.9977 | 0.001866 | 3.278e-09 | 22.54 | 66 | 66 | 2e-09 | 3.6 | 0.05 | 0.2065 | 0.1 | PASS |
| `ff_125c_3v60__vic0.05_vid0.1_rate200000000.0` | ff_125c_3v60 | 200000000.0 | 0.05 | 0.1 | ok | 0 | 0 | **0.9943** (worst) | 0.004398 | 3.145e-09 | 28.54 | 66 | 66 | 1e-09 | 3.6 | 0.05 | 0.213 | 0.1 | PASS |
| `ff_125c_3v60__vic0.05_vid0.35_rate100000000.0` | ff_125c_3v60 | 100000000.0 | 0.05 | 0.35 | ok | 0 | 0 | 0.9975 | 0.001725 | 2.416e-09 | 24.81 | 66 | 66 | 1e-09 | 3.6 | 0.175 | 0.7451 | 0.35 | PASS |
| `ff_125c_3v60__vic0.05_vid0.35_rate200000000.0` | ff_125c_3v60 | 200000000.0 | 0.05 | 0.35 | ok | 0 | 0 | 0.9955 | 0.002815 | 2.418e-09 | 22.72 | 66 | 66 | 5e-10 | 3.6 | 0.175 | 0.7857 | 0.35 | PASS |
