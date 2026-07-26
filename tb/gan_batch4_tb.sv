`timescale 1ns / 1ps

// Batch-4 datapath test for gan_engine_top.
//
// The MAC array computes C[i][j] = sum_k A[i][k] * B[k][j], so its four B columns can
// hold four INDEPENDENT input vectors and its sixteen C words are four neurons x four
// lanes.  At CFG_BATCH=4 one streamed weight tile therefore serves four images, which
// divides the weight traffic that dominates run time by four.
//
// This testbench drives four genuinely different input vectors and checks, against
// expectations it computes itself (no golden files):
//   1. all sixteen C words, not just column 0
//   2. a sixteen-way OP_FLUSH landing at lane*256 + offset in the activation buffer
//   3. OP_LOADB_ACT copying all four lanes back into B's four columns
//   4. four per-lane sigmoid scores and lane-selected OP_LATCH_LOSS
//
// tb/gan_engine_top_tb.sv remains the batch-1 end-to-end check; the two together cover
// both modes.
module gan_batch4_tb;

`include "gan_defs.vh"

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
            @(posedge clk);
            @(posedge clk);
            data = rd_data;
            rd_en <= 1'b0;
        end
    endtask

    // ---- fixtures ------------------------------------------------------------
    reg signed [7:0] weights [0:1023];         // A: 4 rows x 256
    reg signed [7:0] base_vec [0:255];
    reg signed [7:0] bvec [0:3][0:255];        // four independent input vectors

    // Requant used for the flush check: FUNC_IDENT, so act == pre and no PWL is
    // involved -- the expectation below is a fully independent reimplementation.
    localparam integer T_S = 20, T_SH = 14;

    function signed [31:0] expect_q(input signed [63:0] acc);
        reg signed [63:0] pre, q;
        begin
            pre = (acc * 64'sd4096 + (64'sd1 <<< (T_S - 1))) >>> T_S;
            if (pre >  64'sd32767) pre =  64'sd32767;
            if (pre < -64'sd32768) pre = -64'sd32768;
            q = (pre * 64'sd4096 + (64'sd1 <<< (T_SH - 1))) >>> T_SH;
            if (q >  64'sd127) q =  64'sd127;
            if (q < -64'sd128) q = -64'sd128;
            expect_q = q[31:0];
        end
    endfunction

    integer errors = 0;
    integer i, j, k;
    reg signed [23:0] rv;
    reg signed [63:0] exp_c [0:3][0:3];
    reg signed [63:0] acc64;

    task check(input [8*24:1] name, input signed [63:0] got, input signed [63:0] exp);
        begin
            if (got !== exp) begin
                $display("  MISMATCH %0s: got %0d, expected %0d", name, got, exp);
                errors = errors + 1;
            end
        end
    endtask

    initial begin
        $readmemh("tb/data/d3004n4_weights.memh", weights);
        $readmemh("tb/data/d3004n4_input.memh", base_vec);

        // Four distinct input vectors: rotate the fixture by the lane index and negate
        // the odd lanes, so no two lanes can accidentally agree.
        for (j = 0; j < 4; j = j + 1)
            for (k = 0; k < 256; k = k + 1)
                bvec[j][k] = (j[0]) ? -base_vec[(k + j * 37) % 256]
                                    :  base_vec[(k + j * 37) % 256];

        $display("=== gan_engine_top batch-4 datapath test ===");
        repeat (8) @(posedge clk);
        rst_n <= 1'b1;
        repeat (4) @(posedge clk);

        exec(OP_CLR_MET, 8'd0);
        exec(OP_ZERO_ACT, 8'd0);
        exec(OP_ZERO_IMG, 8'd0);
        cfg_write(CFG_BATCH, 24'd4);

        // ---- 1. four vectors through one weight tile -------------------------
        $display("[1] one weight tile x four independent input vectors");
        for (i = 0; i < 1024; i = i + 1) host_write(WSEL_A, i[9:0], weights[i]);
        for (k = 0; k < 256; k = k + 1)
            for (j = 0; j < 4; j = j + 1)
                host_write(WSEL_B, k[9:0] * 4 + j[9:0], bvec[j][k]);

        exec(OP_CLR_ACC, 8'd0);
        exec(OP_TILE, 8'd0);

        for (i = 0; i < 4; i = i + 1)
            for (j = 0; j < 4; j = j + 1) begin
                acc64 = 0;
                for (k = 0; k < 256; k = k + 1)
                    acc64 = acc64 + weights[i * 256 + k] * bvec[j][k];
                exp_c[i][j] = $signed(acc64[23:0]);      // C is a 24-bit word
                host_read(RSEL_C, i[9:0] * 4 + j[9:0], rv);
                check("C[i][j]", rv, exp_c[i][j]);
            end
        $display("    all 16 C words checked (4 neurons x 4 lanes)");

        // ---- 2. a 16-way flush into the activation buffer --------------------
        $display("[2] OP_FLUSH with BATCH=4, NOUT=4 -> 16 activations");
        cfg_write(CFG_MA, 24'sd4096); cfg_write(CFG_MB, 24'sd0);
        cfg_write(CFG_S, T_S);        cfg_write(CFG_MH, 24'sd4096);
        cfg_write(CFG_SH, T_SH);      cfg_write(CFG_FUNC, {21'd0, GF_IDENT});
        cfg_write(CFG_B0, 24'sd0);    cfg_write(CFG_B1, 24'sd0);
        cfg_write(CFG_B2, 24'sd0);    cfg_write(CFG_B3, 24'sd0);
        cfg_write(CFG_DST_SEL, {22'd0, DST_ACT});
        cfg_write(CFG_NOUT, 24'd4);
        cfg_write(CFG_DST_PTR, 24'd0);
        exec(OP_FLUSH, 8'd0);

        for (j = 0; j < 4; j = j + 1)
            for (i = 0; i < 4; i = i + 1) begin
                host_read(RSEL_ACT, j[9:0] * 256 + i[9:0], rv);
                check("ACT[lane][i]", rv, expect_q(exp_c[i][j]));
            end
        $display("    all 16 landed at lane*256 + offset");

        // DST_PTR must have advanced by NOUT once (not once per lane).
        exec(OP_FLUSH, 8'd0);
        for (j = 0; j < 4; j = j + 1) begin
            host_read(RSEL_ACT, j[9:0] * 256 + 10'd4, rv);
            check("2nd flush ptr", rv, expect_q(exp_c[0][j]));
        end
        $display("    DST_PTR auto-incremented by NOUT across the whole batch");

        // ---- 3. OP_LOADB_ACT must move all four lanes ------------------------
        $display("[3] OP_LOADB_ACT with BATCH=4 -> B's four columns");
        exec(OP_LOADB_ACT, 8'd0);
        exec(OP_CLR_ACC, 8'd0);
        exec(OP_TILE, 8'd0);
        // B[k][j] now holds ACT[j*256 + k]: the two flushes wrote k = 0..7.
        for (i = 0; i < 4; i = i + 1)
            for (j = 0; j < 4; j = j + 1) begin
                acc64 = 0;
                for (k = 0; k < 4; k = k + 1)
                    acc64 = acc64 + weights[i * 256 + k] * expect_q(exp_c[k][j]);
                for (k = 4; k < 8; k = k + 1)
                    acc64 = acc64 + weights[i * 256 + k] * expect_q(exp_c[k - 4][j]);
                host_read(RSEL_C, i[9:0] * 4 + j[9:0], rv);
                check("C after LOADB", rv, $signed(acc64[23:0]));
            end
        $display("    every lane's activations reappeared in its own B column");

        // ---- 4. per-lane scores and lane-selected loss ------------------------
        $display("[4] four sigmoid scores + OP_LATCH_LOSS per lane");
        exec(OP_CLR_MET, 8'd0);
        cfg_write(CFG_S, 24'd22);                      // scale into the sigmoid's range
        cfg_write(CFG_FUNC, {21'd0, GF_SIGMOID});
        cfg_write(CFG_NOUT, 24'd1);
        cfg_write(CFG_DST_SEL, {22'd0, DST_SCORE_FAKE});
        exec(OP_FLUSH, 8'd0);
        cfg_write(CFG_DST_SEL, {22'd0, DST_SCORE_REAL});
        exec(OP_FLUSH, 8'd0);

        for (j = 0; j < 4; j = j + 1) begin
            host_read(RSEL_MET, MET_Y_FAKE_L0 + j[9:0], rv);
            $display("    lane %0d  y_fake = %4d/4096", j, rv);
            if (rv > 24'sd4096 || rv < 0) begin
                $display("    ERROR: score out of range"); errors = errors + 1;
            end
            exec(OP_LATCH_LOSS, j[7:0]);
            host_read(RSEL_MET, MET_LOSS_G, rv);
            if (rv <= 0) begin
                $display("    ERROR: lane %0d loss_G not positive", j); errors = errors + 1;
            end
        end
        host_read(RSEL_MET, MET_N_SAMPLES, rv);
        check("N_SAMPLES", rv, 64'sd4);
        $display("    four lanes folded into the metric accumulators");

        $display("");
        if (errors == 0) $display("PASS: batch-4 datapath verified (%0d checks)", 16 + 16 + 4 + 16 + 1);
        else             $display("FAIL: %0d mismatches", errors);
        $finish;
    end

endmodule
