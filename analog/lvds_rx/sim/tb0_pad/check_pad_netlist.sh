#!/bin/bash
# Compare the device lines of netlist/pad_asig_5p0.spice with the PDK's own ngspice netlist of the same cell
# (case-insensitive, whitespace-normalised).  Prints OK/DIFF.  Run via tools/cx from analog/lvds_rx.
cd "$(dirname "$0")/../.." || exit 1     # works from any directory
P=/foss/pdks/gf180mcuD/libs.ref/gf180mcu_fd_io/spice/gf180mcu_fd_io.spice
awk 'tolower($0) ~ /^\.subckt gf180mcu_fd_io__asig_5p0 /,tolower($0) ~ /^\.ends/' $P | grep -v '^\.' | tr 'A-Z' 'a-z' | tr -s ' ' | sort > /tmp/pad_pdk.txt
awk 'tolower($0) ~ /^\.subckt gf180mcu_fd_io__asig_5p0 /,tolower($0) ~ /^\.ends/' netlist/pad_asig_5p0.spice | grep -v '^\.' | tr 'A-Z' 'a-z' | tr -s ' ' | sort > /tmp/pad_mine.txt
if diff -q /tmp/pad_pdk.txt /tmp/pad_mine.txt >/dev/null; then echo "pad netlist device lines: IDENTICAL to PDK spice ($(wc -l < /tmp/pad_mine.txt) devices)"; else echo DIFF; diff /tmp/pad_pdk.txt /tmp/pad_mine.txt; fi
