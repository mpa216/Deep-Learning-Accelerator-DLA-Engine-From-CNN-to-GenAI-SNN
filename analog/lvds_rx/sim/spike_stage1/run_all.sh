#!/bin/bash
# run the three stage-1 spike variants over all corners, then aggregate (inside the container, from analog/lvds_rx):
#   docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx bash sim/spike_stage1/run_all.sh [--force]
set -e
for v in A H0 H1; do
  python3 sim/harness/cli.py run sim/spike_stage1/spike_$v.json --jobs 6 "$@" | tail -2
done
python3 sim/spike_stage1/analyze.py
