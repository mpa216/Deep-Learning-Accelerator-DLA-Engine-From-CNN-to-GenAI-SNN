#!/bin/bash
P=/foss/pdks/gf180mcuD/libs.tech
echo "== magic tech lines 36-70"; sed -n 36,70p $P/magic/gf180mcuD.tech
echo "== tech DNWELL region 580-590, 810-820, 1340-1405"; sed -n 580,590p $P/magic/gf180mcuD.tech; sed -n 1340,1405p $P/magic/gf180mcuD.tech
echo "== gencell proc list"; grep -n '^proc gf180mcu::' $P/magic/gf180mcuD.tcl | head -80
echo "== nfet_03v3 defaults + params"; grep -n -A25 'proc gf180mcu::nfet_03v3_defaults' $P/magic/gf180mcuD.tcl | head -50
echo "== klayout fet.py params"; grep -n 'self.param' $P/klayout/tech/pymacros/cells/fet.py | head -40
echo "== DRC DN rules"; grep -n -i "'DN\.\|DN\.[0-9]" $P/klayout/tech/drc/rule_decks/*.drc | head -20
