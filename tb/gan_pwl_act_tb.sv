`timescale 1ns / 1ps

// Unit test for the 9-segment PWL activation unit and the -ln() unit built on it.
//
// Every threshold in every table is exercised on both sides, plus a sweep across the
// full Q4.12 input range, against scripts/gan_golden.py.  The tanh and sigmoid tables
// are the UAS_VLSI reference design's coefficients, so a pass here also demonstrates
// that this chip reproduces that design's activation behaviour exactly.
module gan_pwl_act_tb;

`include "gan_defs.vh"

    reg clk = 1'b0;
    reg rst_n = 1'b0;
    always #5 clk = ~clk;

    // ---- DUT: PWL ------------------------------------------------------------
    reg               req = 1'b0;
    reg  [2:0]        func = 3'd0;
    reg signed [15:0] x = 16'sd0;
    wire signed [15:0] y;
    wire              vld;

    gan_pwl_act u_dut (.clk(clk), .rst_n(rst_n), .req(req), .func(func), .x(x),
                       .y(y), .vld(vld));

    // ---- DUT: -ln() ----------------------------------------------------------
    reg               nl_req = 1'b0;
    reg  [12:0]       nl_y = 13'd0;
    wire signed [23:0] nl_out;
    wire              nl_vld;

    gan_nlog u_nlog (.clk(clk), .rst_n(rst_n), .req(nl_req), .y_q12(nl_y),
                     .nlog(nl_out), .vld(nl_vld));

    reg [35:0] pwl_vec  [0:2047];
    reg [39:0] nlog_vec [0:1023];
    integer n_pwl = 0, n_nlog = 0;
    integer errors = 0;
    integer i;

    reg [2:0]         v_func;
    reg signed [15:0] v_x, v_y;
    reg [12:0]        v_yin;
    reg signed [23:0] v_nlog;

    initial begin
        for (i = 0; i < 2048; i = i + 1) pwl_vec[i]  = 36'hxxxxxxxxx;
        for (i = 0; i < 1024; i = i + 1) nlog_vec[i] = 40'hxxxxxxxxxx;
        $readmemh("tb/data/gan_chip/gan_pwl_vectors.memh", pwl_vec);
        $readmemh("tb/data/gan_chip/gan_nlog_vectors.memh", nlog_vec);
        for (i = 0; i < 2048; i = i + 1) if (pwl_vec[i]  !== 36'hxxxxxxxxx) n_pwl  = i + 1;
        for (i = 0; i < 1024; i = i + 1) if (nlog_vec[i] !== 40'hxxxxxxxxxx) n_nlog = i + 1;
    end

    task check_pwl(input [2:0] f, input signed [15:0] xin, input signed [15:0] exp);
        begin
            @(posedge clk);
            req <= 1'b1; func <= f; x <= xin;
            @(posedge clk);
            req <= 1'b0;
            while (!vld) @(posedge clk);
            if (y !== exp) begin
                if (errors < 12)
                    $display("  MISMATCH func=%0d x=%0d: got %0d, expected %0d",
                             f, xin, y, exp);
                errors = errors + 1;
            end
        end
    endtask

    task check_nlog(input [12:0] yin, input signed [23:0] exp);
        begin
            @(posedge clk);
            nl_req <= 1'b1; nl_y <= yin;
            @(posedge clk);
            nl_req <= 1'b0;
            while (!nl_vld) @(posedge clk);
            if (nl_out !== exp) begin
                if (errors < 24)
                    $display("  MISMATCH nlog y=%0d: got %0d, expected %0d",
                             yin, nl_out, exp);
                errors = errors + 1;
            end
        end
    endtask

    initial begin
        $display("=== gan_pwl_act / gan_nlog unit test ===");
        repeat (4) @(posedge clk);
        rst_n <= 1'b1;
        repeat (4) @(posedge clk);

        $display("checking %0d PWL vectors (tanh, sigmoid, relu, lrelu, ident, log2m)...",
                 n_pwl);
        for (i = 0; i < n_pwl; i = i + 1) begin
            {v_func, v_x, v_y} = pwl_vec[i][34:0];
            check_pwl(v_func, v_x, v_y);
        end

        $display("checking %0d -ln(y) vectors...", n_nlog);
        for (i = 0; i < n_nlog; i = i + 1) begin
            {v_yin, v_nlog} = nlog_vec[i][36:0];
            check_nlog(v_yin, v_nlog);
        end

        if (errors == 0)
            $display("PASS: %0d/%0d vectors match scripts/gan_golden.py exactly",
                     n_pwl + n_nlog, n_pwl + n_nlog);
        else
            $display("FAIL: %0d mismatches out of %0d", errors, n_pwl + n_nlog);
        $finish;
    end

endmodule
