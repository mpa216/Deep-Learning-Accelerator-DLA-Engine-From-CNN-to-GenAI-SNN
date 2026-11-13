# tb9_input_hot

**Overall: PASS**

TB9 supplement (not gated, reported): the same input-current bench at 125 C / 3.6 V (PLAN_V2 C7: leakage at 125 C / 3.6 V at 0.05 V and 2.4 V) for tt, ss and ff, plus the mid-range points

Runs: **12** (ok 12); 12 reused from cache.

## Worst case per metric

| metric | limit | worst run | value | margin | verdict |
|---|---|---|---|---|---|
| iin_a (uA) | - .. 20 | `ss_125c_3v60__vin0.05` | **0.0009027** | 20 | PASS |
| iin_balance_a (uA) | - .. 6 | `ss_125c_3v60__vin0.05` | **1.537e-09** | 6 | PASS |

## All runs

| run | corner | vin | status | iin_a (uA) | iin_balance_a (uA) | i_n_a | i_n_b | i_p_a | i_p_b | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| `tt_125c_3v60__vin0.05` | tt_125c_3v60 | 0.05 | ok | 0.000466 | 3.396e-10 | -2.334e-10 | -4.985e-10 | -4.66e-10 | -4.985e-10 | PASS |
| `tt_125c_3v60__vin1.2` | tt_125c_3v60 | 1.2 | ok | 0.0001889 | 1.366e-10 | -1.817e-10 | -1.896e-10 | -1.889e-10 | -1.896e-10 | PASS |
| `tt_125c_3v60__vin2.35` | tt_125c_3v60 | 2.35 | ok | 0.0003069 | 1.112e-10 | 3.517e-11 | -1.568e-09 | 3.069e-10 | -1.568e-09 | PASS |
| `tt_125c_3v60__vin2.4` | tt_125c_3v60 | 2.4 | ok | 0.0003271 | 1.851e-10 | 3.539e-11 | -1.569e-09 | 3.271e-10 | -1.569e-09 | PASS |
| `ss_125c_3v60__vin0.05` | ss_125c_3v60 | 0.05 | ok | **0.0009027** (worst) | **1.537e-09** (worst) | -8.758e-10 | -9.684e-10 | -9.027e-10 | -9.684e-10 | PASS |
| `ss_125c_3v60__vin1.2` | ss_125c_3v60 | 1.2 | ok | 0.0007308 | 9.267e-10 | -7.308e-10 | -7.3e-10 | -7.271e-10 | -7.3e-10 | PASS |
| `ss_125c_3v60__vin2.35` | ss_125c_3v60 | 2.35 | ok | 0.0003817 | 5.42e-10 | 4.061e-11 | -6.385e-09 | 3.817e-10 | -6.385e-09 | PASS |
| `ss_125c_3v60__vin2.4` | ss_125c_3v60 | 2.4 | ok | 0.000419 | 4.892e-10 | 4.26e-11 | -6.427e-09 | 4.19e-10 | -6.427e-09 | PASS |
| `ff_125c_3v60__vin0.05` | ff_125c_3v60 | 0.05 | ok | 0.0002632 | 6.931e-11 | 1.969e-11 | -2.775e-10 | -2.632e-10 | -2.775e-10 | PASS |
| `ff_125c_3v60__vin1.2` | ff_125c_3v60 | 1.2 | ok | 2.509e-05 | 3.723e-11 | 2.509e-11 | 1.525e-11 | 1.53e-11 | 1.525e-11 | PASS |
| `ff_125c_3v60__vin2.35` | ff_125c_3v60 | 2.35 | ok | 0.0001589 | 1.861e-11 | 4.524e-11 | 6.027e-11 | 1.589e-10 | 6.027e-11 | PASS |
| `ff_125c_3v60__vin2.4` | ff_125c_3v60 | 2.4 | ok | 0.0001732 | 3.465e-11 | 4.526e-11 | 7.007e-11 | 1.732e-10 | 7.007e-11 | PASS |
