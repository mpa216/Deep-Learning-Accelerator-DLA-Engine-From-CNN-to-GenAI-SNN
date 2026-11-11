# extract.tcl -- Magic extraction to a SPICE netlist.
# Environment: CELL, SRC (directory with CELL.mag or a .gds), OUT (netlist path), MODE = lvs | pex_c | pex_rc
#   lvs    : devices and connectivity only (no parasitics), what Netgen needs
#   pex_c  : + parasitic capacitance to substrate and coupling caps between nets (cthresh 0 = keep all)
#   pex_rc : + wire resistance via "extresist" (slower; only for the nets you care about)
set cell $env(CELL)
set src  $env(SRC)
set out  $env(OUT)
set mode $env(MODE)
if {[string match *.gds $src]} {
    gds read $src
    load $cell
} else {
    addpath $src
    load $cell
}
select top cell
extract path ext_$mode
if {$mode eq "lvs"} {
    extract no capacitance
    extract no coupling
    extract no resistance
    extract no length
    extract all
    ext2spice lvs
    ext2spice subcircuit descend off
    ext2spice -p ext_$mode -o $out
} else {
    if {$mode eq "pex_rc"} {
        extract do resistance
        extract all
        ext2sim labels on
        extresist tolerance 10
        extresist all
        ext2spice lvs
        ext2spice extresist on
    } else {
        extract do capacitance
        extract do coupling
        extract all
        ext2spice lvs
    }
    ext2spice cthresh 0
    ext2spice rthresh 0
    ext2spice -p ext_$mode -o $out
}
puts "EXTRACT_DONE $out"
quit -noprompt
