#!/usr/bin/env bash
# Validate the hand-written SDCs by re-running STA on the routed netlists.
# Run INSIDE the apic_headless container from /foss/designs:
#   docker exec apic_headless bash -lc 'cd /foss/designs && bash constraints/validate_sdc.sh'
set -euo pipefail
cd "$(dirname "$0")/.."

STD=3V3lib/gf180mcu_as_sc_mcu7t3v3-main/pdk/libs.ref/gf180mcu_as_sc_mcu7t3v3/lib/gf180mcu_as_sc_mcu7t3v3__tt_025C_3v30.lib
SRAM=gf180mcu_ocd_ip_sram__sram256x8m8wm1/gf180mcu_ocd_ip_sram__sram256x8m8wm1__tt_025C_3v30.lib

run () {  # name  netlist  top  sdc
  echo "############################################################"
  echo "# Validating $1 against $4"
  echo "############################################################"
  LIB_STD="$STD" LIB_SRAM="$SRAM" DESIGN_NL="$2" DESIGN_TOP="$3" DESIGN_SDC="$4" \
    sta -no_init -exit constraints/validate_sdc.tcl
  echo ""
}

run "dla_engine_top (core)" \
    librelane/runs/longtin_a3b_d50/final/nl/dla_engine_top.nl.v \
    dla_engine_top \
    constraints/dla_engine_top.sdc

run "dla_engine_chip (chip)" \
    verilog/dla_engine_chip.nl.v \
    dla_engine_chip \
    constraints/dla_engine_chip.sdc
