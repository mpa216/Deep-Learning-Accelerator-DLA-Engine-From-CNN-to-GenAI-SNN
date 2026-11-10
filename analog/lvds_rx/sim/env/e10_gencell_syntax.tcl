# e10_gencell_syntax.tcl -- do the handoff 11.1 gencell lines work in this Magic?  Also list the parameters of each device.
# Run from a scratch dir:  magic -dnull -noconsole -rcfile /foss/pdks/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc <this file>
cellname rename (UNNAMED) gc_top
box 0 0 0 0
set tests {
  {gf180mcu::nfet_03v3 M1 w 4.0 l 0.5 nf 4 guard 1 full_metal 1}
  {gf180mcu::pfet_03v3 M5 w 5.0 l 0.28 nf 6 guard 1}
  {gf180mcu::ppolyf_u_1k R1 w 2.0 l 10.0}
  {gf180mcu::ppolyf_u R2 w 2.0 l 10.0}
  {gf180mcu::npolyf_u R3 w 2.0 l 10.0}
  {gf180mcu::nmoscap_3p3 C1 w 10.0 l 10.0}
  {gf180mcu::cap_mim_2p0fF C2 w 10.0 l 10.0}
  {gf180mcu::diode_nd2ps_03v3 D1 w 2.0 l 2.0}
  {gf180mcu::diode_pd2nw_03v3 D2 w 2.0 l 2.0}
  {gf180mcu::nfet_03v3 M9 w 4.0 l 0.5 nf 4 deepnwell 1}
  {gf180mcu::nfet_03v3 M10 w 4.0 l 0.5 nf 4 dnwell 1}
}
foreach t $tests {
  set r [catch {magic::gencell {*}$t} msg]
  puts "GENCELL \{$t\} -> rc=$r  [string range $msg 0 120]"
}
puts "DEFAULTS nfet_03v3: [gf180mcu::nfet_03v3_defaults]"
puts "DEFAULTS ppolyf_u: [gf180mcu::ppolyf_u_defaults]"
puts "DEFAULTS nmoscap_3p3: [gf180mcu::nmoscap_3p3_defaults]"
puts "DEFAULTS diode_nd2ps_03v3: [gf180mcu::diode_nd2ps_03v3_defaults]"
quit -noprompt
