`timescale 1ns / 1ps

// B buffer stores matrix B as [k][col] and returns a full k-row at rd_row=k.
module dla_b_buffer_bank #(
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
    input [K_IDX_W-1:0]                rd_row,
    output reg signed [(N*DATA_W)-1:0] col_vector
);

    localparam COL_W        = (N <= 1) ? 1 : $clog2(N);
    localparam SRAM_ADDR_W  = 8; // 256-depth SRAM
    // USE_SRAM assumes DATA_W=8 to match the macro data width.

    wire [K_IDX_W-1:0] wr_row;
    wire [COL_W-1:0]   wr_col;

    assign wr_row = wr_addr / N;
    assign wr_col = wr_addr - (wr_row * N);

    generate
        if (USE_SRAM) begin : GEN_SRAM
            wire signed [DATA_W-1:0] sram_q [0:N-1];

            genvar c;
            for (c = 0; c < N; c = c + 1) begin : GEN_B_COLS
                localparam [COL_W-1:0] COL_IDX = c[COL_W-1:0];
                wire col_we;
                wire [K_IDX_W-1:0] col_addr;
                wire [SRAM_ADDR_W-1:0] sram_addr;
                wire [7:0] sram_q_raw;

                assign col_we   = wr_en && (wr_col == COL_IDX);
                assign col_addr = col_we ? wr_row : rd_row;
                assign sram_addr = {{(SRAM_ADDR_W-K_IDX_W){1'b0}}, col_addr};

                dla_sram_1rw_256x8 u_sram (
                    .clk(clk),
                    .we(col_we),
                    .addr(sram_addr),
                    .wdata(wr_data[7:0]),
                    .rdata(sram_q_raw)
                );

                assign sram_q[COL_IDX] = sram_q_raw;
            end

            integer j;
            always @* begin
                col_vector = {(N*DATA_W){1'b0}};
                for (j = 0; j < N; j = j + 1) begin
                    col_vector[(j*DATA_W) +: DATA_W] = sram_q[j];
                end
            end
        end else begin : GEN_REG
            reg signed [DATA_W-1:0] mem [0:(N*K)-1];
            integer j;

            // Single-port synchronous write using linearized row-major addressing.
            always @(posedge clk) begin
                if (wr_en) begin
                    mem[wr_addr] <= wr_data;
                end
            end

            // Registered read: 1-cycle latency to match the SRAM path so
            // the design stays bit-true under SRAM_LATENCY=1.
            always @(posedge clk) begin
                for (j = 0; j < N; j = j + 1) begin
                    col_vector[(j*DATA_W) +: DATA_W] <= mem[(rd_row*N) + j];
                end
            end
        end
    endgenerate

endmodule
