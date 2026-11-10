# lone_gencell.tcl -- why does a lone Magic gencell nfet report "8 DRC errors"?   (called by lone_gencell.sh)
# Builds the same nfet three ways and counts DRC errors IN the Magic session:
#   lone_g1  : gencell nfet W=4 L=0.5 nf=4 guard 1, as generated (sub-cell instance)                   -> 8 (M1.3)
#   lone_flat: the same, flattened into one cell                                                      -> ?
#   lone_gds : written to GDS and read back (what sak-drc.sh -m and the foundry deck see)             -> 0
proc report {tag} {
    select top cell
    drc check
    drc catchup
    set total 0
    foreach item [drc listall count] { incr total [lindex $item 1] }
    puts "LONE $tag in-session DRC total = $total"
    foreach {txt boxes} [drc listall why] { puts "LONE   $tag rule: $txt  ([llength $boxes] boxes)" }
}
cellname rename (UNNAMED) lone_g1
box values 0um 0um 0um 0um
magic::gencell gf180mcu::nfet_03v3 M1 w 4.0 l 0.5 nf 4 guard 1
report "gencell-instance"
flatten lone_flat
load lone_flat
report "flattened"
gds write lone_flat.gds
quit -noprompt
