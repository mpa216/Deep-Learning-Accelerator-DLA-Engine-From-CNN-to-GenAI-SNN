# drc_magic.tcl -- Magic DRC of a cell.   Environment: CELL (top cell), SRC = path of the .mag directory OR of a .gds file,
# OUT = report file (default drc_magic.rpt).  Prints "MAGIC_DRC_TOTAL <n>" and one line per rule with its error boxes (um).
set cell $env(CELL)
set src  $env(SRC)
set out  [expr {[info exists env(OUT)] ? $env(OUT) : "drc_magic.rpt"}]
if {[string match *.gds $src]} {
    gds readonly true
    gds read $src
    load $cell
} else {
    addpath $src
    load $cell
}
select top cell
drc style drc(full)
drc check
drc catchup
set total 0
foreach item [drc listall count] { incr total [lindex $item 1] }
set fp [open $out w]
puts $fp "cell $cell source $src"
puts $fp "MAGIC_DRC_TOTAL $total"
foreach {txt boxes} [drc listall why] {
    set nb [llength $boxes]
    puts $fp "RULE ($nb) $txt"
    set k 0
    foreach bx $boxes {
        lassign $bx a b c d
        puts $fp [format "    box um: %.3f %.3f %.3f %.3f" [expr {$a*0.005}] [expr {$b*0.005}] [expr {$c*0.005}] [expr {$d*0.005}]]
        if {[incr k] >= 6} break
    }
}
close $fp
puts "MAGIC_DRC_TOTAL $total"
quit -noprompt
