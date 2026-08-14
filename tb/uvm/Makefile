# cocotb + pyuvm testbench for dla_engine_top (longtin variant, C = flip-flops).
# Run inside the apic_headless container:  cd /foss/designs/tb/uvm && make
#
#   SIM=icarus (default) drives the DUT through Icarus Verilog's VPI.
#   Behavioral SRAM models are used (SYNTHESIS is NOT defined).

SIM ?= icarus
TOPLEVEL_LANG ?= verilog

RTL := $(shell pwd)/../../rtl
VERILOG_SOURCES := \
  $(RTL)/dla_engine_top.v \
  $(RTL)/dla_controller.v \
  $(RTL)/dla_pe.v \
  $(RTL)/dla_pe_array.v \
  $(RTL)/dla_a_buffer_bank.v \
  $(RTL)/dla_b_buffer_bank.v \
  $(RTL)/dla_c_buffer_bank.v \
  $(RTL)/gf180_sram_1rw_256x8.v \
  $(RTL)/gf180_sram_1rw_64x8.v

# -g2012 enables the SystemVerilog-2012 constructs the RTL uses ($clog2, generate).
COMPILE_ARGS += -g2012

TOPLEVEL := dla_engine_top
MODULE := dla_uvm

include $(shell cocotb-config --makefiles)/Makefile.sim
