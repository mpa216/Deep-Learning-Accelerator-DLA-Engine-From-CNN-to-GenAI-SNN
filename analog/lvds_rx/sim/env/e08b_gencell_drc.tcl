# e08b_gencell_drc.tcl -- why did the first smoke test report "DRC count 8" for a lone gencell nfet?
# Run (from a scratch dir inside analog/lvds_rx):
#   magic -dnull -noconsole -rcfile /foss/pdks/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc sim/env/e08b_gencell_drc.tcl
cellname rename (UNNAMED) gc_top
box 0 0 0 0
foreach g {{guard 1} {guard 0}} {
  set r [catch {magic::gencell gf180mcu::nfet_03v3 M1 w 4.0 l 0.5 nf 4 {*}$g} msg]
  select top cell
  drc check
  drc catchup
  puts "GEN \{$g\} rc=$r  DRC count: [drc listall count]"
  puts "GEN \{$g\} DRC why: [drc listall why]"
  select top cell
  delete
  select cell M1
  puts "(cells now: [cellname list children])"
}
quit -noprompt
