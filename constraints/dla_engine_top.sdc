# =============================================================================
# dla_engine_top.sdc -- HAND-WRITTEN timing constraints for the DLA accelerator
# core (the Stage-1 tapeout boundary: 4x4 INT8 MAC + A/B/C buffers, 8 SRAM
# macros in the longtin variant).
#
# This is authored by hand, not emitted by write_sdc.  The signed-off flow lets
# OpenROAD synthesise its own constraints from CLOCK_PERIOD; this file is the
# explicit, commented equivalent (plus the things the auto-SDC omits: split
# setup/hold uncertainty, input transition, output load).  Validate it with
# constraints/validate_sdc.tcl, which links the routed netlist and re-runs STA
# against THIS file.
#
# Operating point: single-supply 3.3 V, 40 ns clock (25 MHz), gf180mcu AS 3.3 V
# std cells + gf180 OCD 3.3 V SRAM.  Matches librelane/config_longtin.yaml.
# =============================================================================

# ---- clock -----------------------------------------------------------------
# 40 ns was chosen in the 3.3 V bring-up: actual critical path (SRAM read -> mux
# -> PE MAC -> accumulate) is ~25-30 ns at the slow corner, and 40 ns leaves the
# project's ~9-15 ns margin convention.  See CLAUDE.md "3.3 V bring-up".
set CLK_PERIOD 40.0
create_clock -name clk -period $CLK_PERIOD [get_ports clk]

# Propagated (not ideal) clock so STA uses the real CTS insertion delay.
set_propagated_clock [get_clocks clk]

# Model the clock tree before CTS exists / for netlist-only STA: a source
# latency and a transition so early estimates are not zero-delay.
set_clock_transition 0.15 [get_clocks clk]

# Split uncertainty: setup budget absorbs jitter + CTS skew margin; hold budget
# is smaller (skew only, no jitter on a same-edge check).  The auto-SDC uses a
# single 0.25 ns for both, which over-pessimises hold.
set_clock_uncertainty -setup 0.25 [get_clocks clk]
set_clock_uncertainty -hold  0.10 [get_clocks clk]

# ---- I/O timing budget -----------------------------------------------------
# All top-level I/O is synchronous to clk and talks to an off-chip host (the
# serial bridge in dla_engine_chip, or a test host).  Budget 20% of the period
# (8 ns) each side for board + host setup, leaving 60% for on-chip logic.
set IO_DELAY [expr {0.20 * $CLK_PERIOD}]

set data_inputs  [get_ports {rst_n start wr_en wr_sel wr_addr[*] wr_data[*] rd_en rd_addr[*]}]
set data_outputs [get_ports {rd_data[*] wb_done done busy}]

set_input_delay  $IO_DELAY -clock clk $data_inputs
set_output_delay $IO_DELAY -clock clk $data_outputs

# NOTE on rst_n: it is an ASYNChronously-asserted reset (all FFs use
# `negedge rst_n`).  It is constrained here as a normal timed input (safe /
# conservative).  A production flow would additionally synchronise its
# DEASSERTION and add recovery/removal checks; called out as a known refinement
# rather than hidden with a blanket false_path.

# ---- driver / load models (auto-SDC omits these) ---------------------------
# Model a real off-chip driver slew on inputs and a real capacitive load on
# outputs, so I/O path slews are not idealised to zero.
set_input_transition 0.50 $data_inputs
set_load 0.050 $data_outputs

# ---- design rule limits ----------------------------------------------------
# max_transition is a real signal-integrity limit and is enforced here.
# max_fanout is deliberately left to the library default + CTS: a blanket
# design-wide fanout cap would false-flag the clock-tree leaf buffers (which
# legitimately fan out to 20-50+ registers by CTS construction), not the logic.
set_max_transition 1.50 [current_design]
