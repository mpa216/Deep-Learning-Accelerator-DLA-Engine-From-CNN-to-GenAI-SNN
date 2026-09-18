# validate_sdc.tcl -- link a routed netlist and re-run STA against a HAND-WRITTEN
# SDC, to prove the SDC is syntactically valid and constrains real paths
# (non-vacuous: a real propagated clock, finite slack, no unconstrained
# endpoints).  Pure-timing flow via standalone OpenSTA -- no LEF/tech needed.
#
# Zero-parasitic (no SPEF) STA: slack is optimistic vs the SPEF sign-off, but
# that is fine -- the goal is to validate the CONSTRAINTS, not reproduce signoff.
# Driven by constraints/validate_sdc.sh.
#
#   sta -no_init -exit constraints/validate_sdc.tcl
read_liberty $env(LIB_STD)
read_liberty $env(LIB_SRAM)
read_verilog $env(DESIGN_NL)
link_design  $env(DESIGN_TOP)
read_sdc     $env(DESIGN_SDC)

puts "\n===== CLOCKS (must show a real 40 ns clk, not virtual) ====="
foreach clk [all_clocks] {
  puts "  clock [get_name $clk]  period=[get_property $clk period] ns"
}

puts "\n===== SETUP (max) worst path ====="
report_checks -path_delay max -group_count 1 -digits 3

puts "\n===== HOLD (min) worst path ====="
report_checks -path_delay min -group_count 1 -digits 3

puts "\n===== SLACK SUMMARY ====="
if {[catch {report_worst_slack -max} e]} { puts "worst setup slack: (report_worst_slack unavailable: $e)" }
if {[catch {report_worst_slack -min} e]} { puts "worst hold  slack: (report_worst_slack unavailable: $e)" }
if {[catch {report_tns} e]}              { puts "tns: (report_tns unavailable)" }

puts "\n===== DESIGN-RULE CHECKS (from the SDC limits) ====="
if {[catch {report_check_types -max_slew -max_capacitance -max_fanout -violators} e]} {
  puts "(report_check_types: $e)"
}

puts "\n===== UNCONSTRAINED ENDPOINTS (want: none / empty) ====="
if {[catch {report_checks -unconstrained -digits 3} e]} {
  puts "(report_checks -unconstrained unavailable: $e)"
}
