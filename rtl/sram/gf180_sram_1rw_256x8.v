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

    gf180mcu_ocd_ip_sram__sram256x8m8wm1 u_sram (
        .CLK(clk),
        .CEN(cen),
        .A(addr),
        .GWEN(gwen),
        .WEN(wen),
        .D(wdata),
        .Q(q),
        .VDD(1'b1),
        .VSS(1'b0)
    );

    assign rdata = q;
endmodule

`ifdef SYNTHESIS
(* blackbox *)
module gf180mcu_ocd_ip_sram__sram256x8m8wm1 (
    input        CLK,
    input        CEN,
    input  [7:0] A,
    input        GWEN,
    input  [7:0] WEN,
    input  [7:0] D,
    output [7:0] Q,
    input        VDD,
    input        VSS
);
endmodule
`else
module gf180mcu_ocd_ip_sram__sram256x8m8wm1 (
    input        CLK,
    input        CEN,
    input  [7:0] A,
    input        GWEN,
    input  [7:0] WEN,
    input  [7:0] D,
    output [7:0] Q,
    input        VDD,
    input        VSS
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
