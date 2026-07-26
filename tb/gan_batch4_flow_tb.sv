`timescale 1ns / 1ps

// End-to-end batch-4 flow: four MNIST digits generated and scored in one pass.
//
// This is the "batch 4, host holds images" strategy running for real.  One streamed
// weight tile feeds four independent latents, so the weight traffic that dominates run
// time is amortised 4x.  Four digits are 3,136 bytes and do not fit on chip, so the
// host drains the image buffer as a 1 KiB rolling window during the generator's output
// layer and feeds the pixels back into B for the discriminator.
//
//   generator   4 latents -> 4 x 784 pixels     (drained to the host in 4 windows)
//   D(fake)     4 digits  -> 4 scores
//   D(real)     the real digit replicated across all four lanes -- every lane must
//               return the SAME score, which is a free cross-lane consistency check
//   losses      OP_LATCH_LOSS once per lane
//
// Checked against scripts/gan_golden.py (regenerate with --batch4 first).
// tb/gan_engine_top_tb.sv is the batch-1 sibling; tb/gan_batch4_tb.sv is the focused
// datapath test.
module gan_batch4_flow_tb;

`include "gan_defs.vh"

    localparam integer BATCH   = 4;
    localparam integer IMG_LEN = 784;

    reg clk = 1'b0;
    reg rst_n = 1'b0;
    always #5 clk = ~clk;

    reg               wr_en = 1'b0;
    reg  [1:0]        wr_sel = 2'd0;
    reg  [9:0]        wr_addr = 10'd0;
    reg signed [7:0]  wr_data = 8'sd0;
    reg               cfg_we = 1'b0;
    reg  [3:0]        cfg_addr = 4'd0;
    reg signed [23:0] cfg_data = 24'sd0;
    reg               exec_req = 1'b0;
    reg  [3:0]        exec_op = 4'd0;
    reg  [7:0]        exec_arg = 8'd0;
    reg               rd_en = 1'b0;
    reg  [1:0]        rd_sel = 2'd0;
    reg  [9:0]        rd_addr = 10'd0;
    wire signed [23:0] rd_data;
    wire              busy, verdict, dla_busy, dla_done;

    gan_engine_top dut (
        .clk(clk), .rst_n(rst_n),
        .wr_en(wr_en), .wr_sel(wr_sel), .wr_addr(wr_addr), .wr_data(wr_data),
        .cfg_we(cfg_we), .cfg_addr(cfg_addr), .cfg_data(cfg_data),
        .exec_req(exec_req), .exec_op(exec_op), .exec_arg(exec_arg),
        .rd_en(rd_en), .rd_sel(rd_sel), .rd_addr(rd_addr), .rd_data(rd_data),
        .busy(busy), .verdict(verdict), .dla_busy(dla_busy), .dla_done(dla_done)
    );

    // ---- host-side stores -----------------------------------------------------
    reg signed [7:0] w_g0 [0:(256*64)-1];
    reg signed [7:0] w_g2 [0:(256*256)-1];
    reg signed [7:0] w_g4 [0:(784*256)-1];
    reg signed [7:0] w_d0 [0:(256*784)-1];
    reg signed [7:0] w_d2 [0:(256*256)-1];
    reg signed [7:0] w_d4 [0:(1*256)-1];
    reg signed [7:0] b_g0 [0:255];
    reg signed [7:0] b_g2 [0:255];
    reg signed [7:0] b_g4 [0:783];
    reg signed [7:0] b_d0 [0:255];
    reg signed [7:0] b_d2 [0:255];
    reg signed [7:0] b_d4 [0:0];

    reg signed [23:0] cfgmem  [0:(6*16)-1];
    reg signed [7:0]  zq      [0:(4*64)-1];        // 4 latents, lane-major
    reg signed [7:0]  real_img[0:783];
    reg signed [7:0]  img_exp [0:(4*784)-1];       // 4 golden digits, lane-major
    reg signed [23:0] met_exp [0:31];

    // The host's copy of the four generated digits -- this is the whole point of
    // "host holds images": they never all exist on chip at once.
    reg signed [7:0]  himg [0:3][0:783];

    integer errors = 0;
    integer i, j, k, t, kt, n, f;
    reg signed [23:0] rv;

    initial begin
        $readmemh("weights_vh/mnist_gan_mlp/G300_0_weight.memh", w_g0);
        $readmemh("weights_vh/mnist_gan_mlp/G300_2_weight.memh", w_g2);
        $readmemh("weights_vh/mnist_gan_mlp/G300_4_weight.memh", w_g4);
        $readmemh("weights_vh/mnist_gan_mlp/D300_0_weight.memh", w_d0);
        $readmemh("weights_vh/mnist_gan_mlp/D300_2_weight.memh", w_d2);
        $readmemh("weights_vh/mnist_gan_mlp/D300_4_weight.memh", w_d4);
        $readmemh("weights_vh/mnist_gan_mlp/G300_0_bias.memh", b_g0);
        $readmemh("weights_vh/mnist_gan_mlp/G300_2_bias.memh", b_g2);
        $readmemh("weights_vh/mnist_gan_mlp/G300_4_bias.memh", b_g4);
        $readmemh("weights_vh/mnist_gan_mlp/D300_0_bias.memh", b_d0);
        $readmemh("weights_vh/mnist_gan_mlp/D300_2_bias.memh", b_d2);
        $readmemh("weights_vh/mnist_gan_mlp/D300_4_bias.memh", b_d4);
        $readmemh("tb/data/gan_chip/gan_cfg_b4.memh", cfgmem);
        $readmemh("tb/data/gan_chip/gan_zq_b4.memh", zq);
        $readmemh("tb/data/gan_chip/gan_real_img.memh", real_img);
        $readmemh("tb/data/gan_chip/gan_img_expected_b4.memh", img_exp);
        $readmemh("tb/data/gan_chip/gan_met_expected_b4.memh", met_exp);
    end

    function signed [7:0] wget(input integer lyr, input integer orow, input integer kk);
        begin
            case (lyr)
                0: wget = w_g0[orow * 64  + kk];
                1: wget = w_g2[orow * 256 + kk];
                2: wget = w_g4[orow * 256 + kk];
                3: wget = w_d0[orow * 784 + kk];
                4: wget = w_d2[orow * 256 + kk];
                default: wget = w_d4[orow * 256 + kk];
            endcase
        end
    endfunction

    function signed [7:0] bget(input integer lyr, input integer idx);
        begin
            case (lyr)
                0: bget = b_g0[idx];  1: bget = b_g2[idx];  2: bget = b_g4[idx];
                3: bget = b_d0[idx];  4: bget = b_d2[idx];
                default: bget = b_d4[idx];
            endcase
        end
    endfunction

    // ---- host primitives ------------------------------------------------------
    task cfg_write(input [3:0] addr, input signed [23:0] data);
        begin
            @(posedge clk);
            cfg_we <= 1'b1; cfg_addr <= addr; cfg_data <= data;
            @(posedge clk);
            cfg_we <= 1'b0;
        end
    endtask

    task exec(input [3:0] op, input [7:0] arg);
        begin
            @(posedge clk);
            exec_req <= 1'b1; exec_op <= op; exec_arg <= arg;
            @(posedge clk);
            exec_req <= 1'b0;
            @(posedge clk);
            while (busy) @(posedge clk);
        end
    endtask

    task host_read(input [1:0] sel, input [9:0] addr, output signed [23:0] data);
        begin
            @(posedge clk);
            rd_en <= 1'b1; rd_sel <= sel; rd_addr <= addr;
            @(posedge clk);
            @(posedge clk);
            data = rd_data;
            rd_en <= 1'b0;
        end
    endtask

    task load_cfg_block(input integer lyr);
        integer q;
        begin
            for (q = 0; q < 16; q = q + 1) cfg_write(q[3:0], cfgmem[lyr * 16 + q]);
        end
    endtask

    // Bulk writes hold wr_en high so the engine takes one value per clock -- at batch 4
    // the host moves ~1.4 M bytes per run and a two-cycle-per-write helper would double
    // the simulation time for no reason.
    task load_a_tile(input integer lyr, input integer tile, input integer in_dim,
                     input integer ktile, input integer pad_all);
        integer r, kk, kabs, nwr;
        begin
            nwr = pad_all ? 256 : ((in_dim - ktile * 256) > 256 ? 256
                                                                : (in_dim - ktile * 256));
            @(posedge clk);
            wr_en <= 1'b1; wr_sel <= WSEL_A;
            for (r = 0; r < 4; r = r + 1)
                for (kk = 0; kk < nwr; kk = kk + 1) begin
                    kabs = ktile * 256 + kk;
                    wr_addr <= r * 256 + kk;
                    wr_data <= (kabs < in_dim) ? wget(lyr, tile * 4 + r, kabs) : 8'sd0;
                    @(posedge clk);
                end
            wr_en <= 1'b0;
        end
    endtask

    // B[k][lane] = himg[lane][ktile*256 + k], zero-padded past the 784th pixel.
    task load_b_from_host_img(input integer ktile);
        integer kk, jj, idx;
        begin
            @(posedge clk);
            wr_en <= 1'b1; wr_sel <= WSEL_B;
            for (kk = 0; kk < 256; kk = kk + 1)
                for (jj = 0; jj < BATCH; jj = jj + 1) begin
                    idx = ktile * 256 + kk;
                    wr_addr <= kk * 4 + jj;
                    wr_data <= (idx < IMG_LEN) ? himg[jj][idx] : 8'sd0;
                    @(posedge clk);
                end
            wr_en <= 1'b0;
        end
    endtask

    task set_tile_bias(input integer lyr, input integer tile, input integer out_dim);
        integer r;
        reg signed [7:0] btmp;
        begin
            for (r = 0; r < 4; r = r + 1) begin
                btmp = (tile * 4 + r < out_dim) ? bget(lyr, tile * 4 + r) : 8'sd0;
                cfg_write(CFG_B0 + r[3:0], {{16{btmp[7]}}, btmp});
            end
        end
    endtask

    // Drain one 1 KiB window of the image buffer into the host's four digits.
    // `base` is the pixel index the window starts at; `count` how many per lane.
    task drain_window(input integer base, input integer count);
        integer jj, o;
        begin
            for (jj = 0; jj < BATCH; jj = jj + 1)
                for (o = 0; o < count; o = o + 1) begin
                    host_read(RSEL_IMG, jj * 256 + o, rv);
                    himg[jj][base + o] = rv[7:0];
                end
        end
    endtask

    // ---- a whole layer, batch 4 ----------------------------------------------
    // src: 0 = B already holds the input, 1 = copy from the activation buffer,
    //      2 = the host feeds B from its own image copies (K-tiled).
    task run_layer(input integer lyr, input integer out_dim, input integer in_dim,
                   input integer src, input [1:0] dsel, input integer nout);
        integer n_kt, ntile, drained, win;
        begin
            load_cfg_block(lyr);
            cfg_write(CFG_DST_SEL, {22'd0, dsel});
            cfg_write(CFG_NOUT,    nout);
            cfg_write(CFG_BATCH,   BATCH);
            cfg_write(CFG_DST_PTR, 24'sd0);

            n_kt    = (in_dim + 255) / 256;
            ntile   = (out_dim + nout - 1) / nout;
            drained = 0;
            win     = 0;

            if (src == 1) exec(OP_LOADB_ACT, 8'd0);

            for (t = 0; t < ntile; t = t + 1) begin
                exec(OP_CLR_ACC, 8'd0);
                for (kt = 0; kt < n_kt; kt = kt + 1) begin
                    if (src == 2) load_b_from_host_img(kt);
                    load_a_tile(lyr, t, in_dim, kt, (t == 0) ? 1 : 0);
                    exec(OP_TILE, 8'd0);
                end
                set_tile_bias(lyr, t, out_dim);
                exec(OP_FLUSH, 8'd0);

                // The image buffer is only 256 bytes per lane, so it must be emptied
                // before the write pointer wraps: every 64 flushes, and once at the end.
                if (dsel == DST_IMG) begin
                    drained = drained + 1;
                    if (drained == 64 || t == ntile - 1) begin
                        drain_window(win * 256, drained * 4);
                        win = win + 1;
                        drained = 0;
                    end
                end
            end
        end
    endtask

    task run_discriminator(input [1:0] score_sel);
        begin
            run_layer(3, 256, 784, 2, DST_ACT,   4);
            run_layer(4, 256, 256, 1, DST_ACT,   4);
            run_layer(5, 1,   256, 1, score_sel, 1);
        end
    endtask

    task check24(input [8*24:1] name, input signed [23:0] got, input signed [23:0] exp);
        begin
            if (got !== exp) begin
                $display("  MISMATCH %0s: got %0d, expected %0d", name, got, exp);
                errors = errors + 1;
            end else begin
                $display("  ok       %0s = %0d", name, got);
            end
        end
    endtask

    integer ndiff, maxdiff, d, totdiff;

    initial begin
        $display("=== gan_engine_top batch-4 END-TO-END flow ===");
        $display("    four latents share one weight stream; the host holds the digits");
        repeat (8) @(posedge clk);
        rst_n <= 1'b1;
        repeat (4) @(posedge clk);

        exec(OP_CLR_MET, 8'd0);
        exec(OP_ZERO_ACT, 8'd0);
        exec(OP_ZERO_IMG, 8'd0);
        cfg_write(CFG_BATCH, BATCH);

        // ---- four latents into B's four columns ------------------------------
        $display("[%0t] loading 4 latents into B columns 0..3", $time);
        @(posedge clk);
        wr_en <= 1'b1; wr_sel <= WSEL_B;
        for (k = 0; k < 256; k = k + 1)
            for (j = 0; j < BATCH; j = j + 1) begin
                wr_addr <= k * 4 + j;
                wr_data <= (k < 64) ? zq[j * 64 + k] : 8'sd0;
                @(posedge clk);
            end
        wr_en <= 1'b0;

        $display("[%0t] generator layer 0 (64->256, ReLU) x4 lanes", $time);
        run_layer(0, 256, 64,  0, DST_ACT, 4);
        $display("[%0t] generator layer 1 (256->256, ReLU) x4 lanes", $time);
        run_layer(1, 256, 256, 1, DST_ACT, 4);
        $display("[%0t] generator layer 2 (256->784, PWL tanh) x4 lanes + host drain",
                 $time);
        run_layer(2, 784, 256, 1, DST_IMG, 4);

        // ---- the four digits, as the host reassembled them -------------------
        ndiff = 0; maxdiff = 0; totdiff = 0;
        for (j = 0; j < BATCH; j = j + 1)
            for (i = 0; i < IMG_LEN; i = i + 1) begin
                if (himg[j][i] !== img_exp[j * 784 + i]) begin
                    ndiff = ndiff + 1;
                    d = (himg[j][i] > img_exp[j*784+i]) ? (himg[j][i] - img_exp[j*784+i])
                                                        : (img_exp[j*784+i] - himg[j][i]);
                    totdiff = totdiff + d;
                    if (maxdiff < d) maxdiff = d;
                    if (ndiff <= 6)
                        $display("  lane %0d pixel %0d: got %0d, expected %0d",
                                 j, i, himg[j][i], img_exp[j*784+i]);
                end
            end
        if (ndiff == 0)
            $display("  IMAGES OK: 4 x 784 = 3136/3136 pixels bit-exact vs golden");
        else begin
            $display("  IMAGE MISMATCH: %0d/3136 pixels differ (max |d| = %0d)",
                     ndiff, maxdiff);
            errors = errors + 1;
        end

        f = $fopen("tb/data/gan_chip/gan_img_rtl_b4.memh", "w");
        for (j = 0; j < BATCH; j = j + 1)
            for (i = 0; i < IMG_LEN; i = i + 1) $fwrite(f, "%02x\n", himg[j][i]);
        $fclose(f);

        for (j = 0; j < BATCH; j = j + 1) begin
            $display("");
            $display("  lane %0d:", j);
            for (i = 0; i < 28; i = i + 2) begin
                $write("    ");
                for (k = 0; k < 28; k = k + 1) begin
                    d = (himg[j][i*28+k] + 128) * 10 / 256;
                    case (d)
                        0: $write(" "); 1: $write("."); 2: $write(":"); 3: $write("-");
                        4: $write("="); 5: $write("+"); 6: $write("*"); 7: $write("#");
                        8: $write("%%"); default: $write("@");
                    endcase
                end
                $write("\n");
            end
        end
        $display("");

        // ---- discriminator on the four generated digits ----------------------
        $display("[%0t] D on the 4 GENERATED digits", $time);
        run_discriminator(DST_SCORE_FAKE);

        // ---- discriminator on the real digit, replicated across lanes --------
        $display("[%0t] D on the real digit (same image in all 4 lanes)", $time);
        for (j = 0; j < BATCH; j = j + 1)
            for (i = 0; i < IMG_LEN; i = i + 1) himg[j][i] = real_img[i];
        run_discriminator(DST_SCORE_REAL);

        for (j = 0; j < BATCH; j = j + 1) exec(OP_LATCH_LOSS, j[7:0]);

        // ---- results ---------------------------------------------------------
        $display("");
        $display("[%0t] per-lane scores:", $time);
        for (j = 0; j < BATCH; j = j + 1) begin
            host_read(RSEL_MET, MET_Y_FAKE_L0 + j[9:0], rv);
            check24("y_fake[j] ", rv, met_exp[20 + j]);
        end
        for (j = 0; j < BATCH; j = j + 1) begin
            host_read(RSEL_MET, MET_Y_REAL_L0 + j[9:0], rv);
            check24("y_real[j] ", rv, met_exp[24 + j]);
        end
        $display("  (all four y_real must agree -- same image in every lane)");

        $display("");
        host_read(RSEL_MET, MET_ACC_LOSS_G, rv); check24("ACC_LOSS_G", rv, met_exp[5]);
        host_read(RSEL_MET, MET_ACC_LOSS_D, rv); check24("ACC_LOSS_D", rv, met_exp[6]);
        host_read(RSEL_MET, MET_N_SAMPLES, rv);  check24("N_SAMPLES ", rv, met_exp[7]);
        host_read(RSEL_MET, MET_N_FOOLED, rv);   check24("N_FOOLED  ", rv, met_exp[8]);
        host_read(RSEL_MET, MET_N_REAL_OK, rv);  check24("N_REAL_OK ", rv, met_exp[9]);
        host_read(RSEL_MET, MET_ACC_Y_FAKE, rv); check24("ACC_Y_FAKE", rv, met_exp[12]);
        host_read(RSEL_MET, MET_ACC_Y_REAL, rv); check24("ACC_Y_REAL", rv, met_exp[13]);
        host_read(RSEL_MET, MET_INK, rv);        check24("INK       ", rv, met_exp[14]);

        host_read(RSEL_MET, MET_CYCLES, rv);
        $display("");
        $display("  compute cycles for 4 digits = %0d  (%0d per digit)", rv, rv / 4);

        $display("");
        if (errors == 0)
            $display("PASS: batch-4 end-to-end matches scripts/gan_golden.py exactly");
        else
            $display("FAIL: %0d mismatches", errors);
        $finish;
    end

endmodule
