#!/bin/bash
# negctl.sh  negative controls: break the toy layout three ways and check that the checkers notice.
#   sliver -> Magic DRC and KLayout deck must report > 0;  short, open -> LVS must say NOT CLEAN.
# Needs a finished run (work/lf_toy.gds from run_all.sh).  Output: work/negctl/*, summary lines "NEGCTL ...".
MF="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
S="$MF/scripts"; N="$MF/work/negctl"; rm -rf "$N"; mkdir -p "$N"
G="$MF/work/lf_toy.gds"
for k in sliver short open; do python3 "$S/negctl.py" "$G" lf_toy $k "$N/$k.gds"; done
echo "NEGCTL sliver magic: $(bash "$S/drc_magic.sh" lf_toy "$N/sliver.gds" "$N/sliver_magic.rpt" | grep -m1 MAGIC_DRC_TOTAL)"
echo "NEGCTL sliver klayout: $(bash "$S/drc_klayout.sh" "$N/sliver.gds" lf_toy "$N/sliver_kl" | grep KLAYOUT_DRC_MAIN)"
for k in short open; do
  echo "NEGCTL $k lvs: $(bash "$S/lvs.sh" lf_toy "$N/$k.gds" "$MF/toy.spice" | grep LVS_RESULT)"
done
