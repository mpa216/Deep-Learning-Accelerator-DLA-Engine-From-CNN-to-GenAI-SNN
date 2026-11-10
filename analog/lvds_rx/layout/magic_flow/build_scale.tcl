# build_scale.tcl -- scaling experiment: NROWS identical ABBA input-pair rows (env NROWS, default 34) = 34 x 6 = 204 transistors,
# each row with its own gate straps, S/D tracks and dummy fingers.  Not a meaningful circuit; used only to time the flow
# (build, Magic DRC, KLayout deck, extraction) at the size of the real macro.  Run via scripts/scale_test.sh
source $env(MF)/lib/lf.tcl
set N [expr {[info exists env(NROWS)] ? $env(NROWS) : 34}]
lf::start lf_scale_dev
set TOFF 1.25
for {set k 0} {$k < $N} {incr k} {
    lf::mos_row R$k n 4.0 0.5 {d1 A B B A d2} cx 0 cy [expr {$k * 10.0}] toff $TOFF \
        gnet {d1 VSS A INP B INN d2 VSS} gside {d1 bot A top B bot d2 bot} \
        rnet {VSS N1 TAIL OUT TAIL N1 VSS} tracks {OUT {top 0} N1 {top 1} TAIL {bot 0}}
}
lf::flatten_devices lf_scale
for {set k 0} {$k < $N} {incr k} { lf::mos_wire R$k }
select top cell
drc check
drc catchup
set total 0
foreach item [drc listall count] { incr total [lindex $item 1] }
puts "DRCCOUNT $total"
foreach {txt boxes} [drc listall why] { puts "DRCWHY $txt : [llength $boxes] boxes: [lindex $boxes 0]" }
writeall force
gds write lf_scale.gds
quit -noprompt
