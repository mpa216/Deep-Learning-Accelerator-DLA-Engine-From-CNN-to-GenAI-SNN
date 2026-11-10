#!/bin/bash
# run_all.sh -- re-run every environment experiment and store its stdout in sim/env/results/.
# Run from analog/lvds_rx, inside the container:
#   docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx bash sim/env/run_all.sh
# xschem checks are separate: xschem/smoke/try_export.sh (netlist+svg; its D/E/F variants hang, kill them),
#   xschem/smoke/try_export2.sh, xschem/smoke/try_generate.sh
mkdir -p sim/env/results
ngspice -b -o sim/env/results/e01_header.txt sim/env/e01_header.spice
ngspice -b -o sim/env/results/e02b_junction.txt sim/env/e02b_junction.spice
ngspice -b -o sim/env/results/e02c_capbd.txt sim/env/e02c_capbd.spice
ngspice -b -o sim/env/results/e11_paste_check.txt sim/env/e11_paste_check.spice
for s in e01_variants e02_geometry e03_resistors e03b_term e04_diode_cap e05_vth_gmid e06_corners; do
  echo "=== $s"; date +%T
  python3 sim/env/$s.py > sim/env/results/$s.txt 2>&1; echo "rc=$?"
done
echo "=== e07 (PDK must be unset for the KLayout PCells)"
env -u PDK klayout -b -r sim/env/e07_klayout_dnwell.py > sim/env/results/e07_klayout_dnwell.txt 2>&1; echo "rc=$?"
bash sim/env/e07a_dnwell_grep.sh > sim/env/results/e07a.txt 2>&1
bash sim/env/e07b_dnwell_grep2.sh > sim/env/results/e07b.txt 2>&1
bash sim/env/e09_device_names.sh > sim/env/results/e09_device_names.txt 2>&1
bash sim/env/e08_sak_help.sh > sim/env/results/e08_sak_help.txt 2>&1
bash sim/env/e08_sak_try.sh > sim/env/results/e08_sak_try.txt 2>&1
mkdir -p .scratch/pdk-facts/e08b .scratch/pdk-facts/e10
(cd .scratch/pdk-facts/e08b && magic -dnull -noconsole -rcfile /foss/pdks/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc ../../../sim/env/e08b_gencell_drc.tcl) > sim/env/results/e08b_gencell_drc.txt 2>&1
(cd .scratch/pdk-facts/e10 && magic -dnull -noconsole -rcfile /foss/pdks/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc ../../../sim/env/e10_gencell_syntax.tcl) > sim/env/results/e10_gencell_syntax.txt 2>&1
echo done
