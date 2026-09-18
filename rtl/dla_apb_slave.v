`timescale 1ns / 1ps

// =============================================================================
// dla_apb_slave -- an AMBA APB3 slave front-end for dla_engine_top.
//
// Closes the "standard-bus front-end" gap: the accelerator's native interface
// (wr_en/wr_sel/wr_addr/wr_data + rd_en/rd_addr/rd_data + start/busy/done/
// wb_done) is register/handshake-shaped but not a named protocol.  This wraps
// it behind APB3 so it can drop onto an APB peripheral bus like any IP.  The
// serial bridge (dla_serial_bridge) remains the pad-level option; this is the
// on-SoC option.
//
// APB3 compliance: PREADY-based wait states, PSLVERR, PENABLE/PSEL two-phase.
// The one wait state that matters is on C reads -- the C buffer has a 1-cycle
// registered read (SRAM_LATENCY), so a read cannot complete in a single access
// phase; PREADY is held low for one cycle to absorb that latency.
//
// Register map (byte addresses; PADDR[13:12] selects the region):
//   0x0000..0x0FFF  A window : write A[idx]  = PWDATA[7:0], idx = PADDR[11:2] (0..1023)
//   0x1000..0x1FFF  B window : write B[idx]  = PWDATA[7:0], idx = PADDR[11:2] (0..1023)
//   0x2000..0x203F  C window : read  C[idx]  -> PRDATA (24-bit sign-extended), idx=PADDR[5:2] (0..15)
//   0x3000          CTRL     : write, PWDATA[0]=1 pulses `start`
//   0x3004          STATUS   : read  -> {..., wb_done, done, busy}
// A write elsewhere, or a read of a write-only region, raises PSLVERR.
// =============================================================================
module dla_apb_slave #(
    parameter APB_ADDR_W = 16     // bytes of address space decoded (>= 14)
) (
    input                       PCLK,
    input                       PRESETn,
    // --- APB3 slave port ---
    input                       PSEL,
    input                       PENABLE,
    input                       PWRITE,
    input  [APB_ADDR_W-1:0]     PADDR,
    input  [31:0]               PWDATA,
    output reg [31:0]           PRDATA,
    output                      PREADY,
    output                      PSLVERR
);
    // ---- region decode ----
    localparam [1:0] REG_A = 2'd0, REG_B = 2'd1, REG_C = 2'd2, REG_CTRL = 2'd3;
    wire [1:0] region = PADDR[13:12];

    localparam [1:0] CTRL_OFF = 2'd0;   // PADDR[3:2] within the CTRL region
    localparam [1:0] STAT_OFF = 2'd1;

    // APB access phase (data phase): PSEL & PENABLE.
    wire access = PSEL & PENABLE;

    wire is_wr        = access &  PWRITE;
    wire is_rd        = access & ~PWRITE;
    wire wr_ab        = is_wr & (region == REG_A || region == REG_B);
    wire wr_ctrl      = is_wr & (region == REG_CTRL) & (PADDR[3:2] == CTRL_OFF);
    wire rd_c         = is_rd & (region == REG_C);
    wire rd_status    = is_rd & (region == REG_CTRL) & (PADDR[3:2] == STAT_OFF);

    // ---- wait-state generation ----
    // Every access is single-cycle (PREADY=1) EXCEPT a C read, which needs one
    // wait cycle for the registered read.  cwait=1 marks that we are in the
    // second (data-valid) cycle of a C read.
    reg cwait;
    always @(posedge PCLK or negedge PRESETn) begin
        if (!PRESETn)              cwait <= 1'b0;
        else if (rd_c & ~cwait)    cwait <= 1'b1;   // first C-read cycle -> insert wait
        else                       cwait <= 1'b0;
    end
    // PREADY low only during the first cycle of a C read.
    assign PREADY = ~(rd_c & ~cwait);

    // ---- accelerator control/data interface ----
    wire        dla_start  = wr_ctrl & PWDATA[0];
    wire        dla_wr_en  = wr_ab;
    wire        dla_wr_sel = (region == REG_B);
    wire [9:0]  dla_wr_addr = PADDR[11:2];
    wire signed [7:0] dla_wr_data = PWDATA[7:0];

    // Issue the registered C read in the FIRST C-read cycle so the data is valid
    // in the second (when PREADY rises).
    wire        dla_rd_en   = rd_c & ~cwait;
    wire [3:0]  dla_rd_addr = PADDR[5:2];
    wire signed [23:0] dla_rd_data;

    wire dla_busy, dla_done, dla_wb_done;

    dla_engine_top u_dla (
        .clk     (PCLK),
        .rst_n   (PRESETn),
        .start   (dla_start),
        .wr_en   (dla_wr_en),
        .wr_sel  (dla_wr_sel),
        .wr_addr (dla_wr_addr),
        .wr_data (dla_wr_data),
        .rd_en   (dla_rd_en),
        .rd_addr (dla_rd_addr),
        .rd_data (dla_rd_data),
        .wb_done (dla_wb_done),
        .done    (dla_done),
        .busy    (dla_busy)
    );

    // ---- read data mux ----
    always @(*) begin
        PRDATA = 32'd0;
        if (rd_c)           PRDATA = {{8{dla_rd_data[23]}}, dla_rd_data};      // sign-extend 24->32
        else if (rd_status) PRDATA = {29'd0, dla_wb_done, dla_done, dla_busy}; // [2:0]
    end

    // ---- error response: writes to read-only / undecoded, reads of write-only ----
    wire wr_bad = is_wr & ~(wr_ab | wr_ctrl);
    wire rd_bad = is_rd & ~(rd_c | rd_status);
    assign PSLVERR = wr_bad | rd_bad;

endmodule
