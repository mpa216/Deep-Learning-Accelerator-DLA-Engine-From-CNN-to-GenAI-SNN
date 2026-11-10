# ota_cmp_mc

**Overall: PASS**

Demo: mismatch Monte Carlo (N=200, one ngspice process per seed) of the comparator at TT and at the slow corner, VIC 1.65 V. Pass criterion: mean +- 3 sigma inside the limits, no failed sample.

Runs: **400** (ok 400); 0 reused from cache.

## Monte Carlo statistics (limits applied to mean +- 3 sigma; N valid / failed shown)

### vtrip (mV)

| group | N ok | N failed | mean | sigma | min | max | mean-3s | mean+3s | mean+-6s | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| **tt_27c_3v30 vic=1.65** (worst) | 200 | 0 | -5.286 | 4.667 | -18.34 | 6.929 | -19.29 | 8.715 | -33.29 .. 22.72 | PASS |
| ss_125c_3v00 vic=1.65 | 200 | 0 | -3.617 | 4.692 | -16.77 | 8.74 | -17.69 | 10.46 | -31.77 .. 24.53 | PASS |

Histograms: [tt_27c_3v30 vic=1.65](plots/hist_vtrip__tt_27c_3v30_vic_1.65.png), [ss_125c_3v00 vic=1.65](plots/hist_vtrip__ss_125c_3v00_vic_1.65.png)

### tplh (ns)

| group | N ok | N failed | mean | sigma | min | max | mean-3s | mean+3s | mean+-6s | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| tt_27c_3v30 vic=1.65 | 200 | 0 | 2.76 | 0.1048 | 2.536 | 3.044 | 2.446 | 3.075 | 2.131 .. 3.389 | PASS |
| **ss_125c_3v00 vic=1.65** (worst) | 200 | 0 | 3.214 | 0.1219 | 2.948 | 3.557 | 2.849 | 3.58 | 2.483 .. 3.945 | PASS |

Histograms: [tt_27c_3v30 vic=1.65](plots/hist_tplh__tt_27c_3v30_vic_1.65.png), [ss_125c_3v00 vic=1.65](plots/hist_tplh__ss_125c_3v00_vic_1.65.png)

### idd

| group | N ok | N failed | mean | sigma | min | max | mean-3s | mean+3s | mean+-6s | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| tt_27c_3v30 vic=1.65 | 200 | 0 | 9.751e-05 | 4.283e-05 | 5.844e-05 | 0.0001942 | -3.098e-05 | 0.000226 | -0.0001595 .. 0.0003545 | - |
| ss_125c_3v00 vic=1.65 | 200 | 0 | 8.091e-05 | 2.07e-05 | 5.821e-05 | 0.0001253 | 1.883e-05 | 0.000143 | -4.326e-05 .. 0.0002051 | - |


### idd_raw

| group | N ok | N failed | mean | sigma | min | max | mean-3s | mean+3s | mean+-6s | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| tt_27c_3v30 vic=1.65 | 200 | 0 | -9.751e-05 | 4.283e-05 | -0.0001942 | -5.844e-05 | -0.000226 | 3.098e-05 | -0.0003545 .. 0.0001595 | - |
| ss_125c_3v00 vic=1.65 | 200 | 0 | -8.091e-05 | 2.07e-05 | -0.0001253 | -5.821e-05 | -0.000143 | -1.883e-05 | -0.0002051 .. 4.326e-05 | - |


### tphl

| group | N ok | N failed | mean | sigma | min | max | mean-3s | mean+3s | mean+-6s | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| tt_27c_3v30 vic=1.65 | 200 | 0 | 1.404e-09 | 3.71e-11 | 1.293e-09 | 1.505e-09 | 1.293e-09 | 1.515e-09 | 1.182e-09 .. 1.627e-09 | - |
| ss_125c_3v00 vic=1.65 | 200 | 0 | 1.698e-09 | 4.341e-11 | 1.57e-09 | 1.818e-09 | 1.567e-09 | 1.828e-09 | 1.437e-09 .. 1.958e-09 | - |


