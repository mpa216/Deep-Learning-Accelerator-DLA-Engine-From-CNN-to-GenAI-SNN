# build_toy.tcl -- builds the common toy cell lf_toy (5T OTA + resistor bias) with lib/lf.tcl.
# Run:  bash scripts/build.sh      (environment MF = absolute path of layout/magic_flow, set by build.sh)
#
# Flow: (1) place all generator devices   (2) flatten into one cell   (3) wire: pads, straps, tracks, rings, trunks, pins
source $env(MF)/lib/lf.tcl
lf::start lf_toy_dev
set CX 0.0
set TOFF 1.25

# ======================= phase 1: placement =======================================================
# N2: tail M5 / diode reference M6 (ABBA, gates all on IB, sources VSS shared)
lf::mos_row N2 n 4.0 1.0 {A B B A} cx $CX cy 0 toff $TOFF \
    gnet {A IB B IB} gside {A top B top} rnet {TAIL VSS IB VSS TAIL} \
    tracks {IB {top 0} VSS {top 1} TAIL {top 2}}
# N1: input pair M1 (A, gate INP) / M2 (B, gate INN): ABBA with a dummy finger d1/d2 at each end
set cy1 [expr {$lf::R(N2,padyt) + 2*$TOFF + 4.96}]
lf::mos_row N1 n 4.0 0.5 {d1 A B B A d2} cx $CX cy $cy1 toff $TOFF \
    gnet {d1 VSS A INP B INN d2 VSS} gside {d1 bot A top B bot d2 bot} \
    rnet {VSS N1 TAIL OUT TAIL N1 VSS} tracks {OUT {top 0} N1 {top 1} TAIL {bot 0}}
# P: mirror load M3 (A, diode connected) / M4 (B, output), sources VDD shared, in its own n-well
set ny2c [expr {$cy1 + 2.28 + $TOFF + 0.7 + 0.14 + 0.5}]
set cyp  [expr {$ny2c + 0.36 + 0.12 + 1.0 + 0.12 + 0.36 + 0.5 + 0.14 + $TOFF + 2.28}]
lf::mos_row P p 4.0 1.0 {A B B A} cx $CX cy $cyp toff $TOFF \
    gnet {A N1 B N1} gside {A bot B bot} rnet {N1 VDD OUT VDD N1} \
    tracks {N1 {bot 0} VDD {top 0}}

# ring boxes (inner edge of the ring diffusion), derived from the device and track extents
set nx1 [expr {min($lf::R(N1,x1),$lf::R(N2,x1)) - 0.4}]
set nx2 [expr {max($lf::R(N1,x2),$lf::R(N2,x2)) + 0.4}]
set ny1 [expr {$lf::R(N2,padyb) - $TOFF - 0.14 - 0.5}]
set ny2 [expr {$lf::R(N1,padyt) + $TOFF + 0.7 + 0.14 + 0.5}]
set px1 [expr {$lf::R(P,x1) + 0.43 - 0.5}]
set px2 [expr {$lf::R(P,x2) - 0.43 + 0.5}]
set py1 [expr {$lf::R(P,padyb) - $TOFF - 0.14 - 0.5}]
set py2 [expr {$lf::R(P,padyt) + $TOFF + 0.14 + 0.5}]
# poly resistor R1 (19.5 um x 1 um, ppolyf_u_1k), bottom terminal level with the IB track below N2
set yIBb [expr {$lf::R(N2,padyb) - $TOFF}]
set xRc  [expr {$nx2 + 0.36 + 2.5}]
lf::resistor R1 $xRc [expr {$yIBb - 0.18}] 1.0 19.5

# ======================= phase 2: flatten =========================================================
lf::flatten_devices lf_toy

# ======================= phase 3: wiring ==========================================================
foreach r {N2 N1 P} { lf::mos_wire $r }
set nring [lf::ring n $nx1 $ny1 $nx2 $ny2]
set pring [lf::ring p $px1 $py1 $px2 $py2]

# dummy S regions (VSS) and dummy gates (VSS) of N1 go to the p-ring on Metal1
lf::region_tie N1 0 [expr {$nx1 - 0.2}]
lf::region_tie N1 6 [expr {$nx2 + 0.2}]
lassign $lf::R(N1,strap,d1) xa xb ys
lf::hwire m1 $ys [expr {$nx1 - 0.2}] $xb 0.23
lassign $lf::R(N1,strap,d2) xa xb ys
lf::hwire m1 $ys $xa [expr {$nx2 + 0.2}] 0.23
# N2 gate strap (IB) crosses the IB stub of region 2: via1 joins them
lassign $lf::R(N2,strap,A) xa xb ysIB
lf::via1 $CX $ysIB
# P: gate strap (N1) to the N1 track of P through a solid Metal2 piece (no notch between pad and track)
lassign $lf::R(P,strap,A) xa xb ysP
lassign $lf::R(P,track,N1) ta tb tyP
set xg $lf::R(P,fx0)
lf::via1 $xg $ysP
lf::rect m2 [expr {$xg-0.2}] [expr {$tyP-0.14}] [expr {$xg+0.2}] [expr {$ysP+0.2}]

# ---------------- Metal3 trunks between rows ----------------------------------------------------------
# TAIL: N2 TAIL track  <->  N1 TAIL track at region 4
set xT $lf::R(N1,rx4)
lassign $lf::R(N2,track,TAIL) a b tyN2T
lassign $lf::R(N1,track,TAIL) a b tyN1T
lf::via2 $xT $tyN2T
lf::via2 $xT $tyN1T
lf::vwire m3 $xT $tyN2T $tyN1T 0.4
# N1 net: N1 row top track (idx 1)  <->  P bottom track
lassign $lf::R(N1,track,N1) a b tyN1N
set xN $lf::R(N1,rx1)
lf::via2 $xN $tyN1N
lf::via2 $xN $tyP
lf::vwire m3 $xN $tyN1N $tyP 0.4
# OUT: N1 OUT track -> P region 2 (via1 + via2) -> pin at the top
lassign $lf::R(N1,track,OUT) a b tyOUT
lf::via2 $CX $tyOUT
lf::via1 $CX $lf::R(P,cy)
lf::via2 $CX $lf::R(P,cy)
set ytop [expr {[lindex $pring 3] + 1.0}]
set ybot [expr {[lindex $nring 1] - 1.0}]
lf::vwire m3 $CX $tyOUT $ytop 0.4
lf::pin OUT m3 $CX $ytop
# VDD: P top track up to the n-ring (Metal2), pin on that Metal2
lassign $lf::R(P,track,VDD) a b tyV
set xv $lf::R(P,rx1)
set yringN [expr {$py2 + 0.18}]
lf::via1 $xv $yringN
lf::vwire m2 $xv $tyV $yringN 0.28
lf::lab VDD m2 $xv $yringN
# VSS: N2 VSS track (idx 1) -> M3 down to the p-ring south side, pin there
lassign $lf::R(N2,track,VSS) a b tyVS
set xs $lf::R(N2,rx1)
set yringS [expr {$ny1 - 0.18}]
lf::via2 $xs $tyVS
lf::via1 $xs $yringS
lf::via2 $xs $yringS
lf::vwire m3 $xs $tyVS $yringS 0.4
lf::lab VSS m3 $xs $yringS
# INP: A strap of N1 -> via stack -> M3 up to the top, pin
lassign $lf::R(N1,strap,A) a b ysA
set xI [expr {$CX - 0.9}]   ;# between the A gate stubs (M1 spacing) and clear of the OUT stub / trunk
lf::via1 $xI $ysA
lf::via2 $xI $ysA
lf::vwire m3 $xI $ysA $ytop 0.4
lf::pin INP m3 $xI $ytop
# INN: B strap of N1 -> via stack -> M3 down to the bottom, pin
lassign $lf::R(N1,strap,B) a b ysB
set xB [expr {$CX + 1.9}]          ;# the via cannot sit between the two B gate stubs (M1 spacing): extend the strap east
lf::hwire m1 $ysB $b [expr {$xB + 0.2}] 0.23
lf::via1 $xB $ysB
lf::via2 $xB $ysB
lf::vwire m3 $xB $ysB $ybot 0.4
lf::pin INN m3 $xB $ybot

# ---------------- IB: N2 region 2 stub down, then east on Metal2 to the resistor bottom terminal -------
lf::via1 $CX $lf::R(N2,cy)
lf::vwire m2 $CX $lf::R(N2,cy) $yIBb 0.28
set xR  [expr {($lf::R(R1,x1) + $lf::R(R1,x2))/2.0}]
set yRt [expr {$lf::R(R1,y2) - 0.18}]
lf::via1 $xR $yIBb
lf::hwire m2 $yIBb [expr {$CX - 0.14}] $xR 0.28   ;# start at the stub edge: no 0.14 um jog (M2.1)
# resistor top terminal -> VDD n-ring east side, Metal1 straight west
lf::hwire m1 $yRt [expr {[lindex $pring 2] - 0.2}] [expr {$lf::R(R1,x1) + 0.3}] 0.23

puts "ROWS N2 cy=$lf::R(N2,cy) N1 cy=$lf::R(N1,cy) P cy=$lf::R(P,cy) nring=$nring pring=$pring ytop=$ytop ybot=$ybot yIBb=$yIBb yRt=$yRt"
select top cell
drc check
drc catchup
puts "DRCCOUNT [drc listall count]"
foreach {txt boxes} [drc listall why] { puts "DRCWHY $txt : [llength $boxes] boxes: [lindex $boxes 0]" }
writeall force
gds write lf_toy.gds
quit -noprompt
