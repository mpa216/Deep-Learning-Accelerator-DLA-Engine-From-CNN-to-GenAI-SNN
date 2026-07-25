`timescale 1ns / 1ps
`default_nettype none

// Stage-2 padring chip_core for the experimental full-GAN chip.
//
// Same structure as the main branch's chip_core_dla.sv -- a 4-wire serial bridge in
// front of the hardened engine macro -- but wrapping gan_engine_top instead of
// dla_engine_top, and using three of the spare bidir pads for status the main-branch
// chip could not produce: the discriminator's verdict and the engine's activity.
//
// Bidir pin allocation (20 pads):
//   [0] SCLK (in)   [1] MOSI (in)   [2] CS_N (in)   [3] MISO (out)
//   [4] busy (out)      engine busy: the host polls this between commands
//   [5] dla_busy (out)  MAC array active
//   [6] dla_done (out)  MAC pass complete
//   [7] verdict (out)   D(generated) > 0.5 -- the generator fooled the discriminator
//   [8..19] unused (inputs, pulled down)
// clk/rst_n come from the padring's dedicated clock/reset pads.
//
// This file replaces the padring fork's src/chip_core.sv at integration time.
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

    assign input_pu = '0;
    assign input_pd = '0;

    wire _unused;
    assign _unused = &{1'b0, input_in, bidir_in[NUM_BIDIR_PADS-1:3], analog};

    localparam int PIN_SCLK     = 0;
    localparam int PIN_MOSI     = 1;
    localparam int PIN_CS_N     = 2;
    localparam int PIN_MISO     = 3;
    localparam int PIN_BUSY     = 4;
    localparam int PIN_DLA_BUSY = 5;
    localparam int PIN_DLA_DONE = 6;
    localparam int PIN_VERDICT  = 7;
    localparam int PIN_FIRST_SPARE = 8;

    wire sclk_pad = bidir_in[PIN_SCLK];
    wire mosi_pad = bidir_in[PIN_MOSI];
    wire cs_n_pad = bidir_in[PIN_CS_N];
    wire miso_pad;

    wire        w_wr_en, w_cfg_we, w_exec_req, w_rd_en;
    wire [1:0]  w_wr_sel, w_rd_sel;
    wire [9:0]  w_wr_addr, w_rd_addr;
    wire signed [7:0]  w_wr_data;
    wire [3:0]  w_cfg_addr, w_exec_op;
    wire signed [23:0] w_cfg_data, w_rd_data;
    wire [7:0]  w_exec_arg;
    wire        w_busy, w_verdict, w_dla_busy, w_dla_done;

    gan_serial_bridge u_bridge (
        .clk      (clk),
        .rst_n    (rst_n),
        .sclk_pad (sclk_pad),
        .mosi_pad (mosi_pad),
        .cs_n_pad (cs_n_pad),
        .miso_pad (miso_pad),
        .wr_en    (w_wr_en),
        .wr_sel   (w_wr_sel),
        .wr_addr  (w_wr_addr),
        .wr_data  (w_wr_data),
        .cfg_we   (w_cfg_we),
        .cfg_addr (w_cfg_addr),
        .cfg_data (w_cfg_data),
        .exec_req (w_exec_req),
        .exec_op  (w_exec_op),
        .exec_arg (w_exec_arg),
        .rd_en    (w_rd_en),
        .rd_sel   (w_rd_sel),
        .rd_addr  (w_rd_addr),
        .rd_data  (w_rd_data)
    );

    // Bare instantiation: the hardened gan_engine_top netlist carries no parameters,
    // and its VDD/VSS are connected physically by PDN_MACRO_CONNECTIONS, not in RTL
    // (same convention as the SRAM macros inside it -- see CLAUDE.md bring-up note 1).
    gan_engine_top u_gan (
        .clk      (clk),
        .rst_n    (rst_n),
        .wr_en    (w_wr_en),
        .wr_sel   (w_wr_sel),
        .wr_addr  (w_wr_addr),
        .wr_data  (w_wr_data),
        .cfg_we   (w_cfg_we),
        .cfg_addr (w_cfg_addr),
        .cfg_data (w_cfg_data),
        .exec_req (w_exec_req),
        .exec_op  (w_exec_op),
        .exec_arg (w_exec_arg),
        .rd_en    (w_rd_en),
        .rd_sel   (w_rd_sel),
        .rd_addr  (w_rd_addr),
        .rd_data  (w_rd_data),
        .busy     (w_busy),
        .verdict  (w_verdict),
        .dla_busy (w_dla_busy),
        .dla_done (w_dla_done)
    );

    genvar i;
    generate
        for (i = 0; i < NUM_BIDIR_PADS; i = i + 1) begin : GEN_BIDIR
            if (i == PIN_MISO) begin : G_MISO
                assign bidir_out[i] = miso_pad;
                assign bidir_oe[i]  = 1'b1;
            end else if (i == PIN_BUSY) begin : G_BUSY
                assign bidir_out[i] = w_busy;
                assign bidir_oe[i]  = 1'b1;
            end else if (i == PIN_DLA_BUSY) begin : G_DLA_BUSY
                assign bidir_out[i] = w_dla_busy;
                assign bidir_oe[i]  = 1'b1;
            end else if (i == PIN_DLA_DONE) begin : G_DLA_DONE
                assign bidir_out[i] = w_dla_done;
                assign bidir_oe[i]  = 1'b1;
            end else if (i == PIN_VERDICT) begin : G_VERDICT
                assign bidir_out[i] = w_verdict;
                assign bidir_oe[i]  = 1'b1;
            end else begin : G_IN_OR_UNUSED
                assign bidir_out[i] = 1'b0;
                assign bidir_oe[i]  = 1'b0;
            end

            assign bidir_cs[i] = 1'b0;                 // CMOS input threshold
            assign bidir_sl[i] = 1'b0;                 // fast slew
            assign bidir_ie[i] = ~bidir_oe[i];
            assign bidir_pu[i] = 1'b0;
            assign bidir_pd[i] = (i >= PIN_FIRST_SPARE) ? 1'b1 : 1'b0;
        end
    endgenerate

endmodule

`default_nettype wire
