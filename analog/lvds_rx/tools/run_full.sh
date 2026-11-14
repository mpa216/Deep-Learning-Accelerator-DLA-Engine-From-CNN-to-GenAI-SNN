#!/bin/bash
# The `make full` sequence with a log (results/full_run.log, gitignored via *.log) and an explicit job count.
# usage: tools/cx bash tools/run_full.sh [jobs]          (default 4: the owner's limit of 4 parallel simulations)
# T11: make full passes no --jobs (flow/run_all.py defaults to 6), and stops at the first failing gate before the report;
# here the env check must pass, then the full tier runs, and mutants + report always follow.  Ends with "EXIT <code of the full tier>".
cd "$(dirname "$0")/.." || exit 1
JOBS="${1:-4}"
mkdir -p .scratch
date +%s > .scratch/full_start
{
  python3 flow/envcheck.py && python3 flow/run_all.py --tier smoke --phases env || { echo "EXIT 2 (env check failed)"; exit 2; }
  python3 flow/run_all.py --tier full --phases env,prelayout --jobs "$JOBS"
  rc=$?
  python3 flow/mutants.py
  python3 flow/report.py
  echo "EXIT $rc"
} > results/full_run.log 2>&1
date +%s > .scratch/full_end
