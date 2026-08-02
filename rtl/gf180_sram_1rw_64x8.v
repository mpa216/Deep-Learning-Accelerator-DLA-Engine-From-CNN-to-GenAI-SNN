/// sta-blackbox
// ^ Same directive, and for the same reason, as gf180_sram_1rw_256x8.v: OpenSTA's
//   Verilog reader only parses gate-level netlists, so this file is blackboxed for
//   STA and read normally by Icarus, Verilator and Yosys.
`timescale 1ns / 1ps

// Wrapper around the GF180MCU 64x8 1RW SRAM macro.
//
// The C buffer is the only user.  It needs 48 bytes (16 accumulators x 3 byte
// planes) and 64 is the shallowest depth this SRAM family offers, so this is the
// smallest macro the design can be built from: 301.3 x 152.21 = 45,861 um2 against
// 67,771 um2 for the 256-deep part it replaces.
module dla_sram_1rw_64x8 (
    input         clk,
    input         we,
    input  [5:0]  addr,
    input  [7:0]  wdata,
    output [7:0]  rdata
);
    wire       cen;
    wire       gwen;
    wire [7:0] wen;
    wire [7:0] q;

    assign cen  = 1'b0;            // Active-low chip enable.
    assign gwen = ~we;             // Active-low global write enable.
    assign wen  = we ? 8'h00 : 8'hFF; // Active-low per-bit write mask.

    // Macro VDD/VSS deliberately left unconnected in RTL -- see the long note in
    // gf180_sram_1rw_256x8.v.  Power arrives physically via PDN_MACRO_CONNECTIONS.
    gf180mcu_ocd_ip_sram__sram64x8m8wm1 u_sram (
        .CLK(clk),
        .CEN(cen),
        .A(addr),
        .GWEN(gwen),
        .WEN(wen),
        .D(wdata),
        .Q(q)
    );

    assign rdata = q;
endmodule

`ifdef SYNTHESIS
// Synthesis sees an empty black box -- LibreLane links the real .lef/.gds/.lib at
// place-and-route.  Power pins follow the foundry USE_POWER_PINS convention.
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
`else
// Behavioral model for simulation (Icarus).  Not read during synthesis.
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
                    if (!WEN[i]) begin
                        mem[A][i] <= D[i];
                    end
                end
            end
            q_reg <= mem[A];
        end
    end
endmodule
`endif
