`timescale 1ns / 1ps

// Self-checking testbench for dla_apb_slave: drives the DLA entirely over APB3
// (write A/B windows -> pulse START via CTRL -> poll STATUS -> read C window),
// and checks the 16 results against a golden matmul computed here in the TB.
// Also checks PREADY wait-stating on C reads and PSLVERR on a bad access.
//
//   iverilog -g2012 -s dla_apb_tb -o sim/results/dla_apb_tb.vvp \
//     rtl/dla_apb_slave.v rtl/dla_engine_top.v rtl/dla_controller.v rtl/dla_pe.v \
//     rtl/dla_pe_array.v rtl/dla_a_buffer_bank.v rtl/dla_b_buffer_bank.v \
//     rtl/dla_c_buffer_bank.v rtl/gf180_sram_1rw_256x8.v rtl/gf180_sram_1rw_64x8.v \
//     tb/dla_apb_tb.sv
//   vvp sim/results/dla_apb_tb.vvp
module dla_apb_tb;
    localparam N = 4, K = 256;

    reg         PCLK = 0;
    reg         PRESETn;
    reg         PSEL, PENABLE, PWRITE;
    reg  [15:0] PADDR;
    reg  [31:0] PWDATA;
    wire [31:0] PRDATA;
    wire        PREADY, PSLVERR;

    reg         last_slverr;   // PSLVERR captured at the completing edge of a transfer

    always #5 PCLK = ~PCLK;    // 100 MHz

    dla_apb_slave #(.APB_ADDR_W(16)) dut (
        .PCLK(PCLK), .PRESETn(PRESETn),
        .PSEL(PSEL), .PENABLE(PENABLE), .PWRITE(PWRITE),
        .PADDR(PADDR), .PWDATA(PWDATA), .PRDATA(PRDATA),
        .PREADY(PREADY), .PSLVERR(PSLVERR));

    // ---- region base addresses ----
    localparam [15:0] A_BASE = 16'h0000, B_BASE = 16'h1000,
                      C_BASE = 16'h2000, CTRL   = 16'h3000, STATUS = 16'h3004;

    // ---- APB3 master tasks (two-phase, PREADY-aware) ----
    task automatic apb_write(input [15:0] addr, input [31:0] data);
        begin
            @(negedge PCLK); PSEL=1; PWRITE=1; PADDR=addr; PWDATA=data; PENABLE=0;
            @(negedge PCLK); PENABLE=1;
            @(posedge PCLK); while (!PREADY) @(posedge PCLK);
            last_slverr = PSLVERR;
            @(negedge PCLK); PSEL=0; PENABLE=0; PWRITE=0;
        end
    endtask

    task automatic apb_read(input [15:0] addr, output [31:0] data);
        begin
            @(negedge PCLK); PSEL=1; PWRITE=0; PADDR=addr; PENABLE=0;
            @(negedge PCLK); PENABLE=1;
            @(posedge PCLK); while (!PREADY) @(posedge PCLK);
            data = PRDATA; last_slverr = PSLVERR;
            @(negedge PCLK); PSEL=0; PENABLE=0;
        end
    endtask

    // ---- stimulus + golden ----
    integer i, j, k;
    integer A [0:N-1][0:K-1];
    integer B [0:K-1][0:N-1];
    integer expc [0:N-1][0:N-1];
    reg signed [31:0] rd;
    integer errors = 0;
    integer cread_waited = 0;

    initial begin
        PSEL=0; PENABLE=0; PWRITE=0; PADDR=0; PWDATA=0; last_slverr=0;
        PRESETn=0;
        repeat (5) @(posedge PCLK);
        PRESETn=1;
        @(posedge PCLK);

        // Deterministic signed INT8 pattern that varies with every index, so a
        // transposed/mis-strided address would change the result.
        for (i=0;i<N;i=i+1) for (k=0;k<K;k=k+1) A[i][k] = ((i*3 + k) % 7) - 3;  // -3..3
        for (k=0;k<K;k=k+1) for (j=0;j<N;j=j+1) B[k][j] = ((k + j*2) % 5) - 2;  // -2..2
        for (i=0;i<N;i=i+1) for (j=0;j<N;j=j+1) begin
            expc[i][j] = 0;
            for (k=0;k<K;k=k+1) expc[i][j] = expc[i][j] + A[i][k]*B[k][j];
        end

        // Load A: wr_addr = i*K + k    (A window)
        for (i=0;i<N;i=i+1) for (k=0;k<K;k=k+1)
            apb_write(A_BASE + ((i*K + k) << 2), {24'd0, A[i][k][7:0]});
        // Load B: wr_addr = k*N + j    (B window)
        for (k=0;k<K;k=k+1) for (j=0;j<N;j=j+1)
            apb_write(B_BASE + ((k*N + j) << 2), {24'd0, B[k][j][7:0]});

        // Start, then poll STATUS.wb_done (bit 2).
        apb_write(CTRL, 32'h1);
        rd = 0;
        while (!rd[2]) apb_read(STATUS, rd);

        // Read C[i][j] = rd_addr i*N + j, compare to golden.
        for (i=0;i<N;i=i+1) for (j=0;j<N;j=j+1) begin
            apb_read(C_BASE + ((i*N + j) << 2), rd);
            if (rd !== expc[i][j]) begin
                $display("  MISMATCH C[%0d][%0d]: apb=%0d golden=%0d", i, j, rd, expc[i][j]);
                errors = errors + 1;
            end
        end

        // Check that C reads actually inserted a wait state (PREADY protocol works).
        // (measured separately below via the monitor)
        // PSLVERR: a write to the read-only STATUS address must error.
        apb_write(STATUS, 32'hDEAD_BEEF);
        if (last_slverr !== 1'b1) begin
            $display("  PSLVERR not raised on bad write");
            errors = errors + 1;
        end
        // A legal write must NOT error.
        apb_write(A_BASE, 32'd0);
        if (last_slverr !== 1'b0) begin
            $display("  PSLVERR wrongly raised on good write");
            errors = errors + 1;
        end

        if (errors == 0 && cread_waited > 0)
            $display("PASS: all 16 C values match golden over APB3; C reads wait-stated (%0d); PSLVERR ok",
                     cread_waited);
        else
            $display("FAIL: errors=%0d cread_waited=%0d", errors, cread_waited);
        $finish;
    end

    // Monitor: count C-read accesses that were held with PREADY low (wait state).
    always @(posedge PCLK) if (PRESETn && PSEL && PENABLE && !PWRITE
                               && PADDR[13:12]==2'd2 && !PREADY)
        cread_waited = cread_waited + 1;

    // Safety timeout.
    initial begin
        #5_000_000;
        $display("FAIL: timeout");
        $finish;
    end
endmodule
