# lf.tcl -- small scripted-layout library for Magic (gf180mcuD), all coordinates in MICRONS.
#
# Source it from a Magic batch script that was started with the PDK rcfile:
#   magic -dnull -noconsole -rcfile $PDK_ROOT/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc build.tcl
#
# Design rules of the library (learned the hard way, see COOKBOOK.md):
#  * every coordinate is rounded to the 5 nm Magic internal grid (200 internal units / um)
#  * transistor bodies come from the PDK generator (magic::gencell, "guard 0"); everything that
#    connects them (gate straps, S/D tracks, vias, guard rings, pins) is painted here
#  * Metal1 = device-level wiring, Metal2 = horizontal tracks, Metal3 = vertical trunks / pins
#
# Public procs:
#   lf::start cell                       name the top cell
#   lf::rect layer x1 y1 x2 y2           paint a rectangle   (lf::clr layers x1 y1 x2 y2)
#   lf::hwire layer y x1 x2 w            horizontal wire centred on y
#   lf::vwire layer x y1 y2 w            vertical wire centred on x
#   lf::via1 x y / lf::via2 x y          via stack pads (M1-M2 / M2-M3) with legal enclosure
#   lf::ring kind x1 y1 x2 y2            guard ring (kind n = p+ ring in p-sub for NMOS,
#                                        kind p = n+ ring in n-well for PMOS); box = INNER clear area
#   lf::tap kind x y                     single substrate/well tap
#   lf::mos_row name type w l pattern .. interdigitated / common-centroid transistor row
#   lf::resistor name x y w l            poly resistor (ppolyf_u_1k) via the PDK generator
#   lf::pin name layer x y               labelled port (pad + label + port make); lf::lab = label+port only
#   lf::writeout cell                    save .mag, write GDS (0.001 um DBU), report DBU

namespace eval lf {
    variable U 0.005          ;# um per Magic internal unit in this tech (200 units / um)
    variable top ""
    variable R                ;# row geometry database, R(name,key)
    array set R {}
    # rule constants used by the generators (um), taken from the PDK ruleset / DRC deck
    variable M1W 0.23         ;# Metal1 min width
    variable PADW 0.40        ;# via landing pad edge (cut 0.28 painted -> 0.26 drawn + enclosure)
    variable VIA 0.28         ;# painted via box (>= 0.28 per the PDK via1_draw proc)
    variable TRK_PITCH 0.70   ;# Metal2 track pitch (width 0.28 + space 0.28 + margin)
}

# ---- low level ---------------------------------------------------------------------------------

proc lf::i {v} {                       ;# um -> integer internal units (5 nm grid)
    variable U
    return [expr {int(round($v / $U))}]
}
proc lf::u {v} {                       ;# internal units -> um
    variable U
    return [expr {$v * $U}]
}
proc lf::start {name} {
    variable top
    set top $name
    cellname rename (UNNAMED) $name
    box values 0um 0um 0um 0um
}
proc lf::q {v} {                       ;# snap a um value to the 5 nm grid and format with the "um" suffix
    return [format %.3fum [expr {[lf::i $v] * 0.005}]]
}
# NOTE: "box values a b c d" takes LAMBDA (0.05 um) when no unit is given, but returns INTERNAL units (5 nm).
# Always pass an explicit "um" suffix when setting, divide by 200 when reading (lf::u).
proc lf::bx {x1 y1 x2 y2} {
    box values [lf::q [expr {min($x1,$x2)}]] [lf::q [expr {min($y1,$y2)}]] \
               [lf::q [expr {max($x1,$x2)}]] [lf::q [expr {max($y1,$y2)}]]
}
proc lf::rect {layer x1 y1 x2 y2} {
    lf::bx $x1 $y1 $x2 $y2
    paint $layer
}
proc lf::clr {layers x1 y1 x2 y2} {
    lf::bx $x1 $y1 $x2 $y2
    erase $layers
}
proc lf::hwire {layer y x1 x2 w} {
    lf::rect $layer [expr {min($x1,$x2)}] [expr {$y - $w/2.0}] [expr {max($x1,$x2)}] [expr {$y + $w/2.0}]
}
proc lf::vwire {layer x y1 y2 w} {
    lf::rect $layer [expr {$x - $w/2.0}] [expr {min($y1,$y2)}] [expr {$x + $w/2.0}] [expr {max($y1,$y2)}]
}

# ---- vias ------------------------------------------------------------------------------------------

proc lf::via1 {x y} {                  ;# Metal1 <-> Metal2 stack, pads on both metals
    variable VIA
    variable PADW
    set h [expr {$VIA/2.0}]
    set p [expr {$PADW/2.0}]
    lf::rect via1 [expr {$x-$h}] [expr {$y-$h}] [expr {$x+$h}] [expr {$y+$h}]
    lf::rect m1   [expr {$x-$p}] [expr {$y-$p}] [expr {$x+$p}] [expr {$y+$p}]
    lf::rect m2   [expr {$x-$p}] [expr {$y-$p}] [expr {$x+$p}] [expr {$y+$p}]
}
proc lf::via2 {x y} {                  ;# Metal2 <-> Metal3 stack
    variable VIA
    variable PADW
    set h [expr {$VIA/2.0}]
    set p [expr {$PADW/2.0}]
    lf::rect via2 [expr {$x-$h}] [expr {$y-$h}] [expr {$x+$h}] [expr {$y+$h}]
    lf::rect m2   [expr {$x-$p}] [expr {$y-$p}] [expr {$x+$p}] [expr {$y+$p}]
    lf::rect m3   [expr {$x-$p}] [expr {$y-$p}] [expr {$x+$p}] [expr {$y+$p}]
}

# ---- guard ring and tap -----------------------------------------------------------------------------
# kind n : p+ ring (psd/psc) in p-substrate/pwell, for NMOS      (ties pwell to a net, usually VSS)
# kind p : n+ ring (nsd/nsc) in an n-well, for PMOS              (ties nwell to a net, usually VDD)
# (x1 y1 x2 y2) is the INNER edge of the diffusion ring.  Ring diffusion is 0.36 um wide, contact strip
# 0.23 um continuous, Metal1 strip 0.36 um continuous on top (full-metal ring).  Returns outer box.

proc lf::ring {kind x1 y1 x2 y2} {
    if {$kind eq "n"} {set dif psd; set con psc; set well pwell; set wext 0.12} \
    else              {set dif nsd; set con nsc; set well nwell; set wext 0.12}
    set dw 0.36
    set cw 0.23
    set ox1 [expr {$x1-$dw}]; set oy1 [expr {$y1-$dw}]
    set ox2 [expr {$x2+$dw}]; set oy2 [expr {$y2+$dw}]
    # diffusion: four bars (corners belong to the horizontal bars)
    lf::rect $dif $ox1 $oy1 $ox2 $y1
    lf::rect $dif $ox1 $y2  $ox2 $oy2
    lf::rect $dif $ox1 $y1  $x1  $y2
    lf::rect $dif $x2  $y1  $ox2 $y2
    set m [expr {($dw-$cw)/2.0}]
    # contacts: continuous strips centred in the diffusion bars
    lf::rect $con [expr {$ox1+$m}] [expr {$oy1+$m}] [expr {$ox2-$m}] [expr {$y1-$m}]
    lf::rect $con [expr {$ox1+$m}] [expr {$y2+$m}]  [expr {$ox2-$m}] [expr {$oy2-$m}]
    # vertical strips stay 0.5 um away from the horizontal ones: contact arrays of two strips must not interleave (CO.2a)
    lf::rect $con [expr {$ox1+$m}] [expr {$y1+0.5}] [expr {$x1-$m}]  [expr {$y2-0.5}]
    lf::rect $con [expr {$x2+$m}]  [expr {$y1+0.5}] [expr {$ox2-$m}] [expr {$y2-0.5}]
    # metal1 strip on the whole ring
    lf::rect m1 $ox1 $oy1 $ox2 $y1
    lf::rect m1 $ox1 $y2  $ox2 $oy2
    lf::rect m1 $ox1 $y1  $x1  $y2
    lf::rect m1 $x2  $y1  $ox2 $y2
    # well: whole ring plus margin
    lf::rect $well [expr {$ox1-$wext}] [expr {$oy1-$wext}] [expr {$ox2+$wext}] [expr {$oy2+$wext}]
    return [list $ox1 $oy1 $ox2 $oy2]
}

proc lf::tap {kind x y} {              ;# single tap: contact 0.23, diffusion 0.60 sq (DF.9 min area 0.2025, PP.8a/NP.8a implant min area 0.35), M1 0.40 sq (M1.3), well 1.1 sq (NW.1a min width 0.86)
    if {$kind eq "n"} {set dif psd; set con psc; set well pwell} else {set dif nsd; set con nsc; set well nwell}
    lf::rect $con [expr {$x-0.115}] [expr {$y-0.115}] [expr {$x+0.115}] [expr {$y+0.115}]
    lf::rect $dif [expr {$x-0.30}]  [expr {$y-0.30}]  [expr {$x+0.30}]  [expr {$y+0.30}]
    lf::rect m1   [expr {$x-0.20}]  [expr {$y-0.20}]  [expr {$x+0.20}]  [expr {$y+0.20}]
    lf::rect $well [expr {$x-0.55}] [expr {$y-0.55}]  [expr {$x+0.55}]  [expr {$y+0.55}]
}

# ---- transistor row ------------------------------------------------------------------------------------
# lf::mos_row NAME TYPE W L PATTERN  (x X y Y | cx CX cy CY)  gnet {..} gside {..} rnet {..} tracks {..}
#   TYPE     n | p        (nfet_03v3 / pfet_03v3)
#   W        width per finger (um), L gate length (um)
#   PATTERN  list with one symbol per finger, left to right, e.g. {d A B B A d}
#   x y | cx cy   lower-left corner, or centre, of the generator cell (um)
#   gnet     dict symbol -> gate net name      (used only for bookkeeping / strap grouping)
#   gside    dict symbol -> top | bot          side of the Metal1 gate strap; the pad on the other side is erased
#   rnet     list of nf+1 net names, S/D region j = diffusion between finger j-1 and j ("" = leave open)
#   toff     distance (um) from the pad row to track idx 0 (default 1.25; must clear the 0.4 um via pads of the strap)
#   tracks   dict net -> {side idx}  Metal2 track for that net; side top|bot, idx 0 = nearest to the row
#            (nets in an interleaved pattern must be nested: the inner net gets the smaller idx)
# Stored geometry (R array, um): NAME,x1/y1/x2/y2 (cell bbox), cx cy, pitch, nf, fx<i> (finger centre x),
#   rx<j> (region centre x), padyt padyb (gate pad centre y), strap,<net>,<side> {x1 x2 y}, track,<net> {x1 x2 y}
proc lf::mos_row {name type w l pattern args} {
    set x 0; set y 0
    variable R
    variable TRK_PITCH
    if {![info exists R(rows)]} {set R(rows) {}}
    array set o {gnet {} gside {} rnet {} tracks {} stubw 0.28 toff 1.25}
    array set o $args
    if {[info exists o(x)]} {set x $o(x)}
    if {[info exists o(y)]} {set y $o(y)}
    set nf [llength $pattern]
    set dev [expr {$type eq "n" ? "nfet_03v3" : "pfet_03v3"}]
    # optional centre placement (the generator puts the lower-left corner at the box); the cell size is
    # analytic: width = (nf-1)*(L+0.52) + L + 1.12 (+0.62 for the PMOS n-well), height = W + 1.16 (+0.62)
    set extra [expr {$type eq "n" ? 0.0 : 0.62}]
    if {[info exists o(cx)]} {set x [expr {$o(cx) - (($nf-1)*($l+0.52) + $l + 1.12 + $extra)/2.0}]}
    if {[info exists o(cy)]} {set y [expr {$o(cy) - ($w + 1.16 + $extra)/2.0}]}
    # --- 1. the PDK generator draws diffusion, poly, contacts, pad metal for all fingers
    lf::bx $x $y $x $y
    magic::gencell gf180mcu::$dev $name w $w l $l nf $nf guard 0
    set bb [box values]
    set x1 [lf::u [lindex $bb 0]]; set y1 [lf::u [lindex $bb 1]]
    set x2 [lf::u [lindex $bb 2]]; set y2 [lf::u [lindex $bb 3]]
    set cx [expr {($x1+$x2)/2.0}]; set cy [expr {($y1+$y2)/2.0}]
    set pitch [expr {$l + 0.52}]
    set padyt [expr {$cy + $w/2.0 + 0.28}]
    set padyb [expr {$cy - $w/2.0 - 0.28}]
    set ph    [expr {($l - 0.02)/2.0}]                ;# half width of the Metal1 gate pad
    foreach k {x1 y1 x2 y2 cx cy pitch padyt padyb nf} {set R($name,$k) [set $k]}
    for {set i 0} {$i < $nf} {incr i} { set R($name,fx$i) [expr {$cx + ($i - ($nf-1)/2.0)*$pitch}] }
    for {set j 0} {$j <= $nf} {incr j} { set R($name,rx$j) [expr {$cx + ($j - $nf/2.0)*$pitch}] }
    set R($name,rbar_y1) [expr {$cy - $w/2.0 + 0.065}]   ;# contact bar extent on Metal1
    set R($name,rbar_y2) [expr {$cy + $w/2.0 - 0.065}]
    set R($name,args) [array get o]
    set R($name,pattern) $pattern
    set R($name,w) $w
    set R($name,l) $l
    lappend R(rows) $name
    return $bb
}

# lf::flatten_devices DEST   Flatten every generator instance placed so far into one flat cell DEST and make it the edit
# cell.  Needed because the generator cells are read-only sub-cells: pad erasure and merging can only be done in a flat cell.
proc lf::flatten_devices {dest} {
    variable top
    flatten $dest
    load $dest
    set top $dest
    select top cell
}

# lf::mos_wire NAME   second phase of mos_row (call after lf::flatten_devices): gate pads/straps and S/D tracks
proc lf::mos_wire {name} {
    variable R
    variable TRK_PITCH
    array set o $R($name,args)
    set pattern $R($name,pattern)
    set w $R($name,w); set l $R($name,l)
    set nf $R($name,nf)
    set cx $R($name,cx); set cy $R($name,cy)
    set x1 $R($name,x1); set x2 $R($name,x2); set y1 $R($name,y1); set y2 $R($name,y2)
    set padyt $R($name,padyt); set padyb $R($name,padyb)
    set ph    [expr {($l - 0.02)/2.0}]
    # --- 2. gate pads: keep only the pad on the requested side, strap per (net, side)
    array set gs $o(gside)
    array set gn $o(gnet)
    array set group {}
    array set gy {}
    for {set i 0} {$i < $nf} {incr i} {
        set s [lindex $pattern $i]
        set side $gs($s)
        set fx $R($name,fx$i)
        if {$side eq "top"} {set pady $padyb; set keepy $padyt; set dir 1} else {set pady $padyt; set keepy $padyb; set dir -1}
        # erase the unused pad (contact + its metal), put the poly back
        lf::clr pc,m1 [expr {$fx-$ph-0.02}] [expr {$pady-0.12}] [expr {$fx+$ph+0.02}] [expr {$pady+0.12}]
        lf::rect poly [expr {$fx-$l/2.0}] [expr {$pady-0.12}] [expr {$fx+$l/2.0}] [expr {$pady+0.12}]
        set sy [expr {$keepy + $dir*0.60}]
        # stub from pad centre to strap, strap collects all fingers of the same net on the same side
        lf::vwire m1 $fx $keepy $sy 0.23
        set key "$s"
        lappend group($key) $fx
        set gy($key) $sy
    }
    foreach key [array names group] {
        
        set xs [lsort -real $group($key)]
        set xa [expr {[lindex $xs 0] - 0.115}]; set xb [expr {[lindex $xs end] + 0.115}]
        lf::hwire m1 $gy($key) $xa $xb 0.23
        set R($name,strap,$key) [list $xa $xb $gy($key)]
    }
    # --- 3. S/D region nets: via1 on the contact bar centre, Metal2 stub to the net's track, track itself
    array set tk $o(tracks)
    set rn $o(rnet)
    array set spans {}
    for {set j 0} {$j <= $nf} {incr j} {
        set net [lindex $rn $j]
        if {$net eq "" || ![info exists tk($net)]} continue
        lappend spans($net) $R($name,rx$j)
    }
    foreach net [array names spans] {
        lassign $tk($net) side idx
        # track y: just beyond the highest Metal1 strap of this row on that side, idx steps outward
        set base [expr {$side eq "top" ? $padyt + $o(toff) : $padyb - $o(toff)}]
        set dir  [expr {$side eq "top" ? 1 : -1}]
        set ty   [expr {$base + $dir*$idx*$TRK_PITCH}]
        set xs [lsort -real $spans($net)]
        foreach rx $xs {
            lf::via1 $rx $cy
            lf::vwire m2 $rx $cy $ty $o(stubw)
        }
        set xa [lindex $xs 0]; set xb [lindex $xs end]
        lf::hwire m2 $ty [expr {$xa-$o(stubw)/2.0}] [expr {$xb+$o(stubw)/2.0}] $o(stubw)
        set R($name,track,$net) [list $xa $xb $ty]
    }
}

# connect a region's Metal1 contact bar horizontally to some x (e.g. a guard ring), on Metal1
proc lf::region_tie {name j xto} {
    variable R
    variable TRK_PITCH
    set cy $R($name,cy)
    lf::hwire m1 $cy $R($name,rx$j) $xto 0.23
}

# ---- poly resistor ------------------------------------------------------------------------------------
proc lf::resistor {name x y w l} {
    variable R
    variable TRK_PITCH
    lf::bx $x $y $x $y
    magic::gencell gf180mcu::ppolyf_u_1k $name w $w l $l guard 0
    set bb [box values]
    set x1 [lf::u [lindex $bb 0]]; set y1 [lf::u [lindex $bb 1]]
    set x2 [lf::u [lindex $bb 2]]; set y2 [lf::u [lindex $bb 3]]
    foreach k {x1 y1 x2 y2} {set R($name,$k) [set $k]}
    set R($name,cx) [expr {($x1+$x2)/2.0}]
    return $bb
}

# ---- pins and output ------------------------------------------------------------------------------------
# Pad (landing area) of the given layer centred on (x y), a label on it, and a port.
proc lf::lab {name layer x y} {        ;# label + port on metal that already exists at (x y)
    lf::bx $x $y $x $y
    label $name FreeSans 0.3um 0 0 0 c $layer
    port make
}
proc lf::pin {name layer x y {sz 0.40}} {
    set h [expr {$sz/2.0}]
    lf::rect $layer [expr {$x-$h}] [expr {$y-$h}] [expr {$x+$h}] [expr {$y+$h}]
    lf::lab $name $layer $x $y
}

proc lf::writeout {cell} {
    save $cell
    gds write $cell.gds
}
