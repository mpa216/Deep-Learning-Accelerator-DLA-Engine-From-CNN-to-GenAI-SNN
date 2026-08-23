`timescale 1ns / 1ps

// End-to-end testbench for the ACV chip-level top (dla_engine_chip).  Drives
// the padframe-facing terminals exactly as the organiser's I/O cells + host
// would (SCLK/MOSI/CS_N in via *_IN, MISO/busy/done/wb_done out via *_OUT) and
// verifies the whole integrated chain -- serial bridge -> dla_engine_top (A/B
// SRAM macros + PE array + flip-flop C buffer) -- reproduces the d3004n4
// golden vectors bit-exactly.  This is the RTL sign-off of the final top that
// includes SRAM + Core + Bridge together.
module dla_engine_chip_tb;
    localparam int N = 4;
    localparam int K = 256;

    reg clk;
    reg rst_n;

    // host-driven inputs
    reg SCLK_IN, MOSI_IN, CS_N_IN;
    // output-pad feedback inputs (unused by the host; tie low)
    reg MISO_IN, busy_IN, done_IN, wb_done_IN;

    // all chip outputs (signal + pad-control terminals) -- only *_OUT are read
    wire clk_PU, clk_PD, rst_n_PU, rst_n_PD;
    wire SCLK_OUT, SCLK_OE, SCLK_IE, SCLK_CS, SCLK_SL, SCLK_PU, SCLK_PD;
    wire MOSI_OUT, MOSI_OE, MOSI_IE, MOSI_CS, MOSI_SL, MOSI_PU, MOSI_PD;
    wire CS_N_OUT, CS_N_OE, CS_N_IE, CS_N_CS, CS_N_SL, CS_N_PU, CS_N_PD;
    wire MISO_OUT, MISO_OE, MISO_IE, MISO_CS, MISO_SL, MISO_PU, MISO_PD;
    wire busy_OUT, busy_OE, busy_IE, busy_CS, busy_SL, busy_PU, busy_PD;
    wire done_OUT, done_OE, done_IE, done_CS, done_SL, done_PU, done_PD;
    wire wb_done_OUT, wb_done_OE, wb_done_IE, wb_done_CS, wb_done_SL, wb_done_PU, wb_done_PD;

    dla_engine_chip dut (
        .clk(clk), .clk_PU(clk_PU), .clk_PD(clk_PD),
        .rst_n(rst_n), .rst_n_PU(rst_n_PU), .rst_n_PD(rst_n_PD),
        .SCLK_IN(SCLK_IN), .SCLK_OUT(SCLK_OUT), .SCLK_OE(SCLK_OE), .SCLK_IE(SCLK_IE),
        .SCLK_CS(SCLK_CS), .SCLK_SL(SCLK_SL), .SCLK_PU(SCLK_PU), .SCLK_PD(SCLK_PD),
        .MOSI_IN(MOSI_IN), .MOSI_OUT(MOSI_OUT), .MOSI_OE(MOSI_OE), .MOSI_IE(MOSI_IE),
        .MOSI_CS(MOSI_CS), .MOSI_SL(MOSI_SL), .MOSI_PU(MOSI_PU), .MOSI_PD(MOSI_PD),
        .CS_N_IN(CS_N_IN), .CS_N_OUT(CS_N_OUT), .CS_N_OE(CS_N_OE), .CS_N_IE(CS_N_IE),
        .CS_N_CS(CS_N_CS), .CS_N_SL(CS_N_SL), .CS_N_PU(CS_N_PU), .CS_N_PD(CS_N_PD),
        .MISO_IN(MISO_IN), .MISO_OUT(MISO_OUT), .MISO_OE(MISO_OE), .MISO_IE(MISO_IE),
        .MISO_CS(MISO_CS), .MISO_SL(MISO_SL), .MISO_PU(MISO_PU), .MISO_PD(MISO_PD),
        .busy_IN(busy_IN), .busy_OUT(busy_OUT), .busy_OE(busy_OE), .busy_IE(busy_IE),
        .busy_CS(busy_CS), .busy_SL(busy_SL), .busy_PU(busy_PU), .busy_PD(busy_PD),
        .done_IN(done_IN), .done_OUT(done_OUT), .done_OE(done_OE), .done_IE(done_IE),
        .done_CS(done_CS), .done_SL(done_SL), .done_PU(done_PU), .done_PD(done_PD),
        .wb_done_IN(wb_done_IN), .wb_done_OUT(wb_done_OUT), .wb_done_OE(wb_done_OE), .wb_done_IE(wb_done_IE),
        .wb_done_CS(wb_done_CS), .wb_done_SL(wb_done_SL), .wb_done_PU(wb_done_PU), .wb_done_PD(wb_done_PD)
    );

    initial begin
        clk = 1'b0;
        forever #5 clk = ~clk;
    end

    // ---- serial host model (identical protocol to chip_core_dla_tb) ----
    localparam int SCLK_HALF_PERIOD_CLKS = 3;

    task automatic clk_wait(input integer n);
        integer i;
        begin
            for (i = 0; i < n; i = i + 1) @(posedge clk);
        end
    endtask

    task automatic sclk_pulse;
        begin
            SCLK_IN = 1'b0;
            clk_wait(SCLK_HALF_PERIOD_CLKS);
            SCLK_IN = 1'b1;
            clk_wait(SCLK_HALF_PERIOD_CLKS);
        end
    endtask

    task automatic shift_out_bits(input integer nbits, input logic [31:0] val);
        integer i;
        begin
            for (i = nbits - 1; i >= 0; i = i - 1) begin
                MOSI_IN = val[i];
                sclk_pulse();
            end
        end
    endtask

    // READ_C: the bridge presents the MSB on MISO as soon as the word is loaded
    // (dout_shreg[23]) and advances one bit per rising SCLK edge, so the host
    // must SAMPLE BEFORE each edge (documented post-silicon protocol) -- sample,
    // then pulse to advance.
    task automatic shift_in_bits(input integer nbits, output logic [31:0] result);
        integer i;
        begin
            result = 32'd0;
            for (i = 0; i < nbits; i = i + 1) begin
                result = {result[30:0], MISO_OUT};
                sclk_pulse();
            end
        end
    endtask

    task automatic do_write(input [1:0] cmd, input [9:0] addr, input [7:0] data);
        begin
            CS_N_IN = 1'b0;
            clk_wait(SCLK_HALF_PERIOD_CLKS);
            shift_out_bits(2, cmd);
            shift_out_bits(10, addr);
            shift_out_bits(8, data);
            clk_wait(SCLK_HALF_PERIOD_CLKS);
            CS_N_IN = 1'b1;
            clk_wait(SCLK_HALF_PERIOD_CLKS);
        end
    endtask

    task automatic do_start;
        begin
            CS_N_IN = 1'b0;
            clk_wait(SCLK_HALF_PERIOD_CLKS);
            shift_out_bits(2, 2'b10);
            shift_out_bits(10, 10'd0);
            clk_wait(SCLK_HALF_PERIOD_CLKS);
            CS_N_IN = 1'b1;
            clk_wait(SCLK_HALF_PERIOD_CLKS);
        end
    endtask

    task automatic do_read(input [3:0] addr, output logic signed [23:0] data);
        logic [31:0] raw;
        begin
            CS_N_IN = 1'b0;
            clk_wait(SCLK_HALF_PERIOD_CLKS);
            shift_out_bits(2, 2'b11);
            shift_out_bits(10, {6'd0, addr});
            clk_wait(2 * SCLK_HALF_PERIOD_CLKS);   // READ_C turnaround
            shift_in_bits(24, raw);
            clk_wait(SCLK_HALF_PERIOD_CLKS);
            CS_N_IN = 1'b1;
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
        rst_n      = 1'b0;
        SCLK_IN    = 1'b0;
        MOSI_IN    = 1'b0;
        CS_N_IN    = 1'b1;
        MISO_IN    = 1'b0;
        busy_IN    = 1'b0;
        done_IN    = 1'b0;
        wb_done_IN = 1'b0;

        $readmemh("tb/data/d3004n4_weights.memh", weights);
        $readmemh("tb/data/d3004n4_bias.memh", bias);
        $readmemh("tb/data/d3004n4_input.memh", input_vec);
        $readmemh("tb/data/d3004n4_expected.memh", expected_val);

        clk_wait(5);
        rst_n = 1'b1;
        clk_wait(5);

        // Write 4 weight rows into A (WRITE_A, addr = row*K+k).
        for (row = 0; row < N; row = row + 1)
            for (k = 0; k < K; k = k + 1)
                do_write(2'b00, row * K + k, weights[row * K + k]);

        // Write the shared input vector into B column 0 (addr = k*N).
        for (k = 0; k < K; k = k + 1)
            do_write(2'b01, k * N, input_vec[k]);

        // Trigger compute and wait for writeback done.
        do_start();
        wait (wb_done_OUT == 1'b1);
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
                $display("row %0d: got %0d matches expected (ACV chip top)", row, result);
            end
        end

        if (mismatches != 0) begin
            $display("FAIL: %0d row mismatches", mismatches);
            $fatal(1);
        end else begin
            $display("PASS: all %0d rows match expected via dla_engine_chip (SRAM+Core+Bridge)", N);
        end

        $finish;
    end
endmodule
