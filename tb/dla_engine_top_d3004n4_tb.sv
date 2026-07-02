`timescale 1ns / 1ps

// N=4/K=256 sibling of dla_engine_top_d3004_tb.sv: exercises all 4 output rows and
// all 4 A/B SRAM macros in parallel (the real hardened dla_engine_top default),
// instead of d3004's single-row N=1 sub-configuration. Row 0 reuses the exact
// D300_4_weight/bias fixture d3004 uses, so its golden value is d3004's own
// (-34139) by construction -- see scripts/gen_d3004n4_vectors.py.
module dla_engine_top_d3004n4_tb;
    localparam int N = 4;
    localparam int K = 256;
    localparam int DATA_W = 8;
    localparam int ACC_W = 24;
    localparam int AB_ADDR_W = (N * K <= 1) ? 1 : $clog2(N * K);
    localparam int C_ADDR_W = (N * N <= 1) ? 1 : $clog2(N * N);

    reg clk;
    reg rst_n;
    reg start;
    reg wr_en;
    reg wr_sel;
    reg [AB_ADDR_W-1:0] wr_addr;
    reg signed [DATA_W-1:0] wr_data;
    reg rd_en;
    reg [C_ADDR_W-1:0] rd_addr;
    wire signed [ACC_W-1:0] rd_data;
    wire wb_done;
    wire done;
    wire busy;

    reg signed [DATA_W-1:0] weights [0:(N*K)-1];
    reg signed [DATA_W-1:0] bias [0:N-1];
    reg signed [DATA_W-1:0] input_vec [0:K-1];
    reg signed [ACC_W-1:0] expected_val [0:N-1];

    string weights_memh;
    string bias_memh;
    string input_memh;
    string expected_memh;
    string vcd_path;

    integer i;
    integer row;
    integer mismatches;

    dla_engine_top #(
        .N(N),
        .K(K),
        .DATA_W(DATA_W),
        .ACC_W(ACC_W),
        .SRAM_LATENCY(1)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .start(start),
        .wr_en(wr_en),
        .wr_sel(wr_sel),
        .wr_addr(wr_addr),
        .wr_data(wr_data),
        .rd_en(rd_en),
        .rd_addr(rd_addr),
        .rd_data(rd_data),
        .wb_done(wb_done),
        .done(done),
        .busy(busy)
    );

    initial begin
        clk = 1'b0;
        forever #5 clk = ~clk;
    end

    initial begin
        if (!$value$plusargs("WEIGHTS_MEMH=%s", weights_memh)) begin
            weights_memh = "tb/data/d3004n4_weights.memh";
        end
        if (!$value$plusargs("BIAS_MEMH=%s", bias_memh)) begin
            bias_memh = "tb/data/d3004n4_bias.memh";
        end
        if (!$value$plusargs("INPUT_MEMH=%s", input_memh)) begin
            input_memh = "tb/data/d3004n4_input.memh";
        end
        if (!$value$plusargs("EXP_MEMH=%s", expected_memh)) begin
            expected_memh = "tb/data/d3004n4_expected.memh";
        end
        if (!$value$plusargs("VCD=%s", vcd_path)) begin
            vcd_path = "dla_engine_top_d3004n4_tb.vcd";
        end

        $readmemh(weights_memh, weights);
        $readmemh(bias_memh, bias);
        $readmemh(input_memh, input_vec);
        $readmemh(expected_memh, expected_val);

        $dumpfile(vcd_path);
        $dumpvars(0, dla_engine_top_d3004n4_tb);
    end

    initial begin
        rst_n = 1'b0;
        start = 1'b0;
        wr_en = 1'b0;
        wr_sel = 1'b0;
        wr_addr = {AB_ADDR_W{1'b0}};
        wr_data = {DATA_W{1'b0}};
        rd_en = 1'b0;
        rd_addr = {C_ADDR_W{1'b0}};

        repeat (5) @(posedge clk);
        rst_n = 1'b1;

        // Load 4 weight rows into the A buffer (row*K+k addressing, matches
        // dla_a_buffer_bank's wr_row = wr_addr/K, wr_col = wr_addr - wr_row*K).
        for (i = 0; i < N * K; i = i + 1) begin
            @(posedge clk);
            wr_en <= 1'b1;
            wr_sel <= 1'b0;
            wr_addr <= i[AB_ADDR_W-1:0];
            wr_data <= weights[i];
        end
        @(posedge clk);
        wr_en <= 1'b0;

        // Load the shared input vector into B column 0 only, matching the real usage
        // pattern (g300_pipeline_top.v's "B column 0, results read from C[i][0]").
        // dla_b_buffer_bank addresses as wr_addr = k*N + col (k outer, N-stride) --
        // the OPPOSITE layout from A's row*K+k -- so column 0 is wr_addr = k*N, not k.
        // Columns 1-3 stay at their power-up value.
        for (i = 0; i < K; i = i + 1) begin
            @(posedge clk);
            wr_en <= 1'b1;
            wr_sel <= 1'b1;
            wr_addr <= i * N;
            wr_data <= input_vec[i];
        end
        @(posedge clk);
        wr_en <= 1'b0;
        wr_sel <= 1'b0;

        // Start computation.
        @(posedge clk);
        start <= 1'b1;
        wait (wb_done == 1'b1);
        @(posedge clk);
        start <= 1'b0;

        // Read back C[row][0] for row = 0..N-1 (flat address row*N, per
        // dla_pe_array's FLAT_IDX = i*N+j) and apply each row's bias.
        mismatches = 0;
        for (row = 0; row < N; row = row + 1) begin
            reg signed [ACC_W-1:0] bias_ext;
            reg signed [ACC_W-1:0] result;

            // C buffer is a shared read/write single-port SRAM (1-cycle registered
            // read): the address presented THIS cycle is only captured at the next
            // edge, so rd_data isn't valid until a second edge after that. Spend one
            // cycle presenting rd_addr (rd_en high), then one more before sampling.
            rd_en <= 1'b1;
            rd_addr <= row * N;
            @(posedge clk);
            @(posedge clk);
            rd_en <= 1'b0;

            bias_ext = {{(ACC_W - DATA_W){bias[row][DATA_W-1]}}, bias[row]};
            result = rd_data + bias_ext;

            if (result !== expected_val[row]) begin
                mismatches = mismatches + 1;
                $display("Mismatch at row %0d: got %0d expected %0d", row, result, expected_val[row]);
            end else begin
                $display("row %0d: got %0d matches expected", row, result);
            end
        end

        if (mismatches != 0) begin
            $display("FAIL: %0d row mismatches", mismatches);
            $fatal(1);
        end else begin
            $display("PASS: all %0d rows match expected", N);
        end

        #20;
        $finish;
    end

endmodule
