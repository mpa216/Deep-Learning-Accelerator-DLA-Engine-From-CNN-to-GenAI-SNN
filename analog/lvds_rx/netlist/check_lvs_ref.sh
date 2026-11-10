#!/bin/bash
# check_lvs_ref.sh -- Netgen self-consistency of the LVS reference: the hierarchical netlist (lvds_rx_lvs_ref.spice) against the flat one
# (lvds_rx_lvs_ref_flat.spice) must "match uniquely" with no property errors, and the device/net counts must agree.
# This proves the generator emits the same circuit twice (it does NOT compare against a layout: that is T9/T10).
#   docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx bash netlist/check_lvs_ref.sh
set -e
mkdir -p .scratch
netgen -batch lvs "netlist/lvds_rx_lvs_ref.spice lvds_rx_x3" "netlist/lvds_rx_lvs_ref_flat.spice lvds_rx_x3" \
    "$PDK_ROOT/$PDK/libs.tech/netgen/${PDK}_setup.tcl" .scratch/lvs_ref_selfcheck.out > .scratch/lvs_ref_selfcheck.log 2>&1
grep -E "Number of devices|Number of nets|Netlists match|Final result|property errors" .scratch/lvs_ref_selfcheck.out | sort -u
if grep -q "^Final result: Circuits match uniquely" .scratch/lvs_ref_selfcheck.out && grep -q "^Netlists match uniquely\.$" .scratch/lvs_ref_selfcheck.out \
   && ! grep -qi "property errors" .scratch/lvs_ref_selfcheck.out; then
    echo "LVS_REF_SELFCHECK: PASS"
else
    echo "LVS_REF_SELFCHECK: FAIL"; exit 1
fi
