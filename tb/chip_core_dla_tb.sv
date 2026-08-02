`timescale 1ns / 1ps

// End-to-end testbench for the Stage-2 serial bridge: drives chip_core's
// bidir pads exactly like an external host would (SCLK/MOSI/CS_N in,
// MISO/busy/done/wb_done out) and verifies the whole chain -- serial
// bridge -> dla_engine_top -- reproduces the d3004n4 golden vectors.
module chip_core_dla_tb;
    localparam int NUM_INPUT_PADS  = 1;
    localparam int NUM_BIDIR_PADS  = 20;
    localparam int NUM_ANALOG_PADS = 60;

    localparam int N = 4;
    localparam int K = 256;

    reg clk;
    reg rst_n;

    reg  [NUM_INPUT_PADS-1:0] input_in;
    wire [NUM_INPUT_PADS-1:0] input_pu, input_pd;

    reg  [NUM_BIDIR_PADS-1:0] bidir_in;
    wire [NUM_BIDIR_PADS-1:0] bidir_out, bidir_oe, bidir_cs, bidir_sl, bidir_ie, bidir_pu, bidir_pd;

    wire [NUM_ANALOG_PADS-1:0] analog;

    localparam int PIN_SCLK = 0, PIN_MOSI = 1, PIN_CS_N = 2, PIN_MISO = 3;
    localparam int PIN_BUSY = 4, PIN_DONE = 5, PIN_WB_DONE = 6;

    chip_core #(
        .NUM_INPUT_PADS  (NUM_INPUT_PADS),
        .NUM_BIDIR_PADS  (NUM_BIDIR_PADS),
        .NUM_ANALOG_PADS (NUM_ANALOG_PADS)
    ) dut (
        .clk       (clk),
        .rst_n     (rst_n),
        .input_in  (input_in),
        .input_pu  (input_pu),
        .input_pd  (input_pd),
        .bidir_in  (bidir_in),
        .bidir_out (bidir_out),
        .bidir_oe  (bidir_oe),
        .bidir_cs  (bidir_cs),
        .bidir_sl  (bidir_sl),
        .bidir_ie  (bidir_ie),
        .bidir_pu  (bidir_pu),
        .bidir_pd  (bidir_pd),
        .analog    (analog)
    );

    assign analog = {NUM_ANALOG_PADS{1'bz}};

    initial begin
        clk = 1'b0;
        forever #5 clk = ~clk;
    end

    // ---- serial host model ----
    // Several clk cycles per SCLK phase gives the 2-flop pad synchronizers
    // comfortable margin.
    localparam int SCLK_HALF_PERIOD_CLKS = 3;

    task automatic clk_wait(input integer n);
        integer i;
        begin
            for (i = 0; i < n; i = i + 1) @(posedge clk);
        end
    endtask

    task automatic sclk_pulse;
        begin
            bidir_in[PIN_SCLK] = 1'b0;
            clk_wait(SCLK_HALF_PERIOD_CLKS);
            bidir_in[PIN_SCLK] = 1'b1;
            clk_wait(SCLK_HALF_PERIOD_CLKS);
        end
    endtask

    // Shift out `nbits` of `val` (MSB first) on MOSI, one sclk_pulse per bit.
    task automatic shift_out_bits(input integer nbits, input logic [31:0] val);
        integer i;
        begin
            for (i = nbits - 1; i >= 0; i = i - 1) begin
                bidir_in[PIN_MOSI] = val[i];
                sclk_pulse();
            end
        end
    endtask

    // Read `nbits` from MISO (MSB first), one sclk_pulse per bit.
    task automatic shift_in_bits(input integer nbits, output logic [31:0] result);
        integer i;
        begin
            result = 32'd0;
            for (i = 0; i < nbits; i = i + 1) begin
                sclk_pulse();
                result = {result[30:0], bidir_out[PIN_MISO]};
            end
        end
    endtask

    task automatic do_write(input [1:0] cmd, input [9:0] addr, input [7:0] data);
        begin
            bidir_in[PIN_CS_N] = 1'b0;
            clk_wait(SCLK_HALF_PERIOD_CLKS);
            shift_out_bits(2, cmd);
            shift_out_bits(10, addr);
            shift_out_bits(8, data);
            clk_wait(SCLK_HALF_PERIOD_CLKS);
            bidir_in[PIN_CS_N] = 1'b1;
            clk_wait(SCLK_HALF_PERIOD_CLKS);
        end
    endtask

    task automatic do_start;
        begin
            bidir_in[PIN_CS_N] = 1'b0;
            clk_wait(SCLK_HALF_PERIOD_CLKS);
            shift_out_bits(2, 2'b10);
            shift_out_bits(10, 10'd0);
            clk_wait(SCLK_HALF_PERIOD_CLKS);
            bidir_in[PIN_CS_N] = 1'b1;
            clk_wait(SCLK_HALF_PERIOD_CLKS);
        end
    endtask

    task automatic do_read(input [3:0] addr, output logic signed [23:0] data);
        logic [31:0] raw;
        begin
            bidir_in[PIN_CS_N] = 1'b0;
            clk_wait(SCLK_HALF_PERIOD_CLKS);
            shift_out_bits(2, 2'b11);
            shift_out_bits(10, {6'd0, addr});
            // READ_C turnaround.  The C buffer now assembles a 24-bit word from
            // three byte planes of one 8-bit macro, so the bridge needs ~9 core
            // clocks after the last address edge before dout_shreg is loaded --
            // it used to be ~4.  Give it a full SCLK period of slack before the
            // first data edge, otherwise that edge lands while the bridge is
            // still walking planes and the whole word shifts out misaligned.
            clk_wait(2 * SCLK_HALF_PERIOD_CLKS);
            shift_in_bits(24, raw);
            clk_wait(SCLK_HALF_PERIOD_CLKS);
            bidir_in[PIN_CS_N] = 1'b1;
            clk_wait(SCLK_HALF_PERIOD_CLKS);
            data = raw[23:0];
        end
    endtask

    // ---- golden data (reuses the d3004n4 fixture) ----
    reg signed [7:0]  weights [0:(N*K)-1];
    reg signed [7:0]  bias [0:N-1];
    reg signed [7:0]  input_vec [0:K-1];
    reg signed [23:0] expected_val [0:N-1];

    integer row, k;
    integer mismatches;
    logic signed [23:0] result, bias_ext;

    initial begin
        rst_n    = 1'b0;
        input_in = '0;
        bidir_in = '0;
        bidir_in[PIN_CS_N] = 1'b1;

        $readmemh("tb/data/d3004n4_weights.memh", weights);
        $readmemh("tb/data/d3004n4_bias.memh", bias);
        $readmemh("tb/data/d3004n4_input.memh", input_vec);
        $readmemh("tb/data/d3004n4_expected.memh", expected_val);

        clk_wait(5);
        rst_n = 1'b1;
        clk_wait(5);

        // Write 4 weight rows into A (WRITE_A, addr = row*K+k).
        for (row = 0; row < N; row = row + 1) begin
            for (k = 0; k < K; k = k + 1) begin
                do_write(2'b00, row * K + k, weights[row * K + k]);
            end
        end

        // Write the shared input vector into B column 0 (addr = k*N, per
        // dla_b_buffer_bank's k-outer/N-stride addressing).
        for (k = 0; k < K; k = k + 1) begin
            do_write(2'b01, k * N, input_vec[k]);
        end

        // Trigger compute.
        do_start();
        wait (bidir_out[PIN_WB_DONE] == 1'b1);
        clk_wait(2);

        // Read back C[row][0] (flat addr = row*N) and apply each row's bias.
        mismatches = 0;
        for (row = 0; row < N; row = row + 1) begin
            do_read(row * N, result);
            bias_ext = {{16{bias[row][7]}}, bias[row]};
            result   = result + bias_ext;
            if (result !== expected_val[row]) begin
                mismatches = mismatches + 1;
                $display("Mismatch at row %0d: got %0d expected %0d", row, result, expected_val[row]);
            end else begin
                $display("row %0d: got %0d matches expected (via serial bridge)", row, result);
            end
        end

        if (mismatches != 0) begin
            $display("FAIL: %0d row mismatches", mismatches);
            $fatal(1);
        end else begin
            $display("PASS: all %0d rows match expected via serial bridge", N);
        end

        $finish;
    end
endmodule
