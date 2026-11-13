#!/bin/bash
# Detached partial regression: full tier, selected gates only.
# usage: tools/cx bash tools/run_only.sh <comma-separated gates> <jobs> [tag]
# Ends by appending "EXIT <code>" to results/<tag>_run.log.
cd "$(dirname "$0")/.." || exit 1
GATES="$1"
JOBS="${2:-4}"
TAG="${3:-partial}"
LOG="results/${TAG}_run.log"
mkdir -p .scratch
date +%s > ".scratch/${TAG}_start"
python3 flow/run_all.py --tier full --phases prelayout --only "$GATES" --jobs "$JOBS" > "$LOG" 2>&1
echo "EXIT $?" >> "$LOG"
date +%s > ".scratch/${TAG}_end"
