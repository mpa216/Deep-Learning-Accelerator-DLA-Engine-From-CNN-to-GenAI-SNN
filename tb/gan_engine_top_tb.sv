`timescale 1ns / 1ps

// Full-flow testbench for the experimental GAN chip.
//
// Plays the part of the host: streams weights tile by tile, programs the per-layer
// config registers, and issues the sequencer opcodes that run
//
//     generator -> 784-pixel digit -> discriminator(fake) -> discriminator(real)
//                                  -> BCE losses + metrics
//
// then checks the image, the two scores, the losses and the whole metric register
// file against scripts/gan_golden.py (regenerate with gen_gan_chip_assets.py first).
//
// Drives the parallel host interface; tb/chip_core_gan_tb.sv covers the same design
// through the real 4-wire serial pads.
module gan_engine_top_tb;

`include "gan_defs.vh"

    // Where a layer's input vector comes from (see run_layer).
    localparam integer SRC_PRELOADED = 0, SRC_ACT = 1, SRC_IMG = 2;

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

    // ---- host-side model of the weight store (streams in from the host) -------
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

    reg signed [23:0] cfgmem   [0:(6*16)-1];      // 6 layers x 16 config registers
    reg signed [7:0]  zq       [0:63];
    reg signed [7:0]  real_img [0:783];
    reg signed [7:0]  img_exp  [0:783];
    reg signed [23:0] met_exp  [0:31];

    reg signed [7:0]  img_got  [0:783];

    integer errors = 0;
    integer i, j, k, t, kt, row, grow, layer;
    integer f;

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
        $readmemh("tb/data/gan_chip/gan_cfg.memh", cfgmem);
        $readmemh("tb/data/gan_chip/gan_zq.memh", zq);
        $readmemh("tb/data/gan_chip/gan_real_img.memh", real_img);
        $readmemh("tb/data/gan_chip/gan_img_expected.memh", img_exp);
        $readmemh("tb/data/gan_chip/gan_met_expected.memh", met_exp);
    end

    // ---- weight / bias accessors --------------------------------------------
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
                0: bget = b_g0[idx];
                1: bget = b_g2[idx];
                2: bget = b_g4[idx];
                3: bget = b_d0[idx];
                4: bget = b_d2[idx];
                default: bget = b_d4[idx];
            endcase
        end
    endfunction

    // ---- host primitives -----------------------------------------------------
    task host_write(input [1:0] sel, input [9:0] addr, input signed [7:0] data);
        begin
            @(posedge clk);
            wr_en <= 1'b1; wr_sel <= sel; wr_addr <= addr; wr_data <= data;
            @(posedge clk);
            wr_en <= 1'b0;
        end
    endtask

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
            @(posedge clk);          // address captured by the SRAM here
            @(posedge clk);          // registered data now visible
            data = rd_data;
            rd_en <= 1'b0;
        end
    endtask

    task load_cfg_block(input integer lyr);
        integer q;
        begin
            for (q = 0; q < 16; q = q + 1) begin
                cfg_write(q[3:0], cfgmem[lyr * 16 + q]);
            end
        end
    endtask

    // ---- write one tile's 4 weight rows into the A buffer --------------------
    // `pad_all` writes the full 256-deep row (needed once per layer to clear the
    // tail); later tiles of a short layer only rewrite the live part.
    task write_a_tile(input integer lyr, input integer tile, input integer in_dim,
                      input integer ktile, input integer pad_all);
        integer r, kk, kabs, nwr;
        begin
            nwr = pad_all ? 256 : ((in_dim - ktile * 256) > 256 ? 256
                                                                : (in_dim - ktile * 256));
            for (r = 0; r < 4; r = r + 1) begin
                for (kk = 0; kk < nwr; kk = kk + 1) begin
                    kabs = ktile * 256 + kk;
                    host_write(WSEL_A, r * 256 + kk,
                               (kabs < in_dim) ? wget(lyr, tile * 4 + r, kabs) : 8'sd0);
                end
            end
        end
    endtask

    // ---- run one dense layer end to end -------------------------------------
    // src selects where the layer's INPUT vector comes from:
    //   SRC_PRELOADED  B already holds it (the host wrote the latent there)
    //   SRC_ACT        copy it from the activation buffer (every hidden layer)
    //   SRC_IMG        copy it from the image buffer, one K-tile at a time
    //                  (the discriminator's 784-wide first layer)
    task run_layer(input integer lyr, input integer out_dim, input integer in_dim,
                   input integer src, input [1:0] dsel, input integer nout);
        integer n_kt, ntile, r;
        reg signed [7:0] btmp;
        begin
            load_cfg_block(lyr);
            cfg_write(CFG_DST_SEL, {22'd0, dsel});
            cfg_write(CFG_NOUT,    nout);
            cfg_write(CFG_DST_PTR, 24'sd0);

            n_kt  = (in_dim + 255) / 256;
            ntile = (out_dim + nout - 1) / nout;

            if (src == SRC_ACT) exec(OP_LOADB_ACT, 8'd0);

            for (t = 0; t < ntile; t = t + 1) begin
                exec(OP_CLR_ACC, 8'd0);
                for (kt = 0; kt < n_kt; kt = kt + 1) begin
                    if (src == SRC_IMG) exec(OP_LOADB_IMG, kt[7:0]);
                    write_a_tile(lyr, t, in_dim, kt, (t == 0) ? 1 : 0);
                    exec(OP_TILE, 8'd0);
                end
                for (r = 0; r < 4; r = r + 1) begin
                    btmp = (t * 4 + r < out_dim) ? bget(lyr, t * 4 + r) : 8'sd0;
                    cfg_write(CFG_B0 + r[3:0], {{16{btmp[7]}}, btmp});
                end
                exec(OP_FLUSH, 8'd0);
            end
        end
    endtask

    task run_discriminator(input [1:0] score_sel);
        begin
            run_layer(3, 256, 784, SRC_IMG, DST_ACT,   4);
            run_layer(4, 256, 256, SRC_ACT, DST_ACT,   4);
            run_layer(5, 1,   256, SRC_ACT, score_sel, 1);
        end
    endtask

    // ---- checking helpers ----------------------------------------------------
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

    reg signed [23:0] rv;
    integer ndiff;
    integer maxdiff;
    integer d;

    initial begin
        $display("=== gan_engine_top full-flow testbench ===");
        repeat (8) @(posedge clk);
        rst_n <= 1'b1;
        repeat (4) @(posedge clk);

        // SRAM macros power up with undefined contents.
        exec(OP_CLR_MET, 8'd0);
        exec(OP_ZERO_ACT, 8'd0);
        exec(OP_ZERO_IMG, 8'd0);
        exec(OP_ZERO_B, 8'd0);

        // ---- generator -------------------------------------------------------
        $display("[%0t] generator: loading latent", $time);
        for (k = 0; k < 256; k = k + 1) begin
            host_write(WSEL_B, k[9:0] * 4, (k < 64) ? zq[k] : 8'sd0);
        end
        $display("[%0t] generator: layer 0 (64->256, ReLU)", $time);
        run_layer(0, 256, 64,  SRC_PRELOADED, DST_ACT, 4);   // z is already in B
        $display("[%0t] generator: layer 1 (256->256, ReLU)", $time);
        run_layer(1, 256, 256, SRC_ACT, DST_ACT, 4);
        $display("[%0t] generator: layer 2 (256->784, PWL tanh)", $time);
        run_layer(2, 784, 256, SRC_ACT, DST_IMG, 4);

        // ---- read the digit back and compare --------------------------------
        $display("[%0t] reading back the generated image", $time);
        for (i = 0; i < 784; i = i + 1) begin
            host_read(RSEL_IMG, i[9:0], rv);
            img_got[i] = rv[7:0];
        end

        ndiff = 0; maxdiff = 0;
        for (i = 0; i < 784; i = i + 1) begin
            if (img_got[i] !== img_exp[i]) begin
                ndiff = ndiff + 1;
                d = (img_got[i] > img_exp[i]) ? (img_got[i] - img_exp[i])
                                              : (img_exp[i] - img_got[i]);
                if (d > maxdiff) maxdiff = d;
                if (ndiff <= 8)
                    $display("  pixel %0d: got %0d, expected %0d", i, img_got[i], img_exp[i]);
            end
        end
        if (ndiff == 0) $display("  IMAGE OK: 784/784 pixels bit-exact vs golden");
        else begin
            $display("  IMAGE MISMATCH: %0d/784 pixels differ (max |d| = %0d)", ndiff, maxdiff);
            errors = errors + 1;
        end

        f = $fopen("tb/data/gan_chip/gan_img_rtl.memh", "w");
        for (i = 0; i < 784; i = i + 1) $fwrite(f, "%02x\n", img_got[i]);
        $fclose(f);

        // ASCII preview, same ramp as the asset generator.
        $display("");
        for (i = 0; i < 28; i = i + 1) begin
            $write("  ");
            for (j = 0; j < 28; j = j + 1) begin
                d = (img_got[i * 28 + j] + 128) * 10 / 256;
                case (d)
                    0: $write(" "); 1: $write("."); 2: $write(":"); 3: $write("-");
                    4: $write("="); 5: $write("+"); 6: $write("*"); 7: $write("#");
                    8: $write("%%"); default: $write("@");
                endcase
            end
            $write("\n");
        end
        $display("");

        // ---- discriminator on the generated digit ----------------------------
        $display("[%0t] discriminator on the GENERATED digit", $time);
        run_discriminator(DST_SCORE_FAKE);

        // ---- discriminator on a real digit -----------------------------------
        $display("[%0t] loading the real digit and re-running D", $time);
        for (i = 0; i < 784; i = i + 1) host_write(WSEL_IMG, i[9:0], real_img[i]);
        run_discriminator(DST_SCORE_REAL);

        // ---- losses ----------------------------------------------------------
        exec(OP_LATCH_LOSS, 8'd0);

        // ---- metric register file --------------------------------------------
        $display("");
        $display("[%0t] metric register file:", $time);
        host_read(RSEL_MET, MET_Y_FAKE, rv);     check24("Y_FAKE    ", rv, met_exp[MET_Y_FAKE]);
        host_read(RSEL_MET, MET_Y_REAL, rv);     check24("Y_REAL    ", rv, met_exp[MET_Y_REAL]);
        host_read(RSEL_MET, MET_LOSS_G, rv);     check24("LOSS_G    ", rv, met_exp[MET_LOSS_G]);
        host_read(RSEL_MET, MET_LOSS_D, rv);     check24("LOSS_D    ", rv, met_exp[MET_LOSS_D]);
        host_read(RSEL_MET, MET_ACC_LOSS_G, rv); check24("ACC_LOSS_G", rv, met_exp[MET_ACC_LOSS_G]);
        host_read(RSEL_MET, MET_ACC_LOSS_D, rv); check24("ACC_LOSS_D", rv, met_exp[MET_ACC_LOSS_D]);
        host_read(RSEL_MET, MET_N_SAMPLES, rv);  check24("N_SAMPLES ", rv, met_exp[MET_N_SAMPLES]);
        host_read(RSEL_MET, MET_N_FOOLED, rv);   check24("N_FOOLED  ", rv, met_exp[MET_N_FOOLED]);
        host_read(RSEL_MET, MET_N_REAL_OK, rv);  check24("N_REAL_OK ", rv, met_exp[MET_N_REAL_OK]);
        host_read(RSEL_MET, MET_ACC_Y_FAKE, rv); check24("ACC_Y_FAKE", rv, met_exp[MET_ACC_Y_FAKE]);
        host_read(RSEL_MET, MET_ACC_Y_REAL, rv); check24("ACC_Y_REAL", rv, met_exp[MET_ACC_Y_REAL]);
        host_read(RSEL_MET, MET_INK, rv);        check24("INK       ", rv, met_exp[MET_INK]);
        host_read(RSEL_MET, MET_SAT_PRE, rv);    check24("SAT_PRE   ", rv, met_exp[MET_SAT_PRE]);
        host_read(RSEL_MET, MET_SAT_OUT, rv);    check24("SAT_OUT   ", rv, met_exp[MET_SAT_OUT]);
        host_read(RSEL_MET, MET_LOGIT, rv);      check24("LOGIT     ", rv, met_exp[MET_LOGIT]);

        host_read(RSEL_MET, MET_Y_FAKE, rv);
        $display("");
        $display("  D(generated) = %0d/4096 = %0d%%  -> VERDICT %0s",
                 rv, (rv * 100) / 4096,
                 (rv > 2048) ? "REAL (generator fooled the discriminator)" : "FAKE");
        host_read(RSEL_MET, MET_Y_REAL, rv);
        $display("  D(real)      = %0d/4096 = %0d%%", rv, (rv * 100) / 4096);
        host_read(RSEL_MET, MET_CYCLES, rv);
        $display("  compute cycles (sequencer busy) = %0d", rv);
        host_read(RSEL_MET, MET_SAT_PRE, rv);
        $display("  pre-activation clamps           = %0d (all in the tanh layer: harmless)", rv);
        host_read(RSEL_MET, MET_SAT_OUT, rv);
        $display("  output-quantiser clamps         = %0d", rv);
        $display("  verdict pad                     = %0b", verdict);

        // Dump the whole metric register file as the chip reports it, so
        // scripts/plot_gan_metrics.py --dump can graph REAL RTL output rather than
        // the golden model.  Same format a bring-up host emits over the serial link.
        f = $fopen("tb/data/gan_chip/gan_met_rtl.txt", "w");
        $fwrite(f, "# metric registers read from gan_engine_top (RTL run)\n");
        for (i = 0; i < 20; i = i + 1) begin
            host_read(RSEL_MET, i[9:0], rv);
            case (i)
                0:  $fwrite(f, "STATUS %0d\n", rv);
                1:  $fwrite(f, "Y_FAKE %0d\n", rv);
                2:  $fwrite(f, "Y_REAL %0d\n", rv);
                3:  $fwrite(f, "LOSS_G %0d\n", rv);
                4:  $fwrite(f, "LOSS_D %0d\n", rv);
                5:  $fwrite(f, "ACC_LOSS_G %0d\n", rv);
                6:  $fwrite(f, "ACC_LOSS_D %0d\n", rv);
                7:  $fwrite(f, "N_SAMPLES %0d\n", rv);
                8:  $fwrite(f, "N_FOOLED %0d\n", rv);
                9:  $fwrite(f, "N_REAL_OK %0d\n", rv);
                10: $fwrite(f, "Y_FAKE_MIN %0d\n", rv);
                11: $fwrite(f, "Y_FAKE_MAX %0d\n", rv);
                12: $fwrite(f, "ACC_Y_FAKE %0d\n", rv);
                13: $fwrite(f, "ACC_Y_REAL %0d\n", rv);
                14: $fwrite(f, "INK %0d\n", rv);
                15: $fwrite(f, "SAT_PRE %0d\n", rv);
                16: $fwrite(f, "SAT_OUT %0d\n", rv);
                17: $fwrite(f, "CYCLES %0d\n", rv);
                18: $fwrite(f, "LOGIT %0d\n", rv);
                default: $fwrite(f, "LAST_ACC %0d\n", rv);
            endcase
        end
        $fclose(f);
        $display("  metric dump -> tb/data/gan_chip/gan_met_rtl.txt");

        $display("");
        if (errors == 0) $display("PASS: chip output matches scripts/gan_golden.py exactly");
        else             $display("FAIL: %0d mismatches", errors);
        $finish;
    end

endmodule
