`timescale 1ns / 1ps

// Per-layer activation capture: the drain path host-side training runs on.
//
// `scripts/gan_train_host.py` keeps the weight update on the host, and to backpropagate
// it needs every layer's ACTIVATION OUTPUT -- not the pre-activation, because every
// activation here has a derivative expressible in its own output (ReLU' = a>0,
// tanh' = 1-a^2, sigmoid' = a(1-a)).  Those outputs come back over the existing RD_ACT
// and RD_IMG reads, so training needs no new RTL -- but nothing verified that what the
// host reads out mid-network actually matches the model.  tb/gan_batch4_flow_tb.sv
// only checks the final image and the metric registers; this fills that gap.
//
// After every ACT-producing layer the host drains the whole 1 KiB buffer and compares
// it byte for byte against scripts/gan_golden.py:
//
//   L0 G0(z)      L1 G2        L2 D0(fake)   L3 D2(fake)   L4 D0(real)   L5 D2(real)
//
// The generator's output layer writes IMG instead, and is checked against the same
// golden digits the flow testbench uses.
//
// Regenerate the golden data first:
//   python3 scripts/gen_gan_chip_assets.py --batch4 --capture-act
module gan_train_capture_tb;

`include "gan_defs.vh"

    localparam integer BATCH   = 4;
    localparam integer IMG_LEN = 784;
    localparam integer NCAP    = 6;

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
    reg signed [7:0]  zq      [0:(4*64)-1];
    reg signed [7:0]  real_img[0:783];
    reg signed [7:0]  img_exp [0:(4*784)-1];

    // Six 1 KiB activation-buffer images, one per capture point, flat: L*1024 + addr.
    reg signed [7:0]  act_exp [0:(NCAP*1024)-1];

    reg signed [7:0]  himg [0:3][0:783];

    integer errors = 0;
    integer act_errors = 0;
    integer i, j, k, t, kt, f;
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
        $readmemh("tb/data/gan_chip/gan_act_expected_L0_b4.memh", act_exp,    0, 1023);
        $readmemh("tb/data/gan_chip/gan_act_expected_L1_b4.memh", act_exp, 1024, 2047);
        $readmemh("tb/data/gan_chip/gan_act_expected_L2_b4.memh", act_exp, 2048, 3071);
        $readmemh("tb/data/gan_chip/gan_act_expected_L3_b4.memh", act_exp, 3072, 4095);
        $readmemh("tb/data/gan_chip/gan_act_expected_L4_b4.memh", act_exp, 4096, 5119);
        $readmemh("tb/data/gan_chip/gan_act_expected_L5_b4.memh", act_exp, 5120, 6143);
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

    // ---- host primitives (identical to tb/gan_batch4_flow_tb.sv) ---------------
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

    // ---- THE CHECK: drain the whole activation buffer and compare -------------
    // This is exactly what the training host does between layers, over the same
    // RSEL_ACT reads, so a pass here is what licenses the host backward pass.
    task check_act(input [8*10:1] name, input integer cap, input integer out_dim);
        integer jj, o, bad;
        reg signed [7:0] got, exp;
        begin
            bad = 0;
            for (jj = 0; jj < BATCH; jj = jj + 1)
                for (o = 0; o < out_dim; o = o + 1) begin
                    host_read(RSEL_ACT, jj * 256 + o, rv);
                    got = rv[7:0];
                    exp = act_exp[cap * 1024 + jj * 256 + o];
                    if (got !== exp) begin
                        bad = bad + 1;
                        if (bad <= 4)
                            $display("    lane %0d addr %0d: got %0d, expected %0d",
                                     jj, o, got, exp);
                    end
                end
            if (bad == 0)
                $display("  ok       %0s drained %0d/%0d bytes bit-exact",
                         name, BATCH * out_dim, BATCH * out_dim);
            else begin
                $display("  MISMATCH %0s: %0d of %0d drained bytes differ",
                         name, bad, BATCH * out_dim);
                act_errors = act_errors + bad;
                errors = errors + 1;
            end
        end
    endtask

    // ---- a whole layer, batch 4 ----------------------------------------------
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

    integer ndiff;

    initial begin
        $display("=== gan_engine_top per-layer ACTIVATION CAPTURE (batch 4) ===");
        $display("    the drain path scripts/gan_train_host.py backpropagates from");
        repeat (8) @(posedge clk);
        rst_n <= 1'b1;
        repeat (4) @(posedge clk);

        exec(OP_CLR_MET, 8'd0);
        exec(OP_ZERO_ACT, 8'd0);
        exec(OP_ZERO_IMG, 8'd0);
        cfg_write(CFG_BATCH, BATCH);

        // four latents into B's four columns
        @(posedge clk);
        wr_en <= 1'b1; wr_sel <= WSEL_B;
        for (k = 0; k < 256; k = k + 1)
            for (j = 0; j < BATCH; j = j + 1) begin
                wr_addr <= k * 4 + j;
                wr_data <= (k < 64) ? zq[j * 64 + k] : 8'sd0;
                @(posedge clk);
            end
        wr_en <= 1'b0;

        // ---- generator -------------------------------------------------------
        $display("[%0t] G layer 0 (64->256, ReLU)", $time);
        run_layer(0, 256, 64, 0, DST_ACT, 4);
        check_act("G0        ", 0, 256);

        $display("[%0t] G layer 1 (256->256, ReLU)", $time);
        run_layer(1, 256, 256, 1, DST_ACT, 4);
        check_act("G2        ", 1, 256);

        $display("[%0t] G layer 2 (256->784, PWL tanh) -> IMG, host drain", $time);
        run_layer(2, 784, 256, 1, DST_IMG, 4);

        ndiff = 0;
        for (j = 0; j < BATCH; j = j + 1)
            for (i = 0; i < IMG_LEN; i = i + 1)
                if (himg[j][i] !== img_exp[j * 784 + i]) ndiff = ndiff + 1;
        if (ndiff == 0)
            $display("  ok       G4 -> IMG  3136/3136 drained pixels bit-exact");
        else begin
            $display("  MISMATCH G4 -> IMG: %0d/3136 pixels differ", ndiff);
            errors = errors + 1;
        end

        // ---- discriminator on the four generated digits ----------------------
        $display("[%0t] D on the 4 generated digits", $time);
        run_layer(3, 256, 784, 2, DST_ACT, 4);
        check_act("D0(fake)  ", 2, 256);
        run_layer(4, 256, 256, 1, DST_ACT, 4);
        check_act("D2(fake)  ", 3, 256);
        run_layer(5, 1, 256, 1, DST_SCORE_FAKE, 1);

        // ---- discriminator on the real digit, replicated across lanes --------
        $display("[%0t] D on the real digit (same image in all 4 lanes)", $time);
        for (j = 0; j < BATCH; j = j + 1)
            for (i = 0; i < IMG_LEN; i = i + 1) himg[j][i] = real_img[i];
        run_layer(3, 256, 784, 2, DST_ACT, 4);
        check_act("D0(real)  ", 4, 256);
        run_layer(4, 256, 256, 1, DST_ACT, 4);
        check_act("D2(real)  ", 5, 256);
        run_layer(5, 1, 256, 1, DST_SCORE_REAL, 1);

        // ---- the scores the host turns into dL/dlogit ------------------------
        $display("");
        for (j = 0; j < BATCH; j = j + 1) begin
            host_read(RSEL_MET, MET_Y_FAKE_L0 + j[9:0], rv);
            $display("  lane %0d y_fake = %0d", j, rv);
        end
        for (j = 0; j < BATCH; j = j + 1) begin
            host_read(RSEL_MET, MET_Y_REAL_L0 + j[9:0], rv);
            $display("  lane %0d y_real = %0d", j, rv);
        end

        $display("");
        if (errors == 0)
            $display("PASS: every drained activation matches gan_golden.py -- the host has everything backpropagation needs");
        else
            $display("FAIL: %0d layers bad (%0d bytes)", errors, act_errors);
        $finish;
    end

endmodule
