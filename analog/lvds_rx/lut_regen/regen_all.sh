#!/bin/bash
# regen_all.sh - regenerate EVERY LUT with one command (run through tools/cx, i.e. inside the container):
#
#   docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx bash lut_regen/regen_all.sh [typical|corners|all]
#
# typical : nfet_03v3.mat + pfet_03v3.mat  (corner typical, 27 C, VSB 0..2.0 V in 0.2 V steps, 12 L values)
# corners : nfet/pfet_03v3_ss_125C.mat and _ff_n40C.mat (7 L values, VSB 0..0.8 V)
# all     : both (default), then validation (validate_all.sh) -> lut_regen/validation_report.txt
# Time (measured here, one sweep per core, machine otherwise idle): ~15.5 min per typical sweep,
# ~4.3 min per corner sweep.  Disk: the raw sweep text is ~1 GB for a typical sweep; it is deleted
# right after conversion, so peak usage is ~1 GB per running job.  At most 3 jobs run in parallel.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
WHAT="${1:-all}"
python3 make_decks.py > /dev/null || exit 1
mkdir -p ../luts work

run() {  # deck corner temp outname
  bash "$HERE/run_sweep.sh" "$1" "$2" "$3" "$4" > "$HERE/work/$4.runlog" 2>&1 \
    && echo "OK   $4" || echo "FAIL $4 (see work/$4.runlog)"
}
export -f run; export HERE

JOBS=()
if [ "$WHAT" = typical ] || [ "$WHAT" = all ]; then
  JOBS+=("techsweep_nfet_03v3_typical_27C_vsb2 NOM 27 nfet_03v3"
         "techsweep_pfet_03v3_typical_27C_vsb2 NOM 27 pfet_03v3")
fi
if [ "$WHAT" = corners ] || [ "$WHAT" = all ]; then
  JOBS+=("techsweep_nfet_03v3_ss_125C_vsb08 SS 125 nfet_03v3_ss_125C"
         "techsweep_pfet_03v3_ss_125C_vsb08 SS 125 pfet_03v3_ss_125C"
         "techsweep_nfet_03v3_ff_-40C_vsb08 FF -40 nfet_03v3_ff_n40C"
         "techsweep_pfet_03v3_ff_-40C_vsb08 FF -40 pfet_03v3_ff_n40C")
fi
printf '%s\n' "${JOBS[@]}" | xargs -P 3 -L 1 bash -c 'run $0 $1 $2 $3'
[ "$WHAT" = all ] && bash "$HERE/validate_all.sh"
exit 0
