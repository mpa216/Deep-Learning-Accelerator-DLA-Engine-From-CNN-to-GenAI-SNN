#!/bin/bash
# Re-run every harness self-test from a clean state (about 3 minutes with 6 jobs).
# From the host:
#   docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx bash sim/harness_demo/run_demo.sh
# Exit code 0 if the unit tests and the three Monte Carlo mechanism checks pass; the demo testbench
# specs are allowed to report FAIL (their limits are demo values), they only have to RUN (status ok).
cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 1       # analog/lvds_rx
rm -rf sim/harness_demo/results sim/harness_demo/pelgrom_n1000.json
rc=0
echo "== unit tests"
python3 -m unittest discover -s sim/harness/tests > /tmp/harness_unittest.log 2>&1; ut=$?
tail -3 /tmp/harness_unittest.log
[ $ut -eq 0 ] || rc=1
echo "== corners demo";              python3 sim/harness/cli.py run sim/harness_demo/ota_cmp_corners.json
echo "== PRBS eye demo";             python3 sim/harness/cli.py run sim/harness_demo/ota_cmp_eye.json
echo "== MC demo (mismatch)";        python3 sim/harness/cli.py run sim/harness_demo/ota_cmp_mc.json
echo "== MC demo (global+mismatch)"; python3 sim/harness/cli.py run sim/harness_demo/ota_cmp_global.json
echo "== Pelgrom campaign (2400 runs)"; python3 sim/harness/cli.py run sim/harness_demo/pelgrom_pair.json
echo "== Pelgrom check";            python3 sim/harness_demo/check_pelgrom.py | tail -4
echo "== reproducibility/cache/independence"; python3 sim/harness_demo/check_repro.py || rc=1
echo "== in-deck loop check";       python3 sim/harness_demo/mc_loop_check.py || rc=1
exit $rc
