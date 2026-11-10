#!/bin/bash
P=/foss/pdks/gf180mcuD/libs.tech
echo "== magic tech layers with dnwell/dnw"; ls $P/magic/
grep -n -i 'dnwell\|dnw\b\|deep' $P/magic/gf180mcuD.tech | head -40
echo "== magic tcl device names (gencell)"; ls $P/magic/*.tcl 2>/dev/null
grep -n -i 'dnwell\|deep\|_dn\b\|dnw' $P/magic/*.tcl | head -30
echo "== klayout pcells with dnwell"; grep -rn -i 'dnwell\|deep' $P/klayout/tech/pymacros/cells/*.py | head -30
echo "== klayout layers"; grep -rn -i 'dnwell' $P/klayout/tech/*.lyp $P/klayout/tech/*.lyt 2>/dev/null | head -10
echo "== xschem symbol names with dn / deep"; ls $P/xschem/ ; ls $P/xschem/symbols 2>/dev/null | grep -i -E 'dn|deep|nfet|pfet'
echo "== ngspice models: any dnwell-related device?"; grep -n -i 'dnwell\|deep.nwell\|isolated' $P/ngspice/sm141064.ngspice | head
echo "== DRC deck rules for DNWELL"; ls $P/klayout/tech/drc/ | head -30; grep -n -i 'dnwell' $P/klayout/tech/drc/rule_decks/*.drc 2>/dev/null | head -20
echo "== Netgen setup device names with dnwell"; grep -n -i 'dnwell\|_dn' $P/netgen/gf180mcuD_setup.tcl | head
echo "== docs"; ls /foss/pdks/gf180mcuD/ ; ls /foss/pdks/gf180mcuD/libs.ref | head -30
