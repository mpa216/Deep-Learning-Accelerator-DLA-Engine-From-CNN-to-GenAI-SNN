`timescale 1ns / 1ps

// ============================================================================
// dla_engine_chip_gan_tb -- FULL MNIST-GAN image, generated end-to-end THROUGH
// THE SERIAL BRIDGE on the taped-out chip.
//
// This is the deferred "combined" demo: it drives the padframe-facing terminals
// of `dla_engine_chip` exactly as an external 3.3 V host would (SCLK/MOSI/CS_N
// in, MISO/busy/done/wb_done out) and runs the *entire* 64->256->256->784
// generator (all tiling, bias, requant, ReLU and the Q20 tanh LUT) with the
// accelerator reachable ONLY over the 4-wire link.
//
// Split of work (identical to g300_pipeline_top, just relocated):
//   * the CHIP does the INT8 matrix-multiply -- for each `START` it produces the
//     four raw 24-bit accumulators C[row][0] = sum_k A[row][k]*B[k][0];
//   * the HOST (this testbench) owns the schedule (WRITE_B once per layer,
//     WRITE_A per 4-neuron tile, START, READ_C x4) and the per-neuron
//     bias-add + requantize + activation, exactly reproducing g300_pipeline_top
//     S_LOADB / S_LOADA / S_REQ.
//
// Validation: the 784 host-side pixels are compared bit-exactly to the same
// Python golden g300_pipeline_tb uses (tb/data/g300_int8/g300_int8_expected.memh).
// A PASS proves the taped-out pads -> serial bridge -> 8 SRAM macros + PE array
// + flip-flop C -> host chain reproduces the whole image.
//
// Run RTL (fast, de-risk):    rtl/dla_engine_chip.sv + rtl/*.v/.sv (no -DSYNTHESIS)
// Run GLS (the real ask):     verilog/dla_engine_chip.nl.v + behavioral SRAM + AS cells
//                             (no -DSYNTHESIS, do NOT add rtl/*.v -- name collision)
// Both need `-I rtl` for the g300_quant_params.vh include below.
// ============================================================================
module dla_engine_chip_gan_tb;
    // requant constants (G300_MA0/MB0/..., shifts) -- generated per latent by
    // scripts/gen_g300_int8_assets.py, same include g300_pipeline_top uses.
    `include "g300_quant_params.vh"

    localparam int N = 4;
    localparam int K = 256;

    localparam int L0_OUT = 256, L0_IN = 64;
    localparam int L2_OUT = 256, L2_IN = 256;
    localparam int L4_OUT = 784, L4_IN = 256;
    localparam int OUT_DIM = L4_OUT;

    localparam int FP_SHIFT   = 20;
    localparam int LUT_SHIFT  = 8;
    localparam longint TANH_MAX_FP = (64'sd4 <<< FP_SHIFT);          // 4 in Q20
    localparam int LUT_SIZE = ((TANH_MAX_FP * 2) >>> LUT_SHIFT) + 1; // 32769

    // --- clock / reset ---
    reg clk;
    reg rst_n;

    // --- host-driven inputs ---
    reg SCLK_IN, MOSI_IN, CS_N_IN;
    // --- output-pad feedback inputs (unused by host; tie low) ---
    reg MISO_IN, busy_IN, done_IN, wb_done_IN;

    // --- all chip outputs (signal + pad-control terminals); only *_OUT are read ---
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
        forever #5 clk = ~clk;   // 100 MHz sim clock
    end

    // ---- serial host model (identical protocol to dla_engine_chip_tb) ----
    localparam int SCLK_HALF_PERIOD_CLKS = 3;   // SCLK <= clk/6, each level held 3 clk

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

    // READ_C: the bridge presents the MSB on MISO once the word is loaded and
    // advances one bit per rising SCLK edge -> SAMPLE BEFORE each edge.
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

    // ---- GAN parameters / activations / golden ----
    reg signed [7:0]  w0 [0:(L0_OUT*L0_IN)-1];
    reg signed [7:0]  w2 [0:(L2_OUT*L2_IN)-1];
    reg signed [7:0]  w4 [0:(L4_OUT*L4_IN)-1];
    reg signed [7:0]  b0 [0:L0_OUT-1];
    reg signed [7:0]  b2 [0:L2_OUT-1];
    reg signed [7:0]  b4 [0:L4_OUT-1];
    reg signed [7:0]  zq [0:L0_IN-1];
    reg signed [23:0] tanh_lut [0:LUT_SIZE-1];

    reg signed [7:0]  h0q [0:L0_OUT-1];   // int8 activations after L0 (ReLU)
    reg signed [7:0]  h2q [0:L2_OUT-1];   // int8 activations after L2 (ReLU)
    reg signed [7:0]  pix_mem [0:L4_OUT-1];
    reg signed [7:0]  expected [0:OUT_DIM-1];

    // source-select helpers (mirror g300_pipeline_top S_LOADB / S_LOADA)
    function automatic signed [7:0] get_input(input int lyr, input int k);
        case (lyr)
            0:       get_input = zq[k];
            1:       get_input = h0q[k];
            default: get_input = h2q[k];
        endcase
    endfunction

    function automatic signed [7:0] get_weight(input int lyr, input int grow, input int k);
        case (lyr)
            0:       get_weight = w0[grow*L0_IN + k];
            1:       get_weight = w2[grow*L2_IN + k];
            default: get_weight = w4[grow*L4_IN + k];
        endcase
    endfunction

    // ---- one full layer, driven entirely over the serial link ----
    integer lyr, in_dim, num_tiles, tile, row, k, r, grow;
    logic signed [23:0] accv [0:N-1];
    logic signed [23:0] rd_tmp;
    reg signed [63:0] t_acc, pre_q20, tmp_pix, pix_val;
    reg [15:0]        lut_idx;
    reg signed [23:0] tanh_val;
    reg signed [7:0]  inb, wsel;

    task automatic run_layer(input int lyr_i);
        begin
            case (lyr_i)
                0: begin in_dim = L0_IN; num_tiles = L0_OUT/N; end
                1: begin in_dim = L2_IN; num_tiles = L2_OUT/N; end
                default: begin in_dim = L4_IN; num_tiles = L4_OUT/N; end
            endcase

            // ---- WRITE_B: shared input activation into B column 0 (addr=k*N),
            //      full K depth, zero-padded past in_dim (matches S_LOADB) ----
            for (k = 0; k < K; k = k + 1) begin
                inb = (k < in_dim) ? get_input(lyr_i, k) : 8'sd0;
                do_write(2'b01, k*N, inb);
            end

            for (tile = 0; tile < num_tiles; tile = tile + 1) begin
                // ---- WRITE_A: 4 weight rows of this tile (addr=row*K+k),
                //      full K, zero-padded (matches S_LOADA) ----
                for (row = 0; row < N; row = row + 1) begin
                    grow = tile*N + row;
                    for (k = 0; k < K; k = k + 1) begin
                        wsel = (k < in_dim) ? get_weight(lyr_i, grow, k) : 8'sd0;
                        do_write(2'b00, row*K + k, wsel);
                    end
                end

                // ---- START, wait for writeback, READ_C x4 ----
                do_start();
                wait (wb_done_OUT == 1'b1);
                clk_wait(2);
                for (row = 0; row < N; row = row + 1) begin
                    do_read(row*N, rd_tmp);      // flat C addr = row*N (col 0)
                    accv[row] = rd_tmp;
                end

                // ---- host-side bias + requant + activation (mirror S_REQ) ----
                for (r = 0; r < N; r = r + 1) begin
                    grow = tile*N + r;
                    if (lyr_i == 0) begin
                        t_acc = accv[r] * G300_MA0 + b0[grow] * G300_MB0;
                        if (t_acc < 0) t_acc = 64'sd0;
                        t_acc = (t_acc + (64'sd1 <<< (G300_REQ_SHIFT-1))) >>> G300_REQ_SHIFT;
                        if (t_acc > 64'sd127) t_acc = 64'sd127;
                        h0q[grow] = t_acc[7:0];
                    end else if (lyr_i == 1) begin
                        t_acc = accv[r] * G300_MA2 + b2[grow] * G300_MB2;
                        if (t_acc < 0) t_acc = 64'sd0;
                        t_acc = (t_acc + (64'sd1 <<< (G300_REQ_SHIFT-1))) >>> G300_REQ_SHIFT;
                        if (t_acc > 64'sd127) t_acc = 64'sd127;
                        h2q[grow] = t_acc[7:0];
                    end else begin
                        pre_q20 = accv[r] * G300_MW4 + b4[grow] * G300_MB4;
                        pre_q20 = (pre_q20 + (64'sd1 <<< (G300_REQ_SHIFT_L4-1)))
                                      >>> G300_REQ_SHIFT_L4;
                        if (pre_q20 > TANH_MAX_FP)       pre_q20 = TANH_MAX_FP;
                        else if (pre_q20 < -TANH_MAX_FP) pre_q20 = -TANH_MAX_FP;
                        lut_idx  = (pre_q20 + TANH_MAX_FP) >>> LUT_SHIFT;
                        tanh_val = tanh_lut[lut_idx];
                        tmp_pix  = (tanh_val + (64'sd1 <<< FP_SHIFT)) * 64'sd255;
                        pix_val  = (tmp_pix + (64'sd1 <<< FP_SHIFT)) >>> (FP_SHIFT + 1);
                        if (pix_val < 0)        pix_val = 64'sd0;
                        else if (pix_val > 255) pix_val = 64'sd255;
                        pix_mem[grow] = pix_val[7:0] - 8'sd128;
                    end
                end

                if ((tile % 16) == 0)
                    $display("  [layer %0d] tile %0d / %0d  (t=%0t)", lyr_i, tile, num_tiles, $time);
            end
        end
    endtask

    integer fh, mismatches, first_bad;
    string actual_memh;

    initial begin
        rst_n      = 1'b0;
        SCLK_IN    = 1'b0;
        MOSI_IN    = 1'b0;
        CS_N_IN    = 1'b1;
        MISO_IN    = 1'b0;
        busy_IN    = 1'b0;
        done_IN    = 1'b0;
        wb_done_IN = 1'b0;

        if (!$value$plusargs("ACTUAL_MEMH=%s", actual_memh))
            actual_memh = "tb/data/g300_int8/g300_int8_serial_gls.memh";

        $readmemh("weights_vh/mnist_gan_mlp/G300_0_weight.memh", w0);
        $readmemh("weights_vh/mnist_gan_mlp/G300_0_bias.memh",   b0);
        $readmemh("weights_vh/mnist_gan_mlp/G300_2_weight.memh", w2);
        $readmemh("weights_vh/mnist_gan_mlp/G300_2_bias.memh",   b2);
        $readmemh("weights_vh/mnist_gan_mlp/G300_4_weight.memh", w4);
        $readmemh("weights_vh/mnist_gan_mlp/G300_4_bias.memh",   b4);
        $readmemh("tb/data/g300_int8/g300_zq.memh",              zq);
        $readmemh("tb/data/g300_fp/g300_tanh_lut_fp.memh",       tanh_lut);
        $readmemh("tb/data/g300_int8/g300_int8_expected.memh",   expected);

        clk_wait(5);
        rst_n = 1'b1;
        clk_wait(5);

        $display("=== Full MNIST-GAN through the serial bridge on dla_engine_chip ===");
        run_layer(0);   // 64  -> 256, ReLU  -> h0q
        $display("layer 0 done (t=%0t)", $time);
        run_layer(1);   // 256 -> 256, ReLU  -> h2q
        $display("layer 1 done (t=%0t)", $time);
        run_layer(2);   // 256 -> 784, tanh  -> pix_mem
        $display("layer 2 done (t=%0t)", $time);

        // ---- validate against the Python golden ----
        fh = $fopen(actual_memh, "w");
        mismatches = 0;
        first_bad  = -1;
        for (k = 0; k < OUT_DIM; k = k + 1) begin
            if (fh) $fdisplay(fh, "%02h", pix_mem[k][7:0]);
            if (pix_mem[k] !== expected[k]) begin
                if (mismatches == 0) first_bad = k;
                mismatches = mismatches + 1;
            end
        end
        if (fh) $fclose(fh);

        if (mismatches != 0) begin
            $display("FAIL: %0d / %0d pixels mismatch (first at %0d: got %0d expected %0d)",
                     mismatches, OUT_DIM, first_bad, pix_mem[first_bad], expected[first_bad]);
            $fatal(1);
        end else begin
            $display("PASS: all %0d pixels match expected -- full GAN image generated through the serial bridge on dla_engine_chip", OUT_DIM);
        end
        $finish;
    end
endmodule
