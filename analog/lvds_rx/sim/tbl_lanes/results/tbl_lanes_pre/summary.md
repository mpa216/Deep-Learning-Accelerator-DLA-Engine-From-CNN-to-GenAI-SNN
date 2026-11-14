# tbl_lanes_pre

**Overall: PASS**

post-layout gate TBL (pre): tb10_lanes with core = netlist/lvds_rx_core.spice

Runs: **1** (ok 1); 0 reused from cache.

## Worst case per metric

| metric | limit | worst run | value | margin | verdict |
|---|---|---|---|---|---|
| xtalk_jitter_ui (% UI) | - .. 5 | `tt_27c_3v30__mc3s0` | **0.06263** | 4.937 | PASS |

## All runs

| run | corner | mc3s | status | xtalk_jitter_ui (% UI) | delay_lane0_ps | delay_lane1_ps | delay_lane2_ps | n_missed_a0 | n_missed_a1 | n_missed_a2 | skew_s | xtalk_lane0_ui | xtalk_lane1_ui | xtalk_lane2_ui | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `tt_27c_3v30__mc3s0` | tt_27c_3v30 | 0 | ok | **0.06263** (worst) | 3659 | 3641 | 3652 | 0 | 0 | 0 | 1.742e-11 | 0.0006263 | 0.0004551 | 0.0005278 | PASS |
