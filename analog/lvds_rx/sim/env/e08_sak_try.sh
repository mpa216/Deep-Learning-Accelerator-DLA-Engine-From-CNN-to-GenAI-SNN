#!/bin/bash
# e08_sak_try.sh -- do sak-drc.sh / sak-lvs.sh / sak-pex.sh work for gf180mcuD on a tiny cell?
# Cell = the PDK standard cell inv_1 (7-track 5 V library): known-good layout + schematic.
# Run through tools/cx from analog/lvds_rx.   Work dir: sim/env/sak_smoke (regenerable, gitignored via sim/**/work? no -> kept small)
L=/foss/pdks/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0
C=gf180mcu_fd_sc_mcu7t5v0__inv_1
W=sim/env/sak_smoke/work
rm -rf $W; mkdir -p $W; cd $W
cp $L/mag/$C.mag .
# the schematic netlist of just this cell, cut out of the library SPICE file
awk -v c="$C" 'BEGIN{IGNORECASE=1} /^\.subckt/ {p=($2==c)} p {print} /^\.ends/ {p=0}' $L/spice/gf180mcu_fd_sc_mcu7t5v0.spice > $C.spice
echo "== schematic netlist"; cat $C.spice
cp ../../../../.scratch/smoke/smoke_top.gds nfetgen.gds 2>/dev/null && echo "(copied nfet gencell gds)"
echo "PDK=$PDK PDK_ROOT=$PDK_ROOT STD_CELL_LIBRARY=$STD_CELL_LIBRARY"

echo; echo "##### sak-drc.sh -m (Magic DRC) on $C"
timeout 300 sak-drc.sh -m -d $C 2>&1 | tail -15
echo; echo "##### sak-drc.sh -k (KLayout DRC) on $C"
timeout 300 sak-drc.sh -k $C 2>&1 | tail -6
echo; echo "##### sak-drc.sh -m on the Magic gencell nfet gds (nfetgen)"
timeout 300 sak-drc.sh -m nfetgen 2>&1 | tail -8

echo; echo "##### sak-lvs.sh  (layout .mag vs spice)"
timeout 300 sak-lvs.sh -s $C.spice -l $C.mag -c $C 2>&1 | tail -25
echo; echo "##### result files"; ls -la
echo; echo "##### netgen comparison summary"
grep -h -i -E "Circuits match|do not match|Final result|uniquely|mismatch" *lvs*.out comp.out 2>/dev/null | head

echo; echo "##### sak-pex.sh -m 2  (parasitic extraction)"
timeout 300 sak-pex.sh -m 2 $C 2>&1 | tail -15
ls -la | head -40
