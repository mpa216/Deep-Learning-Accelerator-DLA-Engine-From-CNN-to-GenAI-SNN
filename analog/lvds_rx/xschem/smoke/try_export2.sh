#!/bin/bash
# try_export2.sh -- headless image export WITH a virtual display and a hard timeout per try.
# (the first attempt, try_export.sh variants D/E/F, hung forever under xvfb-run; see try_export_output.txt)
# Run through tools/cx from analog/lvds_rx.  Never use the kit's xschemrc (it overwrites kit files).
RC=/foss/pdks/gf180mcuD/libs.tech/xschem/xschemrc
W=xschem/smoke/work
S=$W/kit_techsweep.sch
mkdir -p $W/img2
try() { name=$1; shift; echo "== $name"; echo "   cmd: $*"; timeout 60 "$@" >$W/img2/$name.log 2>&1; echo "   rc=$?"; ls -la $W/img2 | grep "$name\." ; head -3 $W/img2/$name.log | cut -c1-160; }
try v1 xvfb-run -a -s "-screen 0 1280x1024x24" xschem --rcfile $RC --png --plotfile $W/img2/v1.png -q $S
try v2 xvfb-run -a -s "-screen 0 1280x1024x24" xschem --rcfile $RC --svg --plotfile $W/img2/v2.svg -q $S
try v3 xvfb-run -a -s "-screen 0 1280x1024x24" xschem --rcfile $RC --command "xschem zoom_full; xschem print svg $W/img2/v3.svg; xschem exit closewindow force" $S
try v4 xvfb-run -a -s "-screen 0 1280x1024x24" xschem --rcfile $RC --command "xschem zoom_full; xschem print png $W/img2/v4.png 1000 700; xschem exit closewindow force" $S
try v5 xschem --rcfile $RC -x -q --command "xschem zoom_full; xschem print svg $W/img2/v5.svg" $S
try v6 xschem --rcfile $RC -x -q --svg --plotfile $W/img2/v6.svg $S
