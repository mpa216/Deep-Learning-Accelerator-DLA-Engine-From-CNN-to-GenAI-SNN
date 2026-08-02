`timescale 1ns / 1ps

module dla_engine_top_d3004_tb;
    localparam int N = 1;
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

    reg signed [DATA_W-1:0] weights [0:K-1];
    reg signed [DATA_W-1:0] bias [0:0];
    reg signed [DATA_W-1:0] input_vec [0:K-1];
    reg signed [ACC_W-1:0] expected_val [0:0];

    string weights_dir;
    string input_memh;
    string expected_memh;
    string vcd_path;
    string actual_memh;
    string actual_txt;

    integer i;

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
        if (!$value$plusargs("WEIGHTS_DIR=%s", weights_dir)) begin
            weights_dir = "weights_vh/mnist_gan_mlp";
        end
        if (!$value$plusargs("INPUT_MEMH=%s", input_memh)) begin
            input_memh = "tb/data/d3004_input.memh";
        end
        if (!$value$plusargs("EXP_MEMH=%s", expected_memh)) begin
            expected_memh = "tb/data/d3004_expected.memh";
        end
        if (!$value$plusargs("VCD=%s", vcd_path)) begin
            vcd_path = "dla_engine_top_d3004_tb.vcd";
        end
        if (!$value$plusargs("ACTUAL_MEMH=%s", actual_memh)) begin
            actual_memh = "tb/data/d3004_actual.memh";
        end
        if (!$value$plusargs("ACTUAL_TXT=%s", actual_txt)) begin
            actual_txt = "tb/data/d3004_actual.txt";
        end

        $readmemh({weights_dir, "/D300_4_weight.memh"}, weights);
        $readmemh({weights_dir, "/D300_4_bias.memh"}, bias);
        $readmemh(input_memh, input_vec);
        $readmemh(expected_memh, expected_val);

        $dumpfile(vcd_path);
        $dumpvars(0, dla_engine_top_d3004_tb);
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

        // Load weights into A buffer.
        for (i = 0; i < K; i = i + 1) begin
            @(posedge clk);
            wr_en <= 1'b1;
            wr_sel <= 1'b0;
            wr_addr <= i[AB_ADDR_W-1:0];
            wr_data <= weights[i];
        end
        @(posedge clk);
        wr_en <= 1'b0;

        // Load input vector into B buffer.
        for (i = 0; i < K; i = i + 1) begin
            @(posedge clk);
            wr_en <= 1'b1;
            wr_sel <= 1'b1;
            wr_addr <= i[AB_ADDR_W-1:0];
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

        // Read the result and apply bias.  The C buffer holds a 24-bit word as
        // three byte planes of one 8-bit macro, so a read needs 3 plane accesses
        // plus the macro's 1-cycle registered latency: hold rd_en/rd_addr steady
        // for 4 edges before sampling.  See dla_c_buffer_bank.v.
        rd_en <= 1'b1;
        rd_addr <= {C_ADDR_W{1'b0}};
        // Five edges, not four: a testbench samples rd_data in the active
        // region straight after an edge, whereas the RTL callers sample it
        // from a clocked block one region later.  The last byte plane is
        // latched by a nonblocking assign on the 4th edge, so it only
        // becomes visible here on the 5th.
        @(posedge clk);
        @(posedge clk);
        @(posedge clk);
        @(posedge clk);
        @(posedge clk);
        rd_en <= 1'b0;

        begin
            reg signed [ACC_W-1:0] bias_ext;
            reg signed [ACC_W-1:0] result;
            reg signed [ACC_W-1:0] exp;
            integer fh_memh;
            integer fh_txt;

            bias_ext = {{(ACC_W - DATA_W){bias[0][DATA_W-1]}}, bias[0]};
            result = rd_data + bias_ext;
            exp = expected_val[0];

            fh_memh = $fopen(actual_memh, "w");
            if (fh_memh) begin
                $fdisplay(fh_memh, "%06h", result[ACC_W-1:0]);
                $fclose(fh_memh);
            end else begin
                $display("Warning: could not open ACTUAL_MEMH=%s", actual_memh);
            end

            fh_txt = $fopen(actual_txt, "w");
            if (fh_txt) begin
                $fdisplay(fh_txt, "%0d", result);
                $fclose(fh_txt);
            end else begin
                $display("Warning: could not open ACTUAL_TXT=%s", actual_txt);
            end

            if (result !== exp) begin
                $display("Mismatch: got %0d, expected %0d", result, exp);
                $fatal(1);
            end else begin
                $display("PASS: output %0d matches expected", result);
            end
        end

        #20;
        $finish;
    end

endmodule
