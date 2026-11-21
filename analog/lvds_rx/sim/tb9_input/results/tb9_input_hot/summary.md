# tb9_input_hot

**Overall: PASS**

TB9 supplement (not gated, reported): the same input-current bench at 125 C / 3.6 V (PLAN_V2 C7: leakage at 125 C / 3.6 V at 0.05 V and 2.4 V) for tt, ss and ff, plus the mid-range points

Runs: **12** (ok 12); 0 reused from cache.

## Worst case per metric

| metric | limit | worst run | value | margin | verdict |
|---|---|---|---|---|---|
| iin_a (uA) | - .. 20 | `ss_125c_3v60__vin0.05` | **0.001112** | 20 | PASS |
| iin_balance_a (uA) | - .. 6 | `ss_125c_3v60__vin2.4` | **4.326e-09** | 6 | PASS |

## All runs

| run | corner | vin | status | iin_a (uA) | iin_balance_a (uA) | i_n_a | i_n_b | i_p_a | i_p_b | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| `tt_125c_3v60__vin0.05` | tt_125c_3v60 | 0.05 | ok | 0.0005269 | 6.485e-10 | -3.398e-10 | -5.694e-10 | -5.269e-10 | -5.694e-10 | PASS |
| `tt_125c_3v60__vin1.2` | tt_125c_3v60 | 1.2 | ok | 0.0002762 | 2.178e-10 | -2.713e-10 | -2.772e-10 | -2.762e-10 | -2.772e-10 | PASS |
| `tt_125c_3v60__vin2.35` | tt_125c_3v60 | 2.35 | ok | 0.000309 | 1.388e-09 | 3.745e-11 | -2.496e-09 | 3.09e-10 | -2.496e-09 | PASS |
| `tt_125c_3v60__vin2.4` | tt_125c_3v60 | 2.4 | ok | 0.0003273 | 1.452e-09 | 4.303e-11 | -2.509e-09 | 3.273e-10 | -2.509e-09 | PASS |
| `ss_125c_3v60__vin0.05` | ss_125c_3v60 | 0.05 | ok | **0.001112** (worst) | 2.009e-09 | -1.112e-09 | -1.147e-09 | -1.07e-09 | -1.147e-09 | PASS |
| `ss_125c_3v60__vin1.2` | ss_125c_3v60 | 1.2 | ok | 0.0009329 | 1.463e-09 | -9.329e-10 | -9.29e-10 | -9.254e-10 | -9.29e-10 | PASS |
| `ss_125c_3v60__vin2.35` | ss_125c_3v60 | 2.35 | ok | 0.000405 | 4.173e-09 | 3.47e-11 | -8.36e-09 | 4.05e-10 | -8.36e-09 | PASS |
| `ss_125c_3v60__vin2.4` | ss_125c_3v60 | 2.4 | ok | 0.0004498 | **4.326e-09** (worst) | 3.725e-11 | -8.418e-09 | 4.498e-10 | -8.418e-09 | PASS |
| `ff_125c_3v60__vin0.05` | ff_125c_3v60 | 0.05 | ok | 0.0002822 | 5.347e-11 | -7.036e-12 | -3.048e-10 | -2.822e-10 | -3.048e-10 | PASS |
| `ff_125c_3v60__vin1.2` | ff_125c_3v60 | 1.2 | ok | 8.446e-06 | 5.554e-11 | 9.991e-13 | -8.541e-12 | -8.446e-12 | -8.541e-12 | PASS |
| `ff_125c_3v60__vin2.35` | ff_125c_3v60 | 2.35 | ok | 6.349e-05 | 1.129e-11 | 4.349e-11 | -1.428e-10 | 6.349e-11 | -1.428e-10 | PASS |
| `ff_125c_3v60__vin2.4` | ff_125c_3v60 | 2.4 | ok | 8.001e-05 | 2.703e-11 | 4.355e-11 | -1.343e-10 | 8.001e-11 | -1.343e-10 | PASS |
