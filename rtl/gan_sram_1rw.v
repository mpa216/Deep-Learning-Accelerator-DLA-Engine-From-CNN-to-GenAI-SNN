/// sta-blackbox
// ^ Same directive as rtl/gf180_sram_1rw_256x8.v: OpenSTA's Verilog reader only
//   parses gate-level netlists, so this file is skipped and blackboxed for STA.
//   Icarus, Verilator and Yosys all see it as an ordinary comment.
`timescale 1ns / 1ps

// Wrappers for the 64x8 and 1024x8 members of the GF180MCU OCD 3.3V SRAM family
// (SRAM_MACRO/gf180mcu_ocd_ip_sram-main/cells/).  rtl/gf180_sram_1rw_256x8.v already
// provides the 256x8; these two complete the set this design needs.
//
// WHY MORE THAN ONE SIZE: the family shares a fixed 301.3 um width and scales only in
// height, so wider-but-shallower is badly inefficient and deeper is a bargain:
//
//     64x8    45,861 um2   717 um2/byte     <- only worth it when 64 words is genuinely all you need
//    256x8    67,771 um2   265 um2/byte
//    512x8    96,985 um2   189 um2/byte
//   1024x8   155,414 um2   152 um2/byte     <- 43% cheaper than 4x 256x8 for the same 1 KiB
//
// So the C buffer (16 words ever used, of 256) drops to 64x8, and the activation and
// image buffers become single 1024x8 macros instead of banked 256x8s -- which also
// deletes the bank-select mux the image buffer used to need.
//
// All three sizes share the identical CLK/CEN/GWEN/WEN/D/Q interface and the same
// tt_025C_3v30 / ss_125C_3v00 / ff_n40C_3v60 corner set; only the address width differs.
// Their headers carry a "timing in the specify blocks needs revising for 3.3V" note --
// the already-taped-out 256x8 carries the same note, it is a family-wide disclaimer
// about the simulation model, not about the liberty data STA actually uses.

// ---------------------------------------------------------------------------
module gan_sram_1rw_64x8 (
    input         clk,
    input         we,
    input  [5:0]  addr,
    input  [7:0]  wdata,
    output [7:0]  rdata
);
    wire       cen  = 1'b0;
    wire       gwen = ~we;
    wire [7:0] wen  = we ? 8'h00 : 8'hFF;
    wire [7:0] q;

    // Macro power pins are deliberately left unconnected in RTL and joined by the
    // PDN during PnR (PDN_MACRO_CONNECTIONS) -- see bring-up note 1 in CLAUDE.md.
    gf180mcu_ocd_ip_sram__sram64x8m8wm1 u_sram (
        .CLK(clk), .CEN(cen), .A(addr), .GWEN(gwen), .WEN(wen), .D(wdata), .Q(q)
    );

    assign rdata = q;
endmodule

// ---------------------------------------------------------------------------
module gan_sram_1rw_1024x8 (
    input         clk,
    input         we,
    input  [9:0]  addr,
    input  [7:0]  wdata,
    output [7:0]  rdata
);
    wire       cen  = 1'b0;
    wire       gwen = ~we;
    wire [7:0] wen  = we ? 8'h00 : 8'hFF;
    wire [7:0] q;

    gf180mcu_ocd_ip_sram__sram1024x8m8wm1 u_sram (
        .CLK(clk), .CEN(cen), .A(addr), .GWEN(gwen), .WEN(wen), .D(wdata), .Q(q)
    );

    assign rdata = q;
endmodule

`ifdef SYNTHESIS
// Empty black boxes: LibreLane links the real .lef/.gds/.lib at place-and-route.
(* blackbox *)
module gf180mcu_ocd_ip_sram__sram64x8m8wm1 (
`ifdef USE_POWER_PINS
    inout        VDD,
    inout        VSS,
`endif
    input        CLK,
    input        CEN,
    input  [5:0] A,
    input        GWEN,
    input  [7:0] WEN,
    input  [7:0] D,
    output [7:0] Q
);
endmodule

(* blackbox *)
module gf180mcu_ocd_ip_sram__sram1024x8m8wm1 (
`ifdef USE_POWER_PINS
    inout        VDD,
    inout        VSS,
`endif
    input        CLK,
    input        CEN,
    input  [9:0] A,
    input        GWEN,
    input  [7:0] WEN,
    input  [7:0] D,
    output [7:0] Q
);
endmodule
`else
// Behavioural models for Icarus.  Identical semantics to the 256x8 model in
// rtl/gf180_sram_1rw_256x8.v -- registered read, per-bit active-low write mask.
module gf180mcu_ocd_ip_sram__sram64x8m8wm1 (
`ifdef USE_POWER_PINS
    inout        VDD,
    inout        VSS,
`endif
    input        CLK,
    input        CEN,
    input  [5:0] A,
    input        GWEN,
    input  [7:0] WEN,
    input  [7:0] D,
    output [7:0] Q
);
    reg [7:0] mem [0:63];
    reg [7:0] q_reg;
    integer i;

    assign Q = q_reg;

    always @(posedge CLK) begin
        if (!CEN) begin
            if (!GWEN) begin
                for (i = 0; i < 8; i = i + 1) begin
                    if (!WEN[i]) mem[A][i] <= D[i];
                end
            end
            q_reg <= mem[A];
        end
    end
endmodule

module gf180mcu_ocd_ip_sram__sram1024x8m8wm1 (
`ifdef USE_POWER_PINS
    inout        VDD,
    inout        VSS,
`endif
    input        CLK,
    input        CEN,
    input  [9:0] A,
    input        GWEN,
    input  [7:0] WEN,
    input  [7:0] D,
    output [7:0] Q
);
    reg [7:0] mem [0:1023];
    reg [7:0] q_reg;
    integer i;

    assign Q = q_reg;

    always @(posedge CLK) begin
        if (!CEN) begin
            if (!GWEN) begin
                for (i = 0; i < 8; i = i + 1) begin
                    if (!WEN[i]) mem[A][i] <= D[i];
                end
            end
            q_reg <= mem[A];
        end
    end
endmodule
`endif
