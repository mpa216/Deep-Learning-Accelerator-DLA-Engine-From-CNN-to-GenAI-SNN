# build_selftest.tcl -- exercises the library primitives that the toy cell does not use directly:
# lf::tap (p-tap and n-well tap), lf::via1/via2 stacks, lf::hwire/vwire on M1/M2/M3, lf::pin, and a ring around a
# single-row device with a different pattern (an interdigitated ABAB PMOS pair with common source).
# Run:  bash scripts/build.sh build_selftest.tcl   then drc_magic.sh / drc_klayout.sh on work/lf_selftest.*
source $env(MF)/lib/lf.tcl
lf::start lf_selftest_dev
# a PMOS pair, ABAB pattern: A and B alternate, sources shared between neighbours is NOT possible with ABAB and
# alternating S/D, so give each finger its own region nets: just test placement + ring + wiring DRC
lf::mos_row Q p 2.0 0.5 {A B A B} cx 0 cy 0 gnet {A GA B GB} gside {A top B bot} \
    rnet {D1 S1 D1 S1 D1} tracks {D1 {top 0} S1 {bot 0}}
lf::flatten_devices lf_selftest
lf::mos_wire Q
set bx1 [expr {$lf::R(Q,x1) + 0.43 - 0.5}]
set bx2 [expr {$lf::R(Q,x2) - 0.43 + 0.5}]
set by1 [expr {$lf::R(Q,padyb) - 1.25 - 0.14 - 0.5}]
set by2 [expr {$lf::R(Q,padyt) + 1.25 + 0.14 + 0.5}]
set ring [lf::ring p $bx1 $by1 $bx2 $by2]
# stand-alone taps, well apart from the n-well
lf::tap n -6.0 0.0
lf::tap n -6.0 3.0
lf::tap p 8.0 0.0
# via stacks and straight wires
lf::hwire m1 -6.0 -6.0 -4.0 0.23
lf::via1 -4.0 -6.0
lf::hwire m2 -6.0 -4.0 -1.0 0.28
lf::via2 -1.0 -6.0
lf::vwire m3 -1.0 -6.0 -9.0 0.4
lf::pin SELFPIN m3 -1.0 -9.0
select top cell
drc check
drc catchup
set total 0
foreach item [drc listall count] { incr total [lindex $item 1] }
puts "DRCCOUNT $total"
foreach {txt boxes} [drc listall why] { puts "DRCWHY $txt : [llength $boxes] boxes: [lindex $boxes 0]" }
writeall force
gds write lf_selftest.gds
quit -noprompt
