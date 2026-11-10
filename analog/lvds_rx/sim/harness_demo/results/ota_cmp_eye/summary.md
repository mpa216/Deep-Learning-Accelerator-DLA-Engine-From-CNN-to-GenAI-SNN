# ota_cmp_eye

**Overall: FAIL**

Demo: PRBS7 eye of the OTA + inverter comparator at 100 Mb/s (UI 10 ns, 1 ns edges), VOD 100 mV and 350 mV, worst5 corners. Limits are the handoff TB5 targets (h-open >= 0.6 UI, DCD <= 5 % UI) applied to a demo circuit that was not designed for them.

Runs: **10** (ok 10); 0 reused from cache.

## Worst case per metric

| metric | limit | worst run | value | margin | verdict |
|---|---|---|---|---|---|
| h_open_ui (UI) | 0.6 .. - | `fs_27c_3v30__vod0.1` | **0.8477** | 0.2477 | PASS |
| dcd_ui (% UI) | - .. 5 | `fs_27c_3v30__vod0.1` | **15.23** | -10.23 | FAIL |

## All runs

| run | corner | vod | status | h_open_ui (UI) | dcd_ui (% UI) | jitter_pp_ps | n_edges | v_open | vid_pp_mV | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| `tt_27c_3v30__vod0.1` | tt_27c_3v30 | 0.1 | ok | 0.8741 | 12.59 FAIL | 1259 | 61 | 3.298 | 200 | FAIL: dcd_ui=0.1259 outside [-inf, 0.05] |
| `tt_27c_3v30__vod0.35` | tt_27c_3v30 | 0.35 | ok | 0.9039 | 9.607 FAIL | 960.7 | 61 | 3.3 | 700 | FAIL: dcd_ui=0.09607 outside [-inf, 0.05] |
| `ss_125c_3v00__vod0.1` | ss_125c_3v00 | 0.1 | ok | 0.8587 | 14.13 FAIL | 1413 | 61 | 2.998 | 200 | FAIL: dcd_ui=0.1413 outside [-inf, 0.05] |
| `ss_125c_3v00__vod0.35` | ss_125c_3v00 | 0.35 | ok | 0.9006 | 9.943 FAIL | 994.3 | 61 | 3 | 700 | FAIL: dcd_ui=0.09943 outside [-inf, 0.05] |
| `ff_m40c_3v60__vod0.1` | ff_m40c_3v60 | 0.1 | ok | 0.8851 | 11.49 FAIL | 1149 | 61 | 3.593 | 200 | FAIL: dcd_ui=0.1149 outside [-inf, 0.05] |
| `ff_m40c_3v60__vod0.35` | ff_m40c_3v60 | 0.35 | ok | 0.9057 | 9.432 FAIL | 943.2 | 61 | 3.6 | 700 | FAIL: dcd_ui=0.09432 outside [-inf, 0.05] |
| `fs_27c_3v30__vod0.1` | fs_27c_3v30 | 0.1 | ok | **0.8477** (worst) | **15.23** (worst) FAIL | 1523 | 61 | 3.279 | 200 | FAIL: dcd_ui=0.1523 outside [-inf, 0.05] |
| `fs_27c_3v30__vod0.35` | fs_27c_3v30 | 0.35 | ok | 0.8862 | 11.38 FAIL | 1138 | 61 | 3.297 | 700 | FAIL: dcd_ui=0.1138 outside [-inf, 0.05] |
| `sf_27c_3v30__vod0.1` | sf_27c_3v30 | 0.1 | ok | 0.9005 | 9.953 FAIL | 995.3 | 61 | 3.3 | 200 | FAIL: dcd_ui=0.09953 outside [-inf, 0.05] |
| `sf_27c_3v30__vod0.35` | sf_27c_3v30 | 0.35 | ok | 0.9212 | 7.882 FAIL | 788.2 | 61 | 3.3 | 700 | FAIL: dcd_ui=0.07882 outside [-inf, 0.05] |
