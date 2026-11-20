# tb9_input_hot

**Overall: PASS**

TB9 supplement (not gated, reported): the same input-current bench at 125 C / 3.6 V (PLAN_V2 C7: leakage at 125 C / 3.6 V at 0.05 V and 2.4 V) for tt, ss and ff, plus the mid-range points

Runs: **12** (ok 12); 0 reused from cache.

## Worst case per metric

| metric | limit | worst run | value | margin | verdict |
|---|---|---|---|---|---|
| iin_a (uA) | - .. 20 | `ss_125c_3v60__vin0.05` | **0.001112** | 20 | PASS |
| iin_balance_a (uA) | - .. 6 | `ss_125c_3v60__vin2.35` | **4.306e-09** | 6 | PASS |

## All runs

| run | corner | vin | status | iin_a (uA) | iin_balance_a (uA) | i_n_a | i_n_b | i_p_a | i_p_b | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| `tt_125c_3v60__vin0.05` | tt_125c_3v60 | 0.05 | ok | 0.0005269 | 6.257e-10 | -3.397e-10 | -5.694e-10 | -5.269e-10 | -5.694e-10 | PASS |
| `tt_125c_3v60__vin1.2` | tt_125c_3v60 | 1.2 | ok | 0.0002762 | 2.762e-10 | -2.713e-10 | -2.772e-10 | -2.762e-10 | -2.772e-10 | PASS |
| `tt_125c_3v60__vin2.35` | tt_125c_3v60 | 2.35 | ok | 0.0003091 | 1.321e-09 | 3.744e-11 | -2.496e-09 | 3.091e-10 | -2.496e-09 | PASS |
| `tt_125c_3v60__vin2.4` | tt_125c_3v60 | 2.4 | ok | 0.0003273 | 1.389e-09 | 4.303e-11 | -2.509e-09 | 3.273e-10 | -2.509e-09 | PASS |
| `ss_125c_3v60__vin0.05` | ss_125c_3v60 | 0.05 | ok | **0.001112** (worst) | 1.909e-09 | -1.112e-09 | -1.147e-09 | -1.07e-09 | -1.147e-09 | PASS |
| `ss_125c_3v60__vin1.2` | ss_125c_3v60 | 1.2 | ok | 0.0009327 | 1.382e-09 | -9.327e-10 | -9.289e-10 | -9.252e-10 | -9.289e-10 | PASS |
| `ss_125c_3v60__vin2.35` | ss_125c_3v60 | 2.35 | ok | 0.000405 | **4.306e-09** (worst) | 3.47e-11 | -8.358e-09 | 4.05e-10 | -8.358e-09 | PASS |
| `ss_125c_3v60__vin2.4` | ss_125c_3v60 | 2.4 | ok | 0.0004432 | 4.258e-09 | 4.31e-11 | -8.423e-09 | 4.432e-10 | -8.423e-09 | PASS |
| `ff_125c_3v60__vin0.05` | ff_125c_3v60 | 0.05 | ok | 0.0002822 | 3.465e-11 | -7.034e-12 | -3.048e-10 | -2.822e-10 | -3.048e-10 | PASS |
| `ff_125c_3v60__vin1.2` | ff_125c_3v60 | 1.2 | ok | 8.445e-06 | 7.525e-11 | 1.002e-12 | -8.539e-12 | -8.445e-12 | -8.539e-12 | PASS |
| `ff_125c_3v60__vin2.35` | ff_125c_3v60 | 2.35 | ok | 6.061e-05 | 9.228e-11 | 4.769e-11 | -1.457e-10 | 6.061e-11 | -1.457e-10 | PASS |
| `ff_125c_3v60__vin2.4` | ff_125c_3v60 | 2.4 | ok | 7.68e-05 | 6.584e-11 | 4.773e-11 | -1.375e-10 | 7.68e-11 | -1.375e-10 | PASS |
