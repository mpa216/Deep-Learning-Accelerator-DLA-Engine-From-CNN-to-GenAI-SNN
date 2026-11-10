#!/bin/bash
# try_netlist.sh -- can xschem netlist the kit schematic headlessly?  (run through tools/cx, from analog/lvds_rx)
K=/foss/designs/Analog/starter_files_open_source_tools/gf180mcuD
OUT=xschem/smoke/netlist_kit
rm -rf $OUT; mkdir -p $OUT
echo "== kit xschemrc (read only, NOT used)"; cat $K/xschemrc
echo "== which"; which xschem Xvfb xvfb-run 2>&1
echo "== DISPLAY=[$DISPLAY]"
echo
echo "== TRY 1: xschem -x -q -n -s --netlist_path (no rcfile)"
xschem -x -q -n -s --netlist_path $OUT/t1 $K/techsweep_nfet_03v3.sch ; echo "rc=$?"; ls -la $OUT/t1 2>&1 | head
echo
# TRY 2 (kit xschemrc) REMOVED: that rcfile sets local_netlist_dir=1 and xschem then overwrites
# the kit's own simulation/techsweep_nfet_03v3.spice (read-only reference folder). Never pass it.
echo
echo "== TRY 3: with PDK xschemrc"
mkdir -p $OUT/t3
xschem --rcfile /foss/pdks/gf180mcuD/libs.tech/xschem/xschemrc -x -q -n -s --netlist_path $OUT/t3 $K/techsweep_nfet_03v3.sch ; echo "rc=$?"; ls -la $OUT/t3 2>&1 | head
