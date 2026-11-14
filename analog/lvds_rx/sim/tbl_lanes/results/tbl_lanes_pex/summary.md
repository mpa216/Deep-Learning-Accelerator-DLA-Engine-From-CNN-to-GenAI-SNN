# tbl_lanes_pex

**Overall: PASS**

post-layout gate TBL (pex): tb10_lanes with core = sim/tbl/core_pexrc.spice

Runs: **1** (ok 1); 0 reused from cache.

## Worst case per metric

| metric | limit | worst run | value | margin | verdict |
|---|---|---|---|---|---|
| xtalk_jitter_ui (% UI) | - .. 5 | `tt_27c_3v30__mc3s0` | **0.09915** | 4.901 | PASS |

## All runs

| run | corner | mc3s | status | xtalk_jitter_ui (% UI) | delay_lane0_ps | delay_lane1_ps | delay_lane2_ps | n_missed_a0 | n_missed_a1 | n_missed_a2 | skew_s | xtalk_lane0_ui | xtalk_lane1_ui | xtalk_lane2_ui | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `tt_27c_3v30__mc3s0` | tt_27c_3v30 | 0 | ok | **0.09915** (worst) | 5358 | 5355 | 5360 | 0 | 0 | 0 | 5.334e-12 | 0.0009915 | 0.0006954 | 0.0005742 | PASS |
