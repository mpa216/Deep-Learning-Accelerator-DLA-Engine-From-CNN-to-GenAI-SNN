`timescale 1ns / 1ps
`default_nettype none

// ============================================================================
// dla_link_sel -- serial-link source select for the LVDS receiver integration
// (handoff "Mode A": the three bridge inputs SCLK / MOSI / CS_N can come either
// from the legacy CMOS pads or from the three lanes of the lvds_rx_x3 macro).
//
// LINK_SEL is a static strap from an input_cmos pad whose weak pull-down is
// enabled, so an unbonded or undriven pad reads 0 = legacy CMOS pins.  It is
// asynchronous to clk and is double-flop synchronised here.
//
//   lvds_en      the synchronised strap; drives the receiver's EN pin.
//   lvds_active  1 = the bridge reads the receiver outputs.  Rises only after
//                lvds_en has been high for WAKE_CLKS consecutive clk cycles, so
//                the bridge never sees the receiver while it is off or waking
//                (EN = 0 forces every RXk_O LOW, which on the CS_N lane would
//                read as a selected frame).  Falls together with lvds_en (same
//                clock edge, combinational AND), before the receiver outputs can
//                move, so leaving LVDS mode needs no wait.
//
// Reset: rst_n (asynchronous assert) clears everything, so EN stays LOW while
// the chip is held in reset.  The macro's power-up rule "EN low until VDD >=
// 2.0 V" (decision D-008, KNOWN_LIMITS en_and_supply) therefore holds whenever
// the board keeps rst_n low through the supply ramp, which the core needs anyway.
//
// Host rule: change LINK_SEL only while CS_N is high on BOTH links (the bridge
// aborts any frame whose CS_N reads high, so a switch between frames is safe).
// Proven properties: formal/dla_link_sel.sby.
// ============================================================================
module dla_link_sel #(
    parameter integer WAKE_CLKS = 64   // 64 x 40 ns = 2.56 us; receiver valid time <= 1 us (spec, TB8)
) (
    input  wire clk,
    input  wire rst_n,
    input  wire link_sel_pad,   // asynchronous strap: 0 = CMOS pins, 1 = LVDS lanes
    output wire lvds_en,        // receiver enable (macro pin EN)
    output wire lvds_active     // 1 = bridge inputs come from the receiver
);
    localparam integer CW = (WAKE_CLKS > 1) ? $clog2(WAKE_CLKS) : 1;
    localparam integer  WAKE_LAST_I = WAKE_CLKS - 1;
    localparam [CW-1:0] WAKE_LAST   = WAKE_LAST_I[CW-1:0];

    reg [1:0]    sync;       // 2-FF synchroniser for the strap
    reg [CW-1:0] wake_cnt;   // cycles of lvds_en high, while waking
    reg          awake;      // wake period complete

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sync     <= 2'b00;
            wake_cnt <= {CW{1'b0}};
            awake    <= 1'b0;
        end else begin
            sync <= {sync[0], link_sel_pad};
            if (!sync[1]) begin
                wake_cnt <= {CW{1'b0}};
                awake    <= 1'b0;
            end else if (!awake) begin
                wake_cnt <= wake_cnt + 1'b1;
                if (wake_cnt == WAKE_LAST) awake <= 1'b1;
            end
        end
    end

    assign lvds_en     = sync[1];
    assign lvds_active = awake & sync[1];
endmodule

`default_nettype wire
