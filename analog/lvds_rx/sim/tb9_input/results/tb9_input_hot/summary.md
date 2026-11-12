# tb9_input_hot

**Overall: PASS**

TB9 supplement (not gated, reported): the same input-current bench at 125 C / 3.6 V (PLAN_V2 C7: leakage at 125 C / 3.6 V at 0.05 V and 2.4 V) for tt, ss and ff, plus the mid-range points

Runs: **12** (ok 12); 0 reused from cache.

## Worst case per metric

| metric | limit | worst run | value | margin | verdict |
|---|---|---|---|---|---|
| iin_a (uA) | - .. 20 | `ss_125c_3v60__vin0.05` | **0.0009013** | 20 | PASS |
| iin_balance_a (uA) | - .. 6 | `ss_125c_3v60__vin0.05` | **1.501e-09** | 6 | PASS |

## All runs

| run | corner | vin | status | iin_a (uA) | iin_balance_a (uA) | i_n_a | i_n_b | i_p_a | i_p_b | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| `tt_125c_3v60__vin0.05` | tt_125c_3v60 | 0.05 | ok | 0.0004655 | 2.99e-10 | -2.345e-10 | -4.986e-10 | -4.655e-10 | -4.986e-10 | PASS |
| `tt_125c_3v60__vin1.2` | tt_125c_3v60 | 1.2 | ok | 0.0001893 | 1.663e-10 | -1.823e-10 | -1.9e-10 | -1.893e-10 | -1.9e-10 | PASS |
| `tt_125c_3v60__vin2.35` | tt_125c_3v60 | 2.35 | ok | 0.0004823 | 1.527e-10 | 1.341e-11 | -1.576e-09 | -4.823e-10 | -1.576e-09 | PASS |
| `tt_125c_3v60__vin2.4` | tt_125c_3v60 | 2.4 | ok | 0.000456 | 1.2e-10 | 1.865e-11 | -1.582e-09 | -4.56e-10 | -1.582e-09 | PASS |
| `ss_125c_3v60__vin0.05` | ss_125c_3v60 | 0.05 | ok | **0.0009013** (worst) | **1.501e-09** (worst) | -8.79e-10 | -9.686e-10 | -9.013e-10 | -9.686e-10 | PASS |
| `ss_125c_3v60__vin1.2` | ss_125c_3v60 | 1.2 | ok | 0.0007325 | 9.475e-10 | -7.325e-10 | -7.313e-10 | -7.283e-10 | -7.313e-10 | PASS |
| `ss_125c_3v60__vin2.35` | ss_125c_3v60 | 2.35 | ok | 0.0003886 | 4.028e-10 | 4.702e-11 | -6.409e-09 | 3.886e-10 | -6.409e-09 | PASS |
| `ss_125c_3v60__vin2.4` | ss_125c_3v60 | 2.4 | ok | 0.000421 | 5.214e-10 | 4.789e-11 | -6.451e-09 | 4.21e-10 | -6.451e-09 | PASS |
| `ff_125c_3v60__vin0.05` | ff_125c_3v60 | 0.05 | ok | 0.0002631 | 2.376e-11 | 1.947e-11 | -2.775e-10 | -2.631e-10 | -2.775e-10 | PASS |
| `ff_125c_3v60__vin1.2` | ff_125c_3v60 | 1.2 | ok | 2.499e-05 | 4.653e-12 | 2.499e-11 | 1.517e-11 | 1.522e-11 | 1.517e-11 | PASS |
| `ff_125c_3v60__vin2.35` | ff_125c_3v60 | 2.35 | ok | 4.115e-05 | 6.01e-11 | 4.115e-11 | 5.916e-11 | 1.527e-11 | 5.916e-11 | PASS |
| `ff_125c_3v60__vin2.4` | ff_125c_3v60 | 2.4 | ok | 4.523e-05 | 7.129e-11 | 4.523e-11 | 6.574e-11 | 2.308e-11 | 6.574e-11 | PASS |
