`timescale 1ns / 1ps
`default_nettype none

// Stage-2 padring chip_core: instantiates the hardened dla_engine_top macro
// (bare, no parameter overrides -- the hardened .nl.v carries no parameters)
// behind a 4-wire serial bridge (dla_serial_bridge) that fits its wide
// interface into the workshop slot's 20-bidir-pad budget.
//
// Bidir pin allocation (see CLAUDE.md "Stage 2 padring" notes):
//   bidir[0] = SCLK (in)   bidir[1] = MOSI (in)   bidir[2] = CS_N (in)
//   bidir[3] = MISO (out)
//   bidir[4] = busy (out)  bidir[5] = done (out)  bidir[6] = wb_done (out)
//   bidir[7..19] = unused (inputs, pulled down)
// clk/rst_n come from the padring's own dedicated clock/reset pads --
// dla_engine_top's clk/rst_n connect directly, no serialization needed.
//
// This file replaces the padring fork's src/chip_core.sv at integration
// time (same pattern as chip_core_multi.sv in the reference example).
module chip_core #(
    parameter NUM_INPUT_PADS,
    parameter NUM_BIDIR_PADS,
    parameter NUM_ANALOG_PADS
    )(
    `ifdef USE_POWER_PINS
    inout  wire VDD,
    inout  wire VSS,
    `endif

    input  wire clk,
    input  wire rst_n,

    input  wire [NUM_INPUT_PADS-1:0] input_in,
    output wire [NUM_INPUT_PADS-1:0] input_pu,
    output wire [NUM_INPUT_PADS-1:0] input_pd,

    input  wire [NUM_BIDIR_PADS-1:0] bidir_in,
    output wire [NUM_BIDIR_PADS-1:0] bidir_out,
    output wire [NUM_BIDIR_PADS-1:0] bidir_oe,
    output wire [NUM_BIDIR_PADS-1:0] bidir_cs,
    output wire [NUM_BIDIR_PADS-1:0] bidir_sl,
    output wire [NUM_BIDIR_PADS-1:0] bidir_ie,
    output wire [NUM_BIDIR_PADS-1:0] bidir_pu,
    output wire [NUM_BIDIR_PADS-1:0] bidir_pd,

    inout  wire [NUM_ANALOG_PADS-1:0] analog
);

    // Disable pull-up/down on the (unused) spare single input pad.
    assign input_pu = '0;
    assign input_pd = '0;

    // Keep synthesis from optimising away padring ports this design doesn't use.
    wire _unused;
    assign _unused = &{1'b0, input_in, bidir_in[19:3], analog};

    // ---- fixed pin allocation on the 20 bidir pads ----
    localparam int PIN_SCLK    = 0;
    localparam int PIN_MOSI    = 1;
    localparam int PIN_CS_N    = 2;
    localparam int PIN_MISO    = 3;
    localparam int PIN_BUSY    = 4;
    localparam int PIN_DONE    = 5;
    localparam int PIN_WB_DONE = 6;
    // 7..19 unused

    wire sclk_pad = bidir_in[PIN_SCLK];
    wire mosi_pad = bidir_in[PIN_MOSI];
    wire cs_n_pad = bidir_in[PIN_CS_N];
    wire miso_pad;

    wire        dla_start, dla_wr_en, dla_wr_sel, dla_rd_en;
    wire [9:0]  dla_wr_addr;
    wire signed [7:0]  dla_wr_data;
    wire [3:0]  dla_rd_addr;
    wire signed [23:0] dla_rd_data;
    wire        dla_wb_done, dla_done, dla_busy;

    dla_serial_bridge #(
        .AB_ADDR_W (10),
        .C_ADDR_W  (4),
        .DATA_W    (8),
        .ACC_W     (24)
    ) u_bridge (
        .clk      (clk),
        .rst_n    (rst_n),
        .sclk_pad (sclk_pad),
        .mosi_pad (mosi_pad),
        .cs_n_pad (cs_n_pad),
        .miso_pad (miso_pad),
        .start    (dla_start),
        .wr_en    (dla_wr_en),
        .wr_sel   (dla_wr_sel),
        .wr_addr  (dla_wr_addr),
        .wr_data  (dla_wr_data),
        .rd_en    (dla_rd_en),
        .rd_addr  (dla_rd_addr),
        .rd_data  (dla_rd_data)
    );

    // Bare instantiation -- matches dla_engine_top's N=4/K=256/DATA_W=8/ACC_W=24
    // defaults, which is what gets baked into the hardened netlist. No VDD/VSS
    // connection: the hardened dla_engine_top.nl.v's port list has no power
    // pins (13 signal ports only, confirmed directly) -- macro power is
    // physical-PDN-only here, via this file's own PDN_MACRO_CONNECTIONS
    // registration (".*u_dla.* VDD VSS VDD VSS" in the padring's
    // config.yaml), the same convention already used for the raw SRAM macro
    // inside dla_engine_top itself (see bring-up note 1 in CLAUDE.md).
    dla_engine_top u_dla (
        .clk     (clk),
        .rst_n   (rst_n),
        .start   (dla_start),
        .wr_en   (dla_wr_en),
        .wr_sel  (dla_wr_sel),
        .wr_addr (dla_wr_addr),
        .wr_data (dla_wr_data),
        .rd_en   (dla_rd_en),
        .rd_addr (dla_rd_addr),
        .rd_data (dla_rd_data),
        .wb_done (dla_wb_done),
        .done    (dla_done),
        .busy    (dla_busy)
    );

    // ---- bidir pad wiring ----
    genvar i;
    generate
        for (i = 0; i < NUM_BIDIR_PADS; i = i + 1) begin : GEN_BIDIR
            if (i == PIN_MISO) begin : G_MISO
                assign bidir_out[i] = miso_pad;
                assign bidir_oe[i]  = 1'b1;
            end else if (i == PIN_BUSY) begin : G_BUSY
                assign bidir_out[i] = dla_busy;
                assign bidir_oe[i]  = 1'b1;
            end else if (i == PIN_DONE) begin : G_DONE
                assign bidir_out[i] = dla_done;
                assign bidir_oe[i]  = 1'b1;
            end else if (i == PIN_WB_DONE) begin : G_WBDONE
                assign bidir_out[i] = dla_wb_done;
                assign bidir_oe[i]  = 1'b1;
            end else begin : G_IN_OR_UNUSED
                // SCLK/MOSI/CS_N (inputs) and the 13 spares: never drive.
                assign bidir_out[i] = 1'b0;
                assign bidir_oe[i]  = 1'b0;
            end

            assign bidir_cs[i] = 1'b0;                  // CMOS input threshold
            assign bidir_sl[i] = 1'b0;                  // fast slew
            assign bidir_ie[i] = ~bidir_oe[i];           // enable input path when not driving
            assign bidir_pu[i] = 1'b0;
            assign bidir_pd[i] = (i >= 7) ? 1'b1 : 1'b0; // pull down the 13 unused spares
        end
    endgenerate

endmodule

`default_nettype wire
