`timescale 1ns / 1ps

// C buffer stores N*N accumulated outputs in SRAM (24-bit via 3x8-bit macros).
// SRAM_DEPTH selects the macro: 256 is the main-branch tapeout's choice, 64 is the
// right-sized one.  Only N*N = 16 words are ever used, so a 256-deep macro wastes
// 94% of its capacity -- and on this SRAM family a 64x8 is 32% smaller than a 256x8.
// The default stays 256 so librelane/config.yaml and the signed-off dla_engine_top
// are unaffected; gan_engine_top overrides it to 64.
module dla_c_buffer_bank #(
    parameter N          = 4,
    parameter ACC_W      = 24,
    parameter ADDR_W     = (N*N <= 1) ? 1 : $clog2(N*N),
    parameter USE_SRAM   = 1,
    parameter SRAM_DEPTH = 256
) (
    input                              clk,
    input                              wr_en,
    input [ADDR_W-1:0]                 wr_addr,
    input signed [ACC_W-1:0]           wr_data,
    input                              rd_en,
    input [ADDR_W-1:0]                 rd_addr,
    output signed [ACC_W-1:0]          rd_data
);

    localparam integer C_DEPTH = N * N;
    localparam integer SRAM_ADDR_W = (SRAM_DEPTH == 64) ? 6 : 8;

    generate
        if (USE_SRAM) begin : GEN_SRAM
            wire [ADDR_W-1:0] rw_addr;
            wire [SRAM_ADDR_W-1:0] sram_addr;
            wire [7:0] q0;
            wire [7:0] q1;
            wire [7:0] q2;

            assign rw_addr = wr_en ? wr_addr : rd_addr;
            assign sram_addr = {{(SRAM_ADDR_W-ADDR_W){1'b0}}, rw_addr};

            if (SRAM_DEPTH == 64) begin : GEN_D64
                gan_sram_1rw_64x8 u_sram0 (
                    .clk(clk), .we(wr_en), .addr(sram_addr),
                    .wdata(wr_data[7:0]),   .rdata(q0));
                gan_sram_1rw_64x8 u_sram1 (
                    .clk(clk), .we(wr_en), .addr(sram_addr),
                    .wdata(wr_data[15:8]),  .rdata(q1));
                gan_sram_1rw_64x8 u_sram2 (
                    .clk(clk), .we(wr_en), .addr(sram_addr),
                    .wdata(wr_data[23:16]), .rdata(q2));
            end else begin : GEN_D256
                dla_sram_1rw_256x8 u_sram0 (
                    .clk(clk), .we(wr_en), .addr(sram_addr),
                    .wdata(wr_data[7:0]),   .rdata(q0));
                dla_sram_1rw_256x8 u_sram1 (
                    .clk(clk), .we(wr_en), .addr(sram_addr),
                    .wdata(wr_data[15:8]),  .rdata(q1));
                dla_sram_1rw_256x8 u_sram2 (
                    .clk(clk), .we(wr_en), .addr(sram_addr),
                    .wdata(wr_data[23:16]), .rdata(q2));
            end

            assign rd_data = {q2, q1, q0};
        end else begin : GEN_REG
            reg signed [ACC_W-1:0] mem [0:C_DEPTH-1];
            reg signed [ACC_W-1:0] rd_reg;

            always @(posedge clk) begin
                if (wr_en) begin
                    mem[wr_addr] <= wr_data;
                end
                if (rd_en) begin
                    rd_reg <= mem[rd_addr];
                end
            end

            assign rd_data = rd_reg;
        end
    endgenerate

endmodule
