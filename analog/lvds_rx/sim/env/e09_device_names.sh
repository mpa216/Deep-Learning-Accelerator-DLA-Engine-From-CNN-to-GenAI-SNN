#!/bin/bash
# e09_device_names.sh -- exact device names per tool (ngspice subckt, Magic gencell, Netgen setup, xschem symbol, KLayout PCell)
P=/foss/pdks/gf180mcuD/libs.tech
echo "### ngspice .subckt names (sm141064.ngspice + sm141064_*.ngspice)"
grep -h -i "^\.subckt" $P/ngspice/sm141064*.ngspice | awk '{print $2}' | sort -u | tr '\n' ' '; echo
echo "### ngspice .lib section names"
grep -h -i "^\.lib " $P/ngspice/sm141064.ngspice | awk '{print $2}' | sort -u | tr '\n' ' '; echo
echo "### Magic: gencell procs (xxx_defaults) in gf180mcuD.tcl"
grep -o "proc gf180mcu::[a-z0-9_]*_defaults" $P/magic/gf180mcuD.tcl | sed 's/proc gf180mcu:://; s/_defaults//' | tr '\n' ' '; echo
echo "### Magic: device names in the extract section (device lines)"
grep -n -E "^ *device " $P/magic/gf180mcuD.tech | awk '{print $3, $4}' | sort -u | tr '\n' ';' | cut -c1-1500; echo
echo "### Magic: all gencell-able names (find 'gencell' types in the .tech 'devices' / tcl 'Device Generator')"
grep -n -i "gencell\|devices" $P/magic/gf180mcuD.tcl | head -20 | cut -c1-160
echo "### Netgen setup: device/model names"
grep -n -E "lappend devices|property|equate classes" $P/netgen/gf180mcuD_setup.tcl | head -80 | cut -c1-140
echo "### KLayout PCell names (register_pcell / library entries)"
grep -rhn "layout.register_pcell\|register_pcell(" $P/klayout/tech/pymacros/cells/__init__.py | cut -c1-120 | head -60
