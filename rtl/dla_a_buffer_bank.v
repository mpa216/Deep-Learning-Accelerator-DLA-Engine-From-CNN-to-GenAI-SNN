`timescale 1ns / 1ps

// A buffer stores matrix A as [row][k] and returns a full row-vector at rd_col=k.
module dla_a_buffer_bank #(
    parameter N        = 4,
    parameter K        = 4,
    parameter DATA_W   = 8,
    parameter ADDR_W   = (N*K <= 1) ? 1 : $clog2(N*K),
    parameter K_IDX_W  = (K <= 1) ? 1 : $clog2(K),
    parameter USE_SRAM = 1
) (
    input                              clk,
    input                              wr_en,
    input [ADDR_W-1:0]                 wr_addr,
    input signed [DATA_W-1:0]          wr_data,
    input [K_IDX_W-1:0]                rd_col,
    output reg signed [(N*DATA_W)-1:0] row_vector
);

    localparam ROW_W        = (N <= 1) ? 1 : $clog2(N);
    localparam SRAM_ADDR_W  = 8; // 256-depth SRAM
    // USE_SRAM assumes DATA_W=8 to match the macro data width.

    wire [ROW_W-1:0]   wr_row;
    wire [K_IDX_W-1:0] wr_col;

    assign wr_row = wr_addr / K;
    assign wr_col = wr_addr - (wr_row * K);

    generate
        if (USE_SRAM) begin : GEN_SRAM
            wire signed [DATA_W-1:0] sram_q [0:N-1];

            genvar r;
            for (r = 0; r < N; r = r + 1) begin : GEN_A_ROWS
                localparam [ROW_W-1:0] ROW_IDX = r[ROW_W-1:0];
                wire row_we;
                wire [K_IDX_W-1:0] row_addr;
                wire [SRAM_ADDR_W-1:0] sram_addr;
                wire [7:0] sram_q_raw;

                assign row_we   = wr_en && (wr_row == ROW_IDX);
                assign row_addr = row_we ? wr_col : rd_col;
                assign sram_addr = {{(SRAM_ADDR_W-K_IDX_W){1'b0}}, row_addr};

                dla_sram_1rw_256x8 u_sram (
                    .clk(clk),
                    .we(row_we),
                    .addr(sram_addr),
                    .wdata(wr_data[7:0]),
                    .rdata(sram_q_raw)
                );

                assign sram_q[ROW_IDX] = sram_q_raw;
            end

            integer i;
            always @* begin
                row_vector = {(N*DATA_W){1'b0}};
                for (i = 0; i < N; i = i + 1) begin
                    row_vector[(i*DATA_W) +: DATA_W] = sram_q[i];
                end
            end
        end else begin : GEN_REG
            reg signed [DATA_W-1:0] mem [0:(N*K)-1];
            integer i;

            // Single-port synchronous write using linearized row-major addressing.
            always @(posedge clk) begin
                if (wr_en) begin
                    mem[wr_addr] <= wr_data;
                end
            end

            // Registered read: 1-cycle latency to match the SRAM path so
            // the design stays bit-true under SRAM_LATENCY=1.
            always @(posedge clk) begin
                for (i = 0; i < N; i = i + 1) begin
                    row_vector[(i*DATA_W) +: DATA_W] <= mem[(i*K) + rd_col];
                end
            end
        end
    endgenerate

endmodule
