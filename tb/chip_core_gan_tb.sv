`timescale 1ns / 1ps

// Pad-level testbench: drives the experimental GAN chip through the real 4-wire
// serial link (SCLK / MOSI / CS_N / MISO) exactly as external hardware would --
// no internal RTL ports are touched.
//
// The full-flow check lives in tb/gan_engine_top_tb.sv (parallel interface, ~440k
// cycles).  Streaming 801 KiB of weight writes one 24-bit serial frame at a time would take
// ~10^8 cycles, so this testbench instead proves the *interface*: every command in
// the protocol, the buffer address maps, one real MAC pass with known-good vectors,
// one post-processing flush, and the metric read path.  Together with the full-flow
// testbench that covers the chip end to end.
//
// It doubles as the reference host implementation for post-silicon bring-up: the
// frame sequences below port 1:1 onto an MCU bit-banging GPIO.
module chip_core_gan_tb;

`include "gan_defs.vh"

    localparam int NUM_INPUT_PADS  = 1;
    localparam int NUM_BIDIR_PADS  = 20;
    localparam int NUM_ANALOG_PADS = 60;

    // Serial commands (must match gan_serial_bridge.v).
    localparam [3:0] C_WR_A   = 4'd0, C_WR_B   = 4'd1, C_WR_IMG = 4'd2, C_WR_ACT = 4'd3,
                     C_WR_CFG = 4'd4, C_EXEC   = 4'd5, C_RD_MET = 4'd6, C_RD_IMG = 4'd7,
                     C_RD_ACT = 4'd8, C_RD_C   = 4'd9, C_WR_BURST = 4'd10,
                     C_WR_BURST8 = 4'd11;

    reg clk = 1'b0;
    reg rst_n = 1'b0;
    always #5 clk = ~clk;                       // 100 MHz sim clock

    reg  [NUM_BIDIR_PADS-1:0] bidir_drv = '0;   // what the host drives onto the pads
    wire [NUM_BIDIR_PADS-1:0] bidir_out, bidir_oe, bidir_cs, bidir_sl,
                              bidir_ie, bidir_pu, bidir_pd;
    wire [NUM_INPUT_PADS-1:0] input_pu, input_pd;
    wire [NUM_ANALOG_PADS-1:0] analog;

    // Model the pad ring: the core drives when bidir_oe is set, otherwise the host does.
    wire [NUM_BIDIR_PADS-1:0] bidir_in;
    genvar g;
    generate
        for (g = 0; g < NUM_BIDIR_PADS; g = g + 1) begin : GEN_PAD
            assign bidir_in[g] = bidir_oe[g] ? bidir_out[g] : bidir_drv[g];
        end
    endgenerate

    chip_core #(
        .NUM_INPUT_PADS  (NUM_INPUT_PADS),
        .NUM_BIDIR_PADS  (NUM_BIDIR_PADS),
        .NUM_ANALOG_PADS (NUM_ANALOG_PADS)
    ) dut (
        .clk(clk), .rst_n(rst_n),
        .input_in('0), .input_pu(input_pu), .input_pd(input_pd),
        .bidir_in(bidir_in), .bidir_out(bidir_out), .bidir_oe(bidir_oe),
        .bidir_cs(bidir_cs), .bidir_sl(bidir_sl), .bidir_ie(bidir_ie),
        .bidir_pu(bidir_pu), .bidir_pd(bidir_pd),
        .analog(analog)
    );

    localparam int PIN_SCLK = 0, PIN_MOSI = 1, PIN_CS_N = 2, PIN_MISO = 3,
                   PIN_BUSY = 4, PIN_VERDICT = 7,
                   PIN_PDATA_LO = 8, PIN_PDATA_HI = 15,
                   PIN_MISO_MIRROR = 16;

    wire miso    = bidir_in[PIN_MISO];
    wire miso_m  = bidir_in[PIN_MISO_MIRROR];
    wire busy    = bidir_in[PIN_BUSY];
    wire verdict = bidir_in[PIN_VERDICT];

    integer errors = 0;

    // bidir[16] mirrors MISO so that readback survives one dead pad or bond wire.  The
    // mirror is only worth its pad if it is bit-identical at every instant, not merely
    // at sample points, so watch both pads continuously rather than checking in the read
    // task -- a mirror that lagged by a delta cycle would pass the latter and fail on
    // silicon.
    integer mirror_errors = 0;
    always @(miso or miso_m) begin
        if (miso_m !== miso) begin
            mirror_errors = mirror_errors + 1;
            if (mirror_errors <= 5)
                $display("  [MIRROR] t=%0t bidir[%0d]=%b does not match MISO=%b",
                         $time, PIN_MISO_MIRROR, miso_m, miso);
        end
    end
    integer i;
    integer edges = 0;             // every SCLK pulse, for measuring link cost

    // ---- fixtures (declared before the tasks that read them) -----------------
    reg signed [7:0]  weights   [0:1023];
    reg signed [7:0]  input_vec [0:255];
    reg signed [7:0]  bias      [0:3];
    reg signed [23:0] expected  [0:3];

    // ---- serial primitives ---------------------------------------------------
    // SCLK is treated as data by the bridge (double-flop synchronised then edge
    // detected), so each level must be held at least 3 core clocks: SCLK <= clk/8.
    task sclk_pulse;
        begin
            edges = edges + 1;
            bidir_drv[PIN_SCLK] = 1'b1;
            repeat (4) @(posedge clk);
            bidir_drv[PIN_SCLK] = 1'b0;
            repeat (4) @(posedge clk);
        end
    endtask

    task shift_out(input integer nbits, input [31:0] value);
        integer b;
        begin
            for (b = nbits - 1; b >= 0; b = b - 1) begin
                bidir_drv[PIN_MOSI] = value[b];
                sclk_pulse;
            end
        end
    endtask

    task cs_low;
        begin
            bidir_drv[PIN_CS_N] = 1'b0;
            repeat (6) @(posedge clk);
        end
    endtask

    task cs_high;
        begin
            bidir_drv[PIN_CS_N] = 1'b1;
            repeat (6) @(posedge clk);
        end
    endtask

    // A write frame: CMD[3:0] ADDR[11:0] DATA[7:0]
    task ser_write(input [3:0] cmd, input [11:0] addr, input [7:0] data);
        begin
            cs_low;
            shift_out(4, {28'd0, cmd});
            shift_out(12, {20'd0, addr});
            shift_out(8, {24'd0, data});
            cs_high;
        end
    endtask

    // A config-register frame: CMD[3:0] ADDR[11:0] DATA[23:0]
    task ser_cfg(input [3:0] addr, input [23:0] data);
        begin
            cs_low;
            shift_out(4, {28'd0, C_WR_CFG});
            shift_out(12, {20'd0, addr});
            shift_out(24, {8'd0, data});
            cs_high;
        end
    endtask

    // An EXEC frame: the opcode and its argument ride in the address field.
    task ser_exec(input [3:0] op, input [7:0] arg);
        begin
            cs_low;
            shift_out(4, {28'd0, C_EXEC});
            shift_out(12, {20'd0, op, arg});
            cs_high;
            while (busy) @(posedge clk);
        end
    endtask

    // A read frame: CMD[3:0] ADDR[11:0], then 24 bits shifted out on MISO.
    // MISO is already valid before the first edge, so sample THEN pulse.
    task ser_read(input [3:0] cmd, input [11:0] addr, output [23:0] data);
        integer b;
        begin
            cs_low;
            shift_out(4, {28'd0, cmd});
            shift_out(12, {20'd0, addr});
            repeat (8) @(posedge clk);        // bridge's 3-phase address/read turnaround
            for (b = 23; b >= 0; b = b - 1) begin
                data[b] = miso;
                sclk_pulse;
            end
            cs_high;
        end
    endtask

    // Serial burst: address sent once, then raw bytes, one per 8 SCLK edges.
    // Only works where the destination addresses are consecutive -- which is exactly
    // the traffic that matters: the A buffer always, and B whenever batch > 1.
    task ser_burst(input [1:0] target, input [9:0] start, input integer n,
                   input integer src_base);
        integer b;
        begin
            cs_low;
            shift_out(4, {28'd0, C_WR_BURST});
            shift_out(12, {20'd0, target, start});
            for (b = 0; b < n; b = b + 1)
                shift_out(8, {24'd0, weights[src_base + b]});
            cs_high;
        end
    endtask

    // Parallel burst: one whole byte per SCLK edge off bidir[8..15].
    task ser_burst8(input [1:0] target, input [9:0] start, input integer n,
                    input integer src_base);
        integer b;
        begin
            cs_low;
            shift_out(4, {28'd0, C_WR_BURST8});
            shift_out(12, {20'd0, target, start});
            for (b = 0; b < n; b = b + 1) begin
                bidir_drv[PIN_PDATA_HI:PIN_PDATA_LO] = weights[src_base + b];
                sclk_pulse;
            end
            cs_high;
        end
    endtask

    task check(input [8*20:1] name, input signed [31:0] got, input signed [31:0] exp);
        begin
            if (got !== exp) begin
                $display("  MISMATCH %0s: got %0d, expected %0d", name, got, exp);
                errors = errors + 1;
            end else begin
                $display("  ok  %0s = %0d", name, got);
            end
        end
    endtask

    // ---- MAC vectors reused from the main branch's d3004n4 unit test ---------

    reg [23:0] rv;
    reg signed [23:0] cvals [0:3];
    integer e0, e_burst, e_burst8, e_burst8s;

    task exec_or_nop; begin @(posedge clk); end endtask

    // The requant the chip should apply, re-implemented independently here.
    // FUNC_IDENT is used so no PWL is involved: act == pre.
    // MA == MB == 4096 means the bias adds to the accumulator with unit weight, so
    // pre = (acc + bias) >> 8 -- which reproduces the d3004n4 golden exactly, since
    // that fixture's golden IS mac + bias (the MAC array itself never adds a bias).
    localparam signed [23:0] T_MA = 24'sd4096, T_MB = 24'sd4096;
    localparam integer       T_S  = 20, T_SH = 14;
    localparam signed [23:0] T_MH = 24'sd4096;

    function signed [31:0] expect_q(input signed [31:0] acc, input signed [31:0] b);
        reg signed [63:0] t;
        reg signed [63:0] pre;
        reg signed [63:0] q;
        begin
            t   = acc * 64'sd4096 + b * 64'sd4096;
            pre = (t + (64'sd1 <<< (T_S - 1))) >>> T_S;
            if (pre >  64'sd32767) pre =  64'sd32767;
            if (pre < -64'sd32768) pre = -64'sd32768;
            q   = (pre * 64'sd4096 + (64'sd1 <<< (T_SH - 1))) >>> T_SH;
            if (q >  64'sd127) q =  64'sd127;
            if (q < -64'sd128) q = -64'sd128;
            expect_q = q[31:0];
        end
    endfunction

    initial begin
        $readmemh("tb/data/d3004n4_weights.memh", weights);
        $readmemh("tb/data/d3004n4_input.memh", input_vec);
        $readmemh("tb/data/d3004n4_bias.memh", bias);
        $readmemh("tb/data/d3004n4_expected.memh", expected);

        bidir_drv = '0;
        bidir_drv[PIN_CS_N] = 1'b1;
        $display("=== chip_core_gan pad-level (serial) testbench ===");
        repeat (10) @(posedge clk);
        rst_n <= 1'b1;
        repeat (10) @(posedge clk);

        // ---- 1. buffer write/read paths through the pads --------------------
        $display("[1] image buffer write + readback across all four banks");
        ser_exec(OP_ZERO_IMG, 8'd0);
        ser_write(C_WR_IMG, 12'd0,   8'h7f);
        ser_write(C_WR_IMG, 12'd1,   8'h81);       // -127
        ser_write(C_WR_IMG, 12'd300, 8'h2a);       // bank 1
        ser_write(C_WR_IMG, 12'd783, 8'h05);       // last real pixel, bank 3
        ser_read(C_RD_IMG, 12'd0,   rv); check("IMG[0]  ", $signed(rv),  32'sd127);
        ser_read(C_RD_IMG, 12'd1,   rv); check("IMG[1]  ", $signed(rv), -32'sd127);
        ser_read(C_RD_IMG, 12'd300, rv); check("IMG[300]", $signed(rv),  32'sd42);
        ser_read(C_RD_IMG, 12'd783, rv); check("IMG[783]", $signed(rv),  32'sd5);
        ser_read(C_RD_IMG, 12'd2,   rv); check("IMG[2]  ", $signed(rv),  32'sd0);

        $display("[2] activation buffer write + readback");
        ser_exec(OP_ZERO_ACT, 8'd0);
        ser_write(C_WR_ACT, 12'd5,   8'h39);
        ser_write(C_WR_ACT, 12'd255, 8'hc0);       // -64
        ser_read(C_RD_ACT, 12'd5,   rv); check("ACT[5]  ", $signed(rv),  32'sd57);
        ser_read(C_RD_ACT, 12'd255, rv); check("ACT[255]", $signed(rv), -32'sd64);

        // ---- 3. a real MAC pass, driven entirely over the serial link -------
        $display("[3] streaming a 4x256 weight tile + 256-deep input vector (this is");
        $display("    the same d3004n4 fixture the main branch's unit test uses)");
        e0 = edges;
        ser_burst8(WSEL_A, 10'd0, 1024, 0);                  // A: row*256 + k, sequential
        e_burst8 = edges - e0;
        // B at batch 1 is strided (k*4), so it cannot burst -- but it is 256 bytes once
        // per layer against 1024 per tile, so it is not where the time goes.
        for (i = 0; i < 256; i = i + 1)
            ser_write(C_WR_B, i[11:0] * 4, input_vec[i]);    // B: k*4 + col
        ser_exec(OP_CLR_ACC, 8'd0);
        ser_exec(OP_TILE, 8'd0);

        for (i = 0; i < 4; i = i + 1) begin
            ser_read(C_RD_C, i[11:0] * 4, rv);
            cvals[i] = $signed(rv);
        end
        // The MAC array produces the dot product only; the d3004n4 golden includes
        // the layer bias, which on this chip is applied later by gan_postproc.
        check("C[0]", cvals[0], expected[0] - bias[0]);
        check("C[1]", cvals[1], expected[1] - bias[1]);
        check("C[2]", cvals[2], expected[2] - bias[2]);
        check("C[3]", cvals[3], expected[3] - bias[3]);

        // ---- 4. post-processing flush, checked against an independent model --
        $display("[4] config write + OP_FLUSH -> activation buffer");
        ser_cfg(CFG_MA,      T_MA);
        ser_cfg(CFG_MB,      T_MB);
        ser_cfg(CFG_S,       T_S);
        ser_cfg(CFG_MH,      T_MH);
        ser_cfg(CFG_SH,      T_SH);
        ser_cfg(CFG_FUNC,    {21'd0, GF_IDENT});
        ser_cfg(CFG_B0,      {{16{bias[0][7]}}, bias[0]});
        ser_cfg(CFG_B1,      {{16{bias[1][7]}}, bias[1]});
        ser_cfg(CFG_B2,      {{16{bias[2][7]}}, bias[2]});
        ser_cfg(CFG_B3,      {{16{bias[3][7]}}, bias[3]});
        ser_cfg(CFG_DST_SEL, {22'd0, DST_ACT});
        ser_cfg(CFG_NOUT,    24'd4);
        ser_cfg(CFG_DST_PTR, 24'd16);
        ser_exec(OP_FLUSH, 8'd0);

        for (i = 0; i < 4; i = i + 1) begin
            ser_read(C_RD_ACT, 12'd16 + i[11:0], rv);
            check("flush   ", $signed(rv), expect_q(cvals[i], bias[i]));
        end

        // The pointer auto-increments by NOUT, so the next flush lands at 20.
        ser_read(C_RD_MET, {7'd0, MET_LAST_ACC}, rv);
        $display("  MET_LAST_ACC (debug) = %0d", $signed(rv));

        // ---- 5. score path + metrics through the pads -----------------------
        $display("[5] sigmoid score + BCE loss through the serial link");
        ser_exec(OP_CLR_MET, 8'd0);
        ser_cfg(CFG_FUNC,    {21'd0, GF_SIGMOID});
        ser_cfg(CFG_S,       24'd22);           // scale C[0] down into the sigmoid's range
        ser_cfg(CFG_DST_SEL, {22'd0, DST_SCORE_FAKE});
        ser_cfg(CFG_NOUT,    24'd1);
        ser_exec(OP_FLUSH, 8'd0);
        ser_cfg(CFG_DST_SEL, {22'd0, DST_SCORE_REAL});
        ser_exec(OP_FLUSH, 8'd0);
        ser_exec(OP_LATCH_LOSS, 8'd0);

        ser_read(C_RD_MET, {7'd0, MET_Y_FAKE}, rv);
        $display("  y_fake    = %0d/4096", rv);
        if (rv > 24'd4096) begin
            $display("  ERROR: sigmoid output out of range"); errors = errors + 1;
        end
        ser_read(C_RD_MET, {7'd0, MET_Y_REAL}, rv);
        $display("  y_real    = %0d/4096", rv);
        ser_read(C_RD_MET, {7'd0, MET_LOSS_G}, rv);
        $display("  loss_G    = %0d (Q12.12)", rv);
        ser_read(C_RD_MET, {7'd0, MET_LOSS_G}, rv);
        if (rv == 24'd0) begin
            $display("  ERROR: loss_G is zero"); errors = errors + 1;
        end
        ser_read(C_RD_MET, {7'd0, MET_LOSS_D}, rv);
        $display("  loss_D    = %0d (Q12.12)", rv);
        ser_read(C_RD_MET, {7'd0, MET_N_SAMPLES}, rv);
        check("N_SAMPLES", $signed(rv), 32'sd1);
        ser_read(C_RD_MET, {7'd0, MET_STATUS}, rv);
        $display("  STATUS    = %06h   verdict pad = %0b", rv, verdict);

        // ---- 6. burst modes: correctness and measured cost -------------------
        $display("[6] burst write modes");
        exec_or_nop;
        // Measured over a full 1024-byte tile, which is the traffic that matters --
        // a 32-byte sample would amortise the 16-edge header badly and understate both.
        e0 = edges;
        ser_burst(WSEL_ACT, 10'd0, 1024, 0);                 // serial burst, one tile
        e_burst = edges - e0;
        for (i = 0; i < 1024; i = i + 32) begin
            ser_read(C_RD_ACT, i[11:0], rv);
            if ($signed(rv) !== weights[i]) begin
                $display("  MISMATCH burst ACT[%0d]: got %0d, expected %0d",
                         i, $signed(rv), weights[i]);
                errors = errors + 1;
            end
        end
        $display("    serial burst: 1024 bytes written, 32 spot-checked");

        e0 = edges;
        ser_burst8(WSEL_IMG, 10'd0, 1024, 0);                // parallel burst, one tile
        e_burst8s = edges - e0;
        for (i = 0; i < 1024; i = i + 32) begin
            ser_read(C_RD_IMG, i[11:0], rv);
            if ($signed(rv) !== weights[i]) begin
                $display("  MISMATCH burst8 IMG[%0d]: got %0d, expected %0d",
                         i, $signed(rv), weights[i]);
                errors = errors + 1;
            end
        end
        $display("    parallel burst: 1024 bytes written, 32 spot-checked");

        $display("");
        $display("    MEASURED SCLK edges for a 1024-byte tile (x100 fixed point):");
        $display("      single-byte frames : %0d edges,  %0d.%02d per byte,   1.00x",
                 1024 * 24, (1024 * 24) / 1024, ((1024 * 24) * 100 / 1024) % 100);
        $display("      serial burst       : %0d edges,  %0d.%02d per byte,  %0d.%02dx",
                 e_burst, e_burst / 1024, (e_burst * 100 / 1024) % 100,
                 (1024 * 24 * 100 / e_burst) / 100, (1024 * 24 * 100 / e_burst) % 100);
        $display("      parallel burst     : %0d edges,  %0d.%02d per byte, %0d.%02dx",
                 e_burst8s, e_burst8s / 1024, (e_burst8s * 100 / 1024) % 100,
                 (1024 * 24 * 100 / e_burst8s) / 100, (1024 * 24 * 100 / e_burst8s) % 100);
        $display("      (the A tile in test 3 also used parallel burst: %0d edges)",
                 e_burst8);

        $display("");
        $display("  [7] MISO mirror on bidir[%0d]: %0d divergences over the whole run",
                 PIN_MISO_MIRROR, mirror_errors);
        errors = errors + mirror_errors;

        if (errors == 0) $display("PASS: all serial-protocol checks matched");
        else             $display("FAIL: %0d mismatches", errors);
        $finish;
    end

endmodule
