# ota_cmp_global

**Overall: FAIL**

Demo: global (die-to-die) plus mismatch statistics, mode both: sw_stat_global=1 with the statistical .lib section and sw_stat_mismatch=1. N=100.

Runs: **100** (ok 100); 0 reused from cache.

## Monte Carlo statistics (limits applied to mean +- 3 sigma; N valid / failed shown)

### vtrip (mV)

| group | N ok | N failed | mean | sigma | min | max | mean-3s | mean+3s | mean+-6s | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| **tt_27c_3v30 vic=1.65** (worst) | 100 | 0 | -4.984 | 4.548 | -16.22 | 8.142 | -18.63 | 8.661 | -32.27 .. 22.3 | PASS |

Histograms: [tt_27c_3v30 vic=1.65](plots/hist_vtrip__tt_27c_3v30_vic_1.65.png)

### idd (uA)

| group | N ok | N failed | mean | sigma | min | max | mean-3s | mean+3s | mean+-6s | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| **tt_27c_3v30 vic=1.65** (worst) | 100 | 0 | 95.27 | 39.32 | 58.07 | 201.7 | -22.68 | 213.2 | -140.6 .. 331.2 | FAIL |

Histograms: [tt_27c_3v30 vic=1.65](plots/hist_idd__tt_27c_3v30_vic_1.65.png)

### idd_raw

| group | N ok | N failed | mean | sigma | min | max | mean-3s | mean+3s | mean+-6s | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| tt_27c_3v30 vic=1.65 | 100 | 0 | -9.527e-05 | 3.932e-05 | -0.0002017 | -5.807e-05 | -0.0002132 | 2.268e-05 | -0.0003312 .. 0.0001406 | - |


### tphl

| group | N ok | N failed | mean | sigma | min | max | mean-3s | mean+3s | mean+-6s | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| tt_27c_3v30 vic=1.65 | 100 | 0 | 1.415e-09 | 6.574e-11 | 1.175e-09 | 1.551e-09 | 1.218e-09 | 1.612e-09 | 1.021e-09 .. 1.81e-09 | - |


### tplh

| group | N ok | N failed | mean | sigma | min | max | mean-3s | mean+3s | mean+-6s | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| tt_27c_3v30 vic=1.65 | 100 | 0 | 2.753e-09 | 1.127e-10 | 2.46e-09 | 3.081e-09 | 2.415e-09 | 3.091e-09 | 2.077e-09 .. 3.429e-09 | - |


