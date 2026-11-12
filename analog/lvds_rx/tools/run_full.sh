#!/bin/bash
# run `make full` with a log (results/full_run.log, gitignored via *.log); usage: tools/cx tools/run_full.sh
cd "$(dirname "$0")/.." || exit 1
mkdir -p .scratch
date +%s > .scratch/full_start
make full > results/full_run.log 2>&1
echo "EXIT $?" >> results/full_run.log
date +%s > .scratch/full_end
