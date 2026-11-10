# ota_cmp_corners

**Overall: FAIL**

Demo: 5T OTA + inverter comparator, worst5 corners x two common-mode voltages. Limits are demo values (propagation delay target of the handoff 9.1 TB4: 5 ns).

Runs: **10** (ok 10); 10 reused from cache.

## Worst case per metric

| metric | limit | worst run | value | margin | verdict |
|---|---|---|---|---|---|
| vtrip (mV) | -50 .. 50 | `ff_m40c_3v60__vic1.65` | **-6.37** | 43.63 | PASS |
| tplh (ns) | - .. 5 | `ss_125c_3v00__vic0.9` | **5.992** | -0.992 | FAIL |
| tphl (ns) | - .. 5 | `ss_125c_3v00__vic0.9` | **3.723** | 1.277 | PASS |
| idd (uA) | - .. 200 | `ff_m40c_3v60__vic1.65` | **87** | 113 | PASS |

## All runs

| run | corner | vic | status | vtrip (mV) | tplh (ns) | tphl (ns) | idd (uA) | idd_raw | verdict |
|---|---|---|---|---|---|---|---|---|---|
| `tt_27c_3v30__vic0.9` | tt_27c_3v30 | 0.9 | ok | -4.9 | 4.247 | 2.514 | 61.86 | -6.186e-05 | PASS |
| `tt_27c_3v30__vic1.65` | tt_27c_3v30 | 1.65 | ok | -4.789 | 2.743 | 1.405 | 85.37 | -8.537e-05 | PASS |
| `ss_125c_3v00__vic0.9` | ss_125c_3v00 | 0.9 | ok | -3.746 | **5.992** (worst) FAIL | **3.723** (worst) | 51.71 | -5.171e-05 | FAIL: tplh=5.992e-09 outside [-inf, 5e-09] |
| `ss_125c_3v00__vic1.65` | ss_125c_3v00 | 1.65 | ok | -3.239 | 3.195 | 1.699 | 84.04 | -8.404e-05 | PASS |
| `ff_m40c_3v60__vic0.9` | ff_m40c_3v60 | 0.9 | ok | -6.362 | 2.949 | 1.812 | 76.63 | -7.663e-05 | PASS |
| `ff_m40c_3v60__vic1.65` | ff_m40c_3v60 | 1.65 | ok | **-6.37** (worst) | 2.417 | 1.197 | **87** (worst) | -8.7e-05 | PASS |
| `fs_27c_3v30__vic0.9` | fs_27c_3v30 | 0.9 | ok | -4.817 | 3.474 | 1.992 | 73.32 | -7.332e-05 | PASS |
| `fs_27c_3v30__vic1.65` | fs_27c_3v30 | 1.65 | ok | -5.25 | 2.805 | 1.206 | 85.32 | -8.532e-05 | PASS |
| `sf_27c_3v30__vic0.9` | sf_27c_3v30 | 0.9 | ok | -5.235 | 5.907 FAIL | 3.482 | 48.45 | -4.845e-05 | FAIL: tplh=5.907e-09 outside [-inf, 5e-09] |
| `sf_27c_3v30__vic1.65` | sf_27c_3v30 | 1.65 | ok | -4.655 | 2.68 | 1.603 | 85.44 | -8.544e-05 | PASS |
