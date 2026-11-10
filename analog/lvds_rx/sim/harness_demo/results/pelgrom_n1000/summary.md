# pelgrom_n1000

**Overall: PASS**

Monte Carlo mechanism proof: sigma of the input offset of an NMOS pair at four gate areas, mismatch only, 200 seeds each (one ngspice process per seed). Compare with harness_demo/check_pelgrom.py.

Runs: **1000** (ok 1000); 0 reused from cache.

## Monte Carlo statistics (limits applied to mean +- 3 sigma; N valid / failed shown)

### vos (mV)

| group | N ok | N failed | mean | sigma | min | max | mean-3s | mean+3s | mean+-6s | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| **tt_27c_3v30 l=0.5u w=1u** (worst) | 1000 | 0 | 0.3126 | 11.95 | -34.78 | 45.72 | -35.52 | 36.15 | -71.36 .. 71.99 | PASS |

Histograms: [tt_27c_3v30 l=0.5u w=1u](plots/hist_vos__tt_27c_3v30_l_0.5u_w_1u.png)

### gain

| group | N ok | N failed | mean | sigma | min | max | mean-3s | mean+3s | mean+-6s | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| tt_27c_3v30 l=0.5u w=1u | 1000 | 0 | -1.308 | 0.003284 | -1.318 | -1.296 | -1.318 | -1.298 | -1.328 .. -1.288 | - |


### odm

| group | N ok | N failed | mean | sigma | min | max | mean-3s | mean+3s | mean+-6s | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| tt_27c_3v30 l=0.5u w=1u | 1000 | 0 | 0.006949 | 0.01562 | -0.039 | 0.06622 | -0.03992 | 0.05382 | -0.08679 .. 0.1007 | - |


### odp

| group | N ok | N failed | mean | sigma | min | max | mean-3s | mean+3s | mean+-6s | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| tt_27c_3v30 l=0.5u w=1u | 1000 | 0 | -0.006131 | 0.01562 | -0.05204 | 0.05324 | -0.053 | 0.04074 | -0.09987 .. 0.08761 | - |


