`timescale 1ns / 1ps

// Verifies study/fp16_mac.v against the model in scripts/gen_fp16_vectors.py.
//
// The FP16 area number quoted in the operand-width study is only meaningful if the unit
// being synthesised computes the right thing, so this replays a recorded sequence of
// multiply-accumulate steps and checks the binary32 accumulator after every one.
//
//   python3 scripts/gen_fp16_vectors.py --n 8192
//   iverilog -g2012 -s fp16_mac_tb -o sim/results/fp16_mac_tb.vvp \
//     study/fp16_mac.v study/fp16_mac_tb.sv
//   vvp sim/results/fp16_mac_tb.vvp
module fp16_mac_tb;

    localparam integer NVEC = 8192;

    reg clk = 1'b0;
    reg rst_n = 1'b0;
    reg clear = 1'b0;
    reg en = 1'b0;
    reg [15:0] a_in = 16'd0, b_in = 16'd0;
    wire [31:0] acc_out;
    always #5 clk = ~clk;

    fp16_mac dut (.clk(clk), .rst_n(rst_n), .clear(clear), .en(en),
                  .a_in(a_in), .b_in(b_in), .acc_out(acc_out));

    reg [63:0] vec [0:NVEC-1];
    integer i, errors = 0, checked = 0;

    initial $readmemh("tb/data/fp16_vectors.memh", vec);

    initial begin
        $display("=== fp16_mac vs scripts/gen_fp16_vectors.py ===");
        repeat (4) @(posedge clk);
        rst_n <= 1'b1;
        repeat (2) @(posedge clk);

        for (i = 0; i < NVEC; i = i + 1) begin
            // The generator restarts the dot product every 256 steps.
            if (i % 256 == 0) begin
                @(posedge clk);
                clear <= 1'b1;
                @(posedge clk);
                clear <= 1'b0;
            end
            a_in <= vec[i][63:48];
            b_in <= vec[i][47:32];
            en   <= 1'b1;
            @(posedge clk);
            en   <= 1'b0;
            @(posedge clk);
            checked = checked + 1;
            if (acc_out !== vec[i][31:0]) begin
                errors = errors + 1;
                if (errors <= 8)
                    $display("  step %0d: a=%04x b=%04x  got %08x, expected %08x",
                             i, vec[i][63:48], vec[i][47:32], acc_out, vec[i][31:0]);
            end
        end

        $display("  checked %0d MAC steps", checked);
        if (errors == 0)
            $display("PASS: fp16_mac matches the model bit-exactly");
        else
            $display("FAIL: %0d mismatches", errors);
        $finish;
    end

endmodule
