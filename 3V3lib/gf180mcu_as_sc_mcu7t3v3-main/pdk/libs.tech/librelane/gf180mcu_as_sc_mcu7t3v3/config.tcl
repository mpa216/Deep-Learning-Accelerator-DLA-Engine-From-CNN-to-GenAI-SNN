set current_folder [file dirname [file normalize [info script]]]
# Technology lib

set ::env(LIB) [dict create]
dict set ::env(LIB) *_tt_025C_3v30 "\
    $::env(PDK_ROOT)/$::env(PDK)/libs.ref/$::env(STD_CELL_LIBRARY)/lib/$::env(STD_CELL_LIBRARY)__tt_025C_3v30.lib\
"
dict set ::env(LIB) *_ff_n40C_3v60 "\
    $::env(PDK_ROOT)/$::env(PDK)/libs.ref/$::env(STD_CELL_LIBRARY)/lib/$::env(STD_CELL_LIBRARY)__ff_n40C_3v60.lib\
"
dict set ::env(LIB) *_ss_125C_3v00 "\
    $::env(PDK_ROOT)/$::env(PDK)/libs.ref/$::env(STD_CELL_LIBRARY)/lib/$::env(STD_CELL_LIBRARY)__ss_125C_3v00.lib\
"

# APIC_A CHANGE (2026-07-03, ported to this source 2026-07-04): also register
# the gf180mcu_fd_io pad-cell liberty at each corner. Without it, OpenSTA links
# pad instances (in_c/in_s/bi_24t/...) as empty blackboxes, so a padring SDC's
# clock source pin (`clk_pad/Y`) does not exist in STA's view -> create_clock
# silently degrades to a VIRTUAL clock -> every register path is unconstrained
# and setup/hold "worst slack" reads +infinity at all 9 corners (hollow
# signoff; observed on the first full Stage 2 run, `Virtual: yes` in
# clock.rpt). The fd_io lib family is characterized per CORE-side VDD voltage;
# the 3v30/2v97/3v63 sets match this 3.3V core rail (2v97/3v63 are the
# nominal-±10% corners; our corner names say 3v00/3v60 -- nearest-available
# characterization, same convention as the SRAM corner matching). Every cell
# in these libs carries dont_use:true, so synthesis/resizer optimization
# cannot pick pad cells. Guarded per-file because some PDK distributions ship
# without the fd_io liberty; pad timing only matters for padring (Stage 2)
# designs, so skipping silently is correct for core-only flows.
foreach {_apic_corner _apic_fdlib} {
    *_tt_025C_3v30 gf180mcu_fd_io__tt_025C_3v30.lib
    *_ff_n40C_3v60 gf180mcu_fd_io__ff_n40C_3v63.lib
    *_ss_125C_3v00 gf180mcu_fd_io__ss_125C_2v97.lib
} {
    set _apic_path "$::env(PDK_ROOT)/$::env(PDK)/libs.ref/gf180mcu_fd_io/lib/$_apic_fdlib"
    if {[file exists $_apic_path]} {
        dict set ::env(LIB) $_apic_corner "[dict get $::env(LIB) $_apic_corner] $_apic_path"
    }
}

set ::env(STA_CORNERS) "nom_tt_025C_3v30 min_tt_025C_3v30 max_tt_025C_3v30 nom_ff_n40C_3v60 min_ff_n40C_3v60 max_ff_n40C_3v60 nom_ss_125C_3v00 min_ss_125C_3v00 max_ss_125C_3v00"
set ::env(DEFAULT_CORNER) "nom_tt_025C_3v30"

# Required by LibreLane >=3.0; not auto-derived here because this config sets
# ::env(LIB) directly instead of the legacy LIB_SYNTH/LIB_SLOWEST/LIB_FASTEST
# vars that the PDK compat shim keys its auto-derivation off of.
set ::env(TIMING_VIOLATION_CORNERS) "*tt*"

# The PDK-wide libs.tech/librelane/config.tcl hardcodes the exclusion-list
# filename as no_synth.cells for every std cell library, but this lib ships
# the same content as synth_exclude.cells -- override explicitly.
set ::env(SYNTH_EXCLUDED_CELL_FILE) "$::env(PDK_ROOT)/$::env(PDK)/libs.tech/librelane/$::env(STD_CELL_LIBRARY)/synth_exclude.cells"

# MUX2 mapping
set ::env(SYNTH_MUX_MAP) "$::env(PDK_ROOT)/$::env(PDK)/libs.tech/librelane/$::env(STD_CELL_LIBRARY)/mux2_map.v"

# Placement site for core cells
# This can be found in the technology lef
set ::env(PLACE_SITE) "unithd"
set ::env(PLACE_SITE_WIDTH) 0.56
set ::env(PLACE_SITE_HEIGHT) 3.92

# welltap and endcap cell
set ::env(WELLTAP_CELL) "$::env(STD_CELL_LIBRARY)__tap_2"
set ::env(ENDCAP_CELL) "$::env(STD_CELL_LIBRARY)__tap_2"

# defaults (can be overridden by designs):
set ::env(SYNTH_DRIVING_CELL) "$::env(STD_CELL_LIBRARY)__inv_2/Y"
set ::env(SYNTH_CLK_DRIVING_CELL) "$::env(STD_CELL_LIBRARY)__inv_4/Y"

set ::env(OUTPUT_CAP_LOAD) "72.91" ; # femtofarad from pin I in liberty file
set ::env(SYNTH_BUFFER_CELL) "$::env(STD_CELL_LIBRARY)__buff_2/A/Y"
set ::env(SYNTH_TIEHI_CELL) "$::env(STD_CELL_LIBRARY)__tieh_4/ONE"
set ::env(SYNTH_TIELO_CELL) "$::env(STD_CELL_LIBRARY)__tiel_4/ZERO"

# Fillcell insertion
set ::env(FILL_CELLS) "$::env(STD_CELL_LIBRARY)__fill_*"
set ::env(DECAP_CELLS) "$::env(STD_CELL_LIBRARY)__fillcap_*"

# Diode Insertion
set ::env(DIODE_CELL) "$::env(STD_CELL_LIBRARY)__diode_2/DIODE"

set ::env(CELL_PAD_EXCLUDE) "$::env(STD_CELL_LIBRARY)__tap_2 $::env(STD_CELL_LIBRARY)__fill_*"

# TritonCTS configurations
set ::env(CTS_ROOT_BUFFER) "$::env(STD_CELL_LIBRARY)__clkbuff_12"
set ::env(CTS_CLK_BUFFER_LIST) "$::env(STD_CELL_LIBRARY)__clkbuff_4 $::env(STD_CELL_LIBRARY)__clkbuff_8 $::env(STD_CELL_LIBRARY)__clkbuff_12"

set ::env(FP_PDN_RAIL_WIDTH) 0.6

set ::env(MAX_TRANSITION_CONSTRAINT) 1.5
set ::env(MAX_FANOUT_CONSTRAINT) 9
set ::env(MAX_CAPACITANCE_CONSTRAINT) 0.2

set ::env(GPL_CELL_PADDING) {0}
set ::env(DPL_CELL_PADDING) {0}

set ::env(TRISTATE_CELLS) "$::env(STD_CELL_LIBRARY)__invz*"
