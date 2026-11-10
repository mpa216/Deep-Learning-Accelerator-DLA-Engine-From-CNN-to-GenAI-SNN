#!/bin/bash
# e08_sak_help.sh -- print usage of the sak helper scripts and what they invoke underneath.
for f in sak-drc.sh sak-lvs.sh sak-pex.sh sak-sch2svg.sh; do
  echo "################ $f -h"
  /foss/tools/sak/$f -h 2>&1 | head -60
done
echo "################ tools invoked by the scripts"
grep -n -E "magic |klayout |netgen |ngspice |python|run_drc|run_lvs|run_pex|kpex|xschem |-rcfile|setup\.tcl|\.lylvs|\.lydrc|\.lyp" /foss/tools/sak/sak-drc.sh /foss/tools/sak/sak-lvs.sh /foss/tools/sak/sak-pex.sh /foss/tools/sak/sak-sch2svg.sh | grep -v "^.*:[0-9]*:\s*#" | cut -c1-220 | head -80
