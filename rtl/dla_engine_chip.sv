`timescale 1ns / 1ps
`default_nettype none

// ============================================================================
// dla_engine_chip -- CHIP-LEVEL (padframe-facing) top for Chipathon 2026
// project A56, block "ACV".
//
// Wraps the eight-macro accelerator core (dla_engine_top: A x4 + B x4 SRAM
// macros, flip-flop C buffer) with the 4-wire serial bridge
// (dla_serial_bridge) and exposes ONLY the user pins of the ACV padframe (11 signed-off + 7 LVDS),
// each expanded to the gf180 I/O-cell terminals that the project floorplan
// template (A56_ACV.def) pins by name.  This is the design that hardens into
// the 1675 x 1110 um ACV project region via FP_DEF_TEMPLATE; the pad CELLS
// themselves live in the organiser's shared padring, outside this boundary.
//
// A56 ACV pin map (layout_announcement/A56.def/.../A56_ACV_pad_map.yaml, the
// 2026-08-25 frame; pins land on the slots in info.yaml order):
//   W12 clk (in_s)   W13 rst_n (in_c)
//   W14 SCLK  W15 MOSI  W16 CS_N  W17 MISO  W18 busy  W19 done  W20 wb_done  (bi_24t)
//   W21 DVDD (dvdd)   W22 DVSS (dvss)
// LVDS integration (branch lvds-integration), appended after DVSS on the free
// north slots of the same frame (librelane/A56_ACV_lvds.def):
//   N01 LINK_SEL (in_c): serial-link source strap, pad pull-down = CMOS pins
//   N02/N03 LVDS_SCLK_P/N   N04/N05 LVDS_MOSI_P/N   N06/N07 LVDS_CSN_P/N
//   (asig_5p0 analog pads -> the lvds_rx_x3 hard macro u_lvds, lanes 0/1/2)
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
    // --- W12 clk (in_s) ---
    input  wire clk,
    output wire clk_PU,
    output wire clk_PD,
    // --- W13 rst_n (in_c) ---
    input  wire rst_n,
    output wire rst_n_PU,
    output wire rst_n_PD,

    // --- W14 SCLK (bi_24t, host -> chip) ---
    input  wire SCLK_IN,
    output wire SCLK_OUT,
    output wire SCLK_OE,
    output wire SCLK_IE,
    output wire SCLK_CS,
    output wire SCLK_SL,
    output wire SCLK_PU,
    output wire SCLK_PD,
    // --- W15 MOSI (bi_24t, host -> chip) ---
    input  wire MOSI_IN,
    output wire MOSI_OUT,
    output wire MOSI_OE,
    output wire MOSI_IE,
    output wire MOSI_CS,
    output wire MOSI_SL,
    output wire MOSI_PU,
    output wire MOSI_PD,
    // --- W16 CS_N (bi_24t, host -> chip) ---
    input  wire CS_N_IN,
    output wire CS_N_OUT,
    output wire CS_N_OE,
    output wire CS_N_IE,
    output wire CS_N_CS,
    output wire CS_N_SL,
    output wire CS_N_PU,
    output wire CS_N_PD,
    // --- W17 MISO (bi_24t, chip -> host) ---
    input  wire MISO_IN,
    output wire MISO_OUT,
    output wire MISO_OE,
    output wire MISO_IE,
    output wire MISO_CS,
    output wire MISO_SL,
    output wire MISO_PU,
    output wire MISO_PD,
    // --- W18 busy (bi_24t, chip -> host) ---
    input  wire busy_IN,
    output wire busy_OUT,
    output wire busy_OE,
    output wire busy_IE,
    output wire busy_CS,
    output wire busy_SL,
    output wire busy_PU,
    output wire busy_PD,
    // --- W19 done (bi_24t, chip -> host) ---
    input  wire done_IN,
    output wire done_OUT,
    output wire done_OE,
    output wire done_IE,
    output wire done_CS,
    output wire done_SL,
    output wire done_PU,
    output wire done_PD,
    // --- W20 wb_done (bi_24t, chip -> host) ---
    input  wire wb_done_IN,
    output wire wb_done_OUT,
    output wire wb_done_OE,
    output wire wb_done_IE,
    output wire wb_done_CS,
    output wire wb_done_SL,
    output wire wb_done_PU,
    output wire wb_done_PD,

    // --- N01 LINK_SEL (in_c): 0 = CMOS serial pins (default), 1 = LVDS lanes ---
    input  wire LINK_SEL,
    output wire LINK_SEL_PU,
    output wire LINK_SEL_PD,
    // --- N02..N07 LVDS pairs (asig_5p0 analog pads, straight to the macro) ---
    inout  wire LVDS_SCLK_P,
    inout  wire LVDS_SCLK_N,
    inout  wire LVDS_MOSI_P,
    inout  wire LVDS_MOSI_N,
    inout  wire LVDS_CSN_P,
    inout  wire LVDS_CSN_N
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

    // ---- LVDS link (Mode A): three receiver lanes in front of the bridge ----
    // LINK_SEL pad: weak pull-down on, so an unbonded / undriven strap = CMOS.
    assign LINK_SEL_PU = 1'b0;
    assign LINK_SEL_PD = 1'b1;

    wire rx_sclk, rx_mosi, rx_cs_n;     // receiver outputs, asynchronous to clk
    wire lvds_en, lvds_active;

    // Hard macro (LEF/GDS in macros/lvds_rx_x3/; SYNTHESIS = blackbox).  Its
    // VDD/VSS pins are tied to DVDD/DVSS by the PDN (PDN_MACRO_CONNECTIONS),
    // never in RTL.  Lane 0 = SCLK, lane 1 = MOSI, lane 2 = CS_N (same polarity
    // as the CMOS pins: RXk_O = 1 when P > N).
    lvds_rx_x3 u_lvds (
        .RX0_P (LVDS_SCLK_P), .RX0_N (LVDS_SCLK_N),
        .RX1_P (LVDS_MOSI_P), .RX1_N (LVDS_MOSI_N),
        .RX2_P (LVDS_CSN_P),  .RX2_N (LVDS_CSN_N),
        .EN    (lvds_en),
        .RX0_O (rx_sclk),
        .RX1_O (rx_mosi),
        .RX2_O (rx_cs_n)
    );

    // Synchronise the strap, enable the receiver, switch after its wake time.
    dla_link_sel #(.WAKE_CLKS(64)) u_link_sel (
        .clk          (clk),
        .rst_n        (rst_n),
        .link_sel_pad (LINK_SEL),
        .lvds_en      (lvds_en),
        .lvds_active  (lvds_active)
    );

    // Static source mux in front of the UNCHANGED bridge synchronisers: the
    // bridge double-flops whichever source is selected, exactly as before.
    wire sclk_src = lvds_active ? rx_sclk : SCLK_IN;
    wire mosi_src = lvds_active ? rx_mosi : MOSI_IN;
    wire cs_n_src = lvds_active ? rx_cs_n : CS_N_IN;

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
        .sclk_pad (sclk_src),
        .mosi_pad (mosi_src),
        .cs_n_pad (cs_n_src),
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
