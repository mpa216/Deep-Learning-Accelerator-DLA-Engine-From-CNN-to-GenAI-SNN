`timescale 1ns / 1ps

// Wrapper around GF180MCU 256x8 1RW SRAM macro.
module dla_sram_1rw_256x8 (
    input         clk,
    input         we,
    input  [7:0]  addr,
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

    // NOTE: the macro's physical VDD/VSS (inout power pins on the
    // blackbox) are intentionally left UNCONNECTED in RTL. Tying an
    // inout to a logic constant (.VDD(1'b1)/.VSS(1'b0)) is an electrical
    // short that Verilator rejects (PORTSHORT/UNSUPPORTED) and aborts
    // lint before synthesis. Power is connected physically during PnR by
    // PDN_MACRO_CONNECTIONS (".*u_sram.* VDD VSS VDD VSS") reading the
    // pins from the macro LEF -- same pattern as sram_rtl_friend.v.
    gf180mcu_ocd_ip_sram__sram256x8m8wm1 u_sram (
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
// Synthesis sees an empty black box -- LibreLane links the real
// .lef/.gds/.lib at place-and-route. Power pins follow the foundry
// USE_POWER_PINS convention so they are NOT tied to logic constants.
(* blackbox *)
module gf180mcu_ocd_ip_sram__sram256x8m8wm1 (
`ifdef USE_POWER_PINS
    inout        VDD,
    inout        VSS,
`endif
    input        CLK,
    input        CEN,
    input  [7:0] A,
    input        GWEN,
    input  [7:0] WEN,
    input  [7:0] D,
    output [7:0] Q
);
endmodule
`else
// Behavioral model for simulation (Icarus). Not read during synthesis.
module gf180mcu_ocd_ip_sram__sram256x8m8wm1 (
`ifdef USE_POWER_PINS
    inout        VDD,
    inout        VSS,
`endif
    input        CLK,
    input        CEN,
    input  [7:0] A,
    input        GWEN,
    input  [7:0] WEN,
    input  [7:0] D,
    output [7:0] Q
);
    reg [7:0] mem [0:255];
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
