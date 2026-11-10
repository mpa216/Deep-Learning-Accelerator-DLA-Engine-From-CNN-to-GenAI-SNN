#!/bin/bash
# validate_all.sh - run every validation on the regenerated LUTs; output -> lut_regen/validation_report.txt
# (run through tools/cx).  Exit status is always 0; read the report (PASS/FAIL lines).
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE/.."
KIT=/foss/designs/Analog/starter_files_open_source_tools/gf180mcuD/simulation
R=lut_regen/validation_report.txt
{
  echo "=== validation of regenerated LUTs, $(date) ==="
  for D in nfet_03v3 pfet_03v3; do
    echo; echo "##### A. regenerated vs kit, $D"
    python3 lut_regen/validate_vs_kit.py luts/$D.mat $KIT/$D.mat $D
  done
  for D in nfet_03v3 pfet_03v3; do
    echo; echo "##### B. spot check vs direct ngspice, $D (typical 27C), on-grid nodes, VSB up to 2.0 V"
    python3 lut_regen/spot_check.py luts/$D.mat $D --mode grid --seed 11
    echo; echo "##### B2. same, VGS/VDS off-grid (interpolation exercised)"
    python3 lut_regen/spot_check.py luts/$D.mat $D --mode offgrid --seed 12
    echo; echo "##### B2w. weak inversion off-grid (ID<1uA allowed; interpolating an exponential on a 25 mV grid: few % EXPECTED, informative)"
    python3 lut_regen/spot_check.py luts/$D.mat $D --mode offgrid --seed 14 --min-id 0 --tol 10
    echo; echo "##### B3. fact 9: L midway between grid nodes (informative; large errors EXPECTED)"
    python3 lut_regen/spot_check.py luts/$D.mat $D --mode lmid --seed 13 --tol 5
  done
  for D in nfet_03v3 pfet_03v3; do
    for C in "ss 125 ss_125C" "ff -40 ff_n40C"; do
      set -- $C
      if [ -f luts/${D}_$3.mat ]; then
        echo; echo "##### C. corner LUT spot check $D $1 $2C"
        python3 lut_regen/spot_check.py luts/${D}_$3.mat $D --mode grid --seed 21 --corner $1 --temp $2
      fi
    done
  done
  echo; echo "##### D. facts check on regenerated tables"
  python3 lut_regen/facts_check.py luts
  echo; echo "##### E. sizing self-test on regenerated tables (GF180_LUT_DIR=luts)"
  GF180_LUT_DIR=$PWD/luts python3 sizing/selftest_gmid.py
} > $R 2>&1
grep -E "^(#####|WORST|[0-9]+/[0-9]+ checks)" $R
