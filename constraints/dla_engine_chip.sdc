# =============================================================================
# dla_engine_chip.sdc -- HAND-WRITTEN timing constraints for the padframe-facing
# chip (A56/ACV): dla_engine_top core + dla_serial_bridge, over the 4-wire link.
#
# The one constraint that MATTERS here and that a naive auto-SDC gets wrong:
# SCLK/MOSI/CS_N are ASYNCHRONOUS pad inputs.  The bridge double-flop
# synchronises them to clk and edge-detects SCLK as data -- there is no second
# clock domain.  Timing the raw pad-to-first-flop path is physically
# meaningless (that is exactly what the synchroniser exists to tolerate), so
# those inputs are declared false paths.  This mirrors the async-input
# false_path fix made by hand in the Stage-2 chip_top.sdc during sign-off.
#
# Validate with constraints/validate_sdc.tcl (links verilog/dla_engine_chip.nl.v).
# =============================================================================

set CLK_PERIOD 40.0
create_clock -name clk -period $CLK_PERIOD [get_ports clk]
set_propagated_clock [get_clocks clk]
set_clock_transition 0.15 [get_clocks clk]
set_clock_uncertainty -setup 0.25 [get_clocks clk]
set_clock_uncertainty -hold  0.10 [get_clocks clk]

# ---- ASYNC serial inputs: false paths (synchroniser-guarded) ---------------
# Cutting all paths FROM these ports: they land only on the first synchroniser
# flop, whose metastability is resolved by the second.  Timing them would
# create spurious setup/hold checks against clk.
set async_inputs [get_ports {SCLK_IN MOSI_IN CS_N_IN}]
set_false_path -from $async_inputs

# The *_IN pins of the OUTPUT pads (MISO/busy/done/wb_done) are pad-Y feedbacks
# that feed nothing functional (see dla_engine_chip.sv `_unused`); not timed.
set_false_path -from [get_ports {MISO_IN busy_IN done_IN wb_done_IN}]

# ---- synchronous I/O -------------------------------------------------------
set IO_DELAY [expr {0.20 * $CLK_PERIOD}]

# Only real synchronous data OUTPUTS to the host.  The *_OE/_IE/_CS/_SL/_PU/_PD
# pad-control outputs are tied to constants in RTL, so they carry no timing arc.
set data_outputs [get_ports {MISO_OUT busy_OUT done_OUT wb_done_OUT}]
set_output_delay $IO_DELAY -clock clk $data_outputs
set_load 0.050 $data_outputs

# rst_n: async-asserted reset (see dla_engine_top.sdc note), timed conservatively.
set_input_delay $IO_DELAY -clock clk [get_ports rst_n]
set_input_transition 0.50 [get_ports rst_n]

# max_transition enforced; max_fanout left to lib+CTS (see dla_engine_top.sdc).
set_max_transition 1.50 [current_design]
