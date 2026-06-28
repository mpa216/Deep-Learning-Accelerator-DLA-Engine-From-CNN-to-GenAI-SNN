`timescale 1ns / 1ps

// Processing Element (PE): accumulates a*b when enabled.
module dla_pe #(
    parameter DATA_W = 8,
    parameter ACC_W  = 24
) (
    input                          clk,
    input                          rst_n,
    input                          clear,
    input                          en,
    input signed [DATA_W-1:0]      a_in,
    input signed [DATA_W-1:0]      b_in,
    output reg signed [ACC_W-1:0]  acc_out
);

    wire signed [(2*DATA_W)-1:0] mult_res;
    wire signed [ACC_W-1:0]      mult_ext;

    // Multiply in DATA_W domain, then sign-extend to accumulator width.
    assign mult_res = a_in * b_in;
    assign mult_ext = {{(ACC_W-(2*DATA_W)){mult_res[(2*DATA_W)-1]}}, mult_res};

    // Synchronous clear + accumulate datapath.
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            acc_out <= {ACC_W{1'b0}};
        end else if (clear) begin
            acc_out <= {ACC_W{1'b0}};
        end else if (en) begin
            acc_out <= acc_out + mult_ext;
        end
    end

endmodule
