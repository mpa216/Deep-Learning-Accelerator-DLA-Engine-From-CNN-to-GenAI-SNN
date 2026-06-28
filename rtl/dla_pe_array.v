`timescale 1ns / 1ps

// N x N PE grid. Each PE receives one A row element and one B column element.
module dla_pe_array #(
    parameter N      = 4,
    parameter DATA_W = 8,
    parameter ACC_W  = 24
) (
    input                              clk,
    input                              rst_n,
    input                              clear,
    input                              en,
    input signed [(N*DATA_W)-1:0]      a_bus,
    input signed [(N*DATA_W)-1:0]      b_bus,
    output signed [(N*N*ACC_W)-1:0]    c_bus
);

    genvar i;
    genvar j;

    generate
        // Instantiate the PE matrix and repack each accumulator into c_bus.
        for (i = 0; i < N; i = i + 1) begin : GEN_PE_ROWS
            for (j = 0; j < N; j = j + 1) begin : GEN_PE_COLS
                localparam FLAT_IDX = (i*N) + j;
                wire signed [ACC_W-1:0] acc_val;

                dla_pe #(
                    .DATA_W(DATA_W),
                    .ACC_W(ACC_W)
                ) u_pe (
                    .clk(clk),
                    .rst_n(rst_n),
                    .clear(clear),
                    .en(en),
                    .a_in(a_bus[(i*DATA_W) +: DATA_W]),
                    .b_in(b_bus[(j*DATA_W) +: DATA_W]),
                    .acc_out(acc_val)
                );

                assign c_bus[(FLAT_IDX*ACC_W) +: ACC_W] = acc_val;
            end
        end
    endgenerate

endmodule
