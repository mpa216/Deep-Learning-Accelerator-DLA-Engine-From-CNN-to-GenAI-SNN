`timescale 1ns / 1ps
`default_nettype none

// ============================================================================
// dla_engine_chip -- CHIP-LEVEL (padframe-facing) top for Chipathon 2026
// project A56, block "ACV".
//
// Wraps the eight-macro accelerator core (dla_engine_top: A x4 + B x4 SRAM
// macros, flip-flop C buffer) with the 4-wire serial bridge
// (dla_serial_bridge) and exposes ONLY the 11 user pins of the ACV padframe,
// each expanded to the gf180 I/O-cell terminals that the project floorplan
// template (A56_ACV.def) pins by name.  This is the design that hardens into
// the 1675 x 1110 um ACV project region via FP_DEF_TEMPLATE; the pad CELLS
// themselves live in the organiser's shared padring, outside this boundary.
//
// A56 ACV pin map (A56_ACV_pad_map.yaml):  W12 = fixed down-bonded quiet
// ground of the quadrant (in the frame, not a design pin), then:
//   W13 clk (in_s)   W14 rst_n (in_c)
//   W15 SCLK  W16 MOSI  W17 CS_N  W18 MISO  W19 busy  W20 done  W21 wb_done  (bi_24t)
//   W22 DVDD (dvdd)   N01 DVSS (dvss)
//
// Pad terminals (project's perspective):
//   bi_24t : *_IN = pad Y (pad->core, INPUT)   *_OUT = pad A (core->pad, OUTPUT)
//            *_OE = output-driver enable        *_IE  = input-receiver enable
//            *_CS = CMOS/schmitt threshold sel  *_SL  = slew-rate select
//            *_PU / *_PD = pad pull-up / pull-down enables
//   in_s/in_c : plain signal (pad Y) + *_PU / *_PD only.
//
// SCLK/MOSI/CS_N are host->chip inputs   -> OE=0, IE=1.
// MISO/busy/done/wb_done are chip->host  -> OE=1, IE=0.
// CS/SL/PU/PD are all tied 0 (CMOS threshold, fast slew, no pad pulls): the
// external 3.3 V host drives every line.
//
// Power (DVDD/DVSS) is NOT an RTL port -- it is handled physically by the PDN
// via VDD_NETS/GND_NETS + FP_TEMPLATE_COPY_POWER_PINS, exactly as the core's
// own supplies are (the signed-off dla_engine_top has no power ports either).
// ============================================================================
module dla_engine_chip (
    // --- W13 clk (in_s) ---
    input  wire clk,
    output wire clk_PU,
    output wire clk_PD,
    // --- W14 rst_n (in_c) ---
    input  wire rst_n,
    output wire rst_n_PU,
    output wire rst_n_PD,

    // --- W15 SCLK (bi_24t, host -> chip) ---
    input  wire SCLK_IN,
    output wire SCLK_OUT,
    output wire SCLK_OE,
    output wire SCLK_IE,
    output wire SCLK_CS,
    output wire SCLK_SL,
    output wire SCLK_PU,
    output wire SCLK_PD,
    // --- W16 MOSI (bi_24t, host -> chip) ---
    input  wire MOSI_IN,
    output wire MOSI_OUT,
    output wire MOSI_OE,
    output wire MOSI_IE,
    output wire MOSI_CS,
    output wire MOSI_SL,
    output wire MOSI_PU,
    output wire MOSI_PD,
    // --- W17 CS_N (bi_24t, host -> chip) ---
    input  wire CS_N_IN,
    output wire CS_N_OUT,
    output wire CS_N_OE,
    output wire CS_N_IE,
    output wire CS_N_CS,
    output wire CS_N_SL,
    output wire CS_N_PU,
    output wire CS_N_PD,
    // --- W18 MISO (bi_24t, chip -> host) ---
    input  wire MISO_IN,
    output wire MISO_OUT,
    output wire MISO_OE,
    output wire MISO_IE,
    output wire MISO_CS,
    output wire MISO_SL,
    output wire MISO_PU,
    output wire MISO_PD,
    // --- W19 busy (bi_24t, chip -> host) ---
    input  wire busy_IN,
    output wire busy_OUT,
    output wire busy_OE,
    output wire busy_IE,
    output wire busy_CS,
    output wire busy_SL,
    output wire busy_PU,
    output wire busy_PD,
    // --- W20 done (bi_24t, chip -> host) ---
    input  wire done_IN,
    output wire done_OUT,
    output wire done_OE,
    output wire done_IE,
    output wire done_CS,
    output wire done_SL,
    output wire done_PU,
    output wire done_PD,
    // --- W21 wb_done (bi_24t, chip -> host) ---
    input  wire wb_done_IN,
    output wire wb_done_OUT,
    output wire wb_done_OE,
    output wire wb_done_IE,
    output wire wb_done_CS,
    output wire wb_done_SL,
    output wire wb_done_PU,
    output wire wb_done_PD
);

    // ---- dedicated input pads: no pulls ----
    assign clk_PU   = 1'b0;  assign clk_PD   = 1'b0;
    assign rst_n_PU = 1'b0;  assign rst_n_PD = 1'b0;

    // ---- host -> chip input pads (SCLK/MOSI/CS_N): driver off, receiver on ----
    assign SCLK_OUT = 1'b0; assign SCLK_OE = 1'b0; assign SCLK_IE = 1'b1;
    assign SCLK_CS  = 1'b0; assign SCLK_SL = 1'b0; assign SCLK_PU = 1'b0; assign SCLK_PD = 1'b0;
    assign MOSI_OUT = 1'b0; assign MOSI_OE = 1'b0; assign MOSI_IE = 1'b1;
    assign MOSI_CS  = 1'b0; assign MOSI_SL = 1'b0; assign MOSI_PU = 1'b0; assign MOSI_PD = 1'b0;
    assign CS_N_OUT = 1'b0; assign CS_N_OE = 1'b0; assign CS_N_IE = 1'b1;
    assign CS_N_CS  = 1'b0; assign CS_N_SL = 1'b0; assign CS_N_PU = 1'b0; assign CS_N_PD = 1'b0;

    // ---- core <-> bridge nets ----
    wire        dla_start, dla_wr_en, dla_wr_sel, dla_rd_en;
    wire [9:0]  dla_wr_addr;
    wire signed [7:0]  dla_wr_data;
    wire [3:0]  dla_rd_addr;
    wire signed [23:0] dla_rd_data;
    wire        dla_wb_done, dla_done, dla_busy;
    wire        miso;

    dla_serial_bridge #(
        .AB_ADDR_W (10),
        .C_ADDR_W  (4),
        .DATA_W    (8),
        .ACC_W     (24)
    ) u_bridge (
        .clk      (clk),
        .rst_n    (rst_n),
        .sclk_pad (SCLK_IN),
        .mosi_pad (MOSI_IN),
        .cs_n_pad (CS_N_IN),
        .miso_pad (miso),
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
    // defaults, i.e. the exact configuration of the signed-off longtin core.
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

    // ---- chip -> host output pads: drive A, output driver on, receiver off ----
    assign MISO_OUT    = miso;        assign MISO_OE    = 1'b1; assign MISO_IE    = 1'b0;
    assign MISO_CS     = 1'b0; assign MISO_SL     = 1'b0; assign MISO_PU     = 1'b0; assign MISO_PD     = 1'b0;
    assign busy_OUT    = dla_busy;    assign busy_OE    = 1'b1; assign busy_IE    = 1'b0;
    assign busy_CS     = 1'b0; assign busy_SL     = 1'b0; assign busy_PU     = 1'b0; assign busy_PD     = 1'b0;
    assign done_OUT    = dla_done;    assign done_OE    = 1'b1; assign done_IE    = 1'b0;
    assign done_CS     = 1'b0; assign done_SL     = 1'b0; assign done_PU     = 1'b0; assign done_PD     = 1'b0;
    assign wb_done_OUT = dla_wb_done; assign wb_done_OE = 1'b1; assign wb_done_IE = 1'b0;
    assign wb_done_CS  = 1'b0; assign wb_done_SL  = 1'b0; assign wb_done_PU  = 1'b0; assign wb_done_PD  = 1'b0;

    // ---- keep the unused pad-input feedbacks (Y of the output pads) alive ----
    wire _unused;
    assign _unused = &{1'b0, MISO_IN, busy_IN, done_IN, wb_done_IN};

endmodule

`default_nettype wire
