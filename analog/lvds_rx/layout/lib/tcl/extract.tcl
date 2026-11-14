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
# FLAT=1 (T10): extract a flattened copy (cell ${cell}_flat).  For parasitics of a hierarchical cell: a hierarchical netlist
# would need coupling capacitors between nodes of different subcell instances, which a SPICE netlist cannot express.
if {[info exists env(FLAT)] && $env(FLAT) eq "1"} {
    expand
    flatten ${cell}_flat
    load ${cell}_flat
    set cell ${cell}_flat
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
