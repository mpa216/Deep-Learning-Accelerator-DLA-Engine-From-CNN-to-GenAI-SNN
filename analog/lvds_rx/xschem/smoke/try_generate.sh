#!/bin/bash
# try_generate.sh -- hand-written .sch (cs_stage.sch): netlist it, simulate the netlist, export SVG and PNG.
# Run through tools/cx from analog/lvds_rx.  Uses ONLY the PDK xschemrc (never the kit's).
RC=/foss/pdks/gf180mcuD/libs.tech/xschem/xschemrc
D=xschem/smoke
W=$D/work/gen
rm -rf $W; mkdir -p $W
cp $D/cs_stage.sch $W/cs_stage.sch
echo "== netlist (no display)"
xschem --rcfile $RC -x -q -n -s -o $W $W/cs_stage.sch; echo "rc=$?"
cat $W/cs_stage.spice
echo "== ngspice on the generated netlist"
ngspice -b $W/cs_stage.spice 2>&1 | grep -E "v\(out\)|i\(vdd\)|rror"
echo "== SVG, no display"
xschem --rcfile $RC -x -q --command "xschem zoom_full; xschem print svg $W/cs_stage.svg" $W/cs_stage.sch; echo "rc=$?"; ls -la $W/cs_stage.svg
echo "== PNG, virtual display"
timeout 90 xvfb-run -a -s "-screen 0 1280x1024x24" xschem --rcfile $RC --command "xschem zoom_full; xschem print png $W/cs_stage.png 800 600; xschem exit closewindow force" $W/cs_stage.sch; echo "rc=$?"; ls -la $W/cs_stage.png
