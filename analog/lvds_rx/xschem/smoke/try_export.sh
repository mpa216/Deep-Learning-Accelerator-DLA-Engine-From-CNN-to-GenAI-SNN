#!/bin/bash
# try_export.sh -- headless SVG/PNG/PDF export and netlisting with a LOCAL COPY of the kit schematic.
# NEVER pass the kit's own xschemrc: it sets local_netlist_dir=1 and then netlists INTO the kit's simulation/ folder.
# Run through tools/cx from analog/lvds_rx.
K=/foss/designs/Analog/starter_files_open_source_tools/gf180mcuD
RC=/foss/pdks/gf180mcuD/libs.tech/xschem/xschemrc
W=xschem/smoke/work
rm -rf $W; mkdir -p $W/net $W/img
cp $K/techsweep_nfet_03v3.sch $W/kit_techsweep.sch

echo "== A: netlist, local copy, PDK rcfile"
xschem --rcfile $RC -x -q -n -s -o $W/net $W/kit_techsweep.sch ; echo "rc=$?"; ls -la $W/net
echo "== diff TRY1 (no rc) vs TRY3 (pdk rc) netlists"
diff xschem/smoke/netlist_kit/t1/techsweep_nfet_03v3.spice xschem/smoke/netlist_kit/t3/techsweep_nfet_03v3.spice && echo "identical"

echo "== B: --svg with -x (no display)"
xschem --rcfile $RC -x -q --svg --plotfile $W/img/b.svg $W/kit_techsweep.sch ; echo "rc=$?"; ls -la $W/img
echo "== C: --png with -x (no display)"
xschem --rcfile $RC -x -q --png --plotfile $W/img/c.png $W/kit_techsweep.sch ; echo "rc=$?"; ls -la $W/img
echo "== D: --png under xvfb-run"
timeout 60 xvfb-run -a xschem --rcfile $RC -q --png --plotfile $W/img/d.png $W/kit_techsweep.sch ; echo "rc=$?"; ls -la $W/img
echo "== E: --svg under xvfb-run"
timeout 60 xvfb-run -a xschem --rcfile $RC -q --svg --plotfile $W/img/e.svg $W/kit_techsweep.sch ; echo "rc=$?"; ls -la $W/img
echo "== F: --pdf / --ps under xvfb-run"
timeout 60 xvfb-run -a xschem --rcfile $RC -q --ps --plotfile $W/img/f.ps $W/kit_techsweep.sch ; echo "rc=$?"; ls -la $W/img
