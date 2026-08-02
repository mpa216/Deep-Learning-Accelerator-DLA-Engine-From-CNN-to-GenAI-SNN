`timescale 1ns / 1ps

// C buffer: N*N accumulated 24-bit outputs in ONE 64x8 SRAM macro.
//
// Was three 256x8 macros used as byte planes -- u_sram0 = bits[7:0], u_sram1 =
// [15:8], u_sram2 = [23:16] -- sharing one address bus so a 24-bit word moved in a
// single cycle.  That spent 203,313 um2 of macro to hold 48 bytes: only addresses
// 0..15 of a 256-deep part were ever used, 6.25% occupancy, because C_DEPTH is
// N*N = 16 and nothing about the design will ever make it larger.
//
// Here the three planes are folded into ONE macro along the address axis instead:
//
//     sram_addr = word*3 + plane        word 0..15, plane 0..2  ->  48 of 64 used
//
// 45,861 um2, a 77% cut, and two fewer macros for the floorplan to route around.
// 64 is the shallowest depth this SRAM family offers, so this is the floor.
//
// The cost is that a 24-bit access is now three SRAM cycles rather than one:
//
//   WRITE  hold wr_en, wr_addr and wr_data steady; the bank walks the three planes
//          and pulses wr_ack on the last one.  The writer advances on wr_ack, so
//          writeback runs 48 cycles per start instead of 16.  Against K=256 compute
//          cycles that is ~+11.8% per start, the price paid for the area.
//
//   READ   hold rd_en and rd_addr steady; the bank walks the planes and assembles
//          rd_data.  Valid from the 4th cycle after rd_en rises (3 plane reads plus
//          the macro's 1-cycle registered read latency).  Callers must wait that
//          long -- C_RD_LATENCY below is the contract, and every caller in this
//          repo (g300_pipeline_top, dla_serial_bridge, the unit testbenches) is
//          written against it.
//
// Writes take priority over reads on the shared address port, as before.  The two
// never overlap in practice: `busy` covers writeback, and callers read after it.
//
// The USE_SRAM=0 register variant is unchanged in behaviour and completes a write
// in one cycle, so it ties wr_ack = wr_en and keeps rd_data at 1-cycle latency.
module dla_c_buffer_bank #(
    parameter N        = 4,
    parameter ACC_W    = 24,
    parameter ADDR_W   = (N*N <= 1) ? 1 : $clog2(N*N),
    parameter USE_SRAM = 1
) (
    input                              clk,
    input                              rst_n,
    input                              wr_en,
    input [ADDR_W-1:0]                 wr_addr,
    input signed [ACC_W-1:0]           wr_data,
    output                             wr_ack,
    input                              rd_en,
    input [ADDR_W-1:0]                 rd_addr,
    output signed [ACC_W-1:0]          rd_data
);

    localparam integer C_DEPTH     = N * N;
    localparam integer PLANES      = ACC_W / 8;   // 3 byte planes per 24-bit word
    localparam integer SRAM_ADDR_W = 6;           // 64-deep macro

    generate
        if (USE_SRAM) begin : GEN_SRAM
            reg  [1:0] wp;                 // plane being written
            reg  [1:0] rp;                 // plane being requested on the read port
            reg  [1:0] rp_d;               // plane whose data lands this cycle
            reg        rd_en_d;
            reg  [7:0] b0, b1, b2;
            wire [7:0] q;

            wire last_plane = (wp == PLANES[1:0] - 2'd1);

            // ---- write plane walker -------------------------------------------
            // wp resets whenever the writer drops wr_en, so a fresh word always
            // starts at plane 0 even if a write is aborted part way through.
            always @(posedge clk or negedge rst_n) begin
                if (!rst_n)      wp <= 2'd0;
                else if (!wr_en) wp <= 2'd0;
                else             wp <= last_plane ? 2'd0 : wp + 2'd1;
            end

            assign wr_ack = wr_en && last_plane;

            // ---- read plane walker --------------------------------------------
            // A read is only issued when the port is not taken by a write, so the
            // plane counter must stall on write cycles too -- otherwise rp would
            // run ahead of the data actually coming back and the bytes would be
            // filed under the wrong plane.
            wire rd_issue = rd_en && !wr_en;

            // The walk also restarts whenever rd_addr moves.  Callers are not
            // required to drop rd_en between reads -- the unit testbenches hold it
            // high across a whole row sweep and just change the address -- so
            // without this the planes of consecutive words interleave and the
            // assembled word is a mix of two addresses.  Combinational, because the
            // restart has to affect the address issued in the very same cycle.
            reg [ADDR_W-1:0] rd_addr_q;
            wire addr_moved = (rd_addr != rd_addr_q);
            wire [1:0] rp_cur = (!rd_en || addr_moved) ? 2'd0 : rp;

            always @(posedge clk or negedge rst_n) begin
                if (!rst_n) begin
                    rp        <= 2'd0;
                    rp_d      <= 2'd0;
                    rd_en_d   <= 1'b0;
                    rd_addr_q <= {ADDR_W{1'b0}};
                end else begin
                    rp <= rd_issue ? ((rp_cur == PLANES[1:0] - 2'd1) ? 2'd0 : rp_cur + 2'd1)
                                   : rp_cur;
                    rp_d      <= rp_cur;
                    rd_en_d   <= rd_issue;
                    rd_addr_q <= rd_addr;
                end
            end

            // Capture each plane as it comes back, one cycle after its address went out.
            always @(posedge clk) begin
                if (rd_en_d) begin
                    case (rp_d)
                        2'd0: b0 <= q;
                        2'd1: b1 <= q;
                        2'd2: b2 <= q;
                        default: ;
                    endcase
                end
            end

            // ---- shared single port -------------------------------------------
            wire [ADDR_W-1:0] word  = wr_en ? wr_addr : rd_addr;
            wire [1:0]        plane = wr_en ? wp      : rp_cur;

            // word*3 + plane, built as word*2 + word + plane so synthesis gets a
            // shift and an add rather than a multiplier.
            wire [SRAM_ADDR_W-1:0] sram_addr =
                {{(SRAM_ADDR_W-ADDR_W){1'b0}}, word} * PLANES[SRAM_ADDR_W-1:0]
                + {{(SRAM_ADDR_W-2){1'b0}}, plane};

            reg [7:0] wbyte;
            always @(*) begin
                case (wp)
                    2'd0: wbyte = wr_data[7:0];
                    2'd1: wbyte = wr_data[15:8];
                    2'd2: wbyte = wr_data[23:16];
                    default: wbyte = 8'h00;
                endcase
            end

            dla_sram_1rw_64x8 u_sram (
                .clk(clk),
                .we(wr_en),
                .addr(sram_addr),
                .wdata(wbyte),
                .rdata(q)
            );

            assign rd_data = {b2, b1, b0};
        end else begin : GEN_REG
            reg signed [ACC_W-1:0] mem [0:C_DEPTH-1];
            reg signed [ACC_W-1:0] rd_reg;

            always @(posedge clk) begin
                if (wr_en) begin
                    mem[wr_addr] <= wr_data;
                end
                if (rd_en) begin
                    rd_reg <= mem[rd_addr];
                end
            end

            assign rd_data = rd_reg;
            assign wr_ack  = wr_en;
        end
    endgenerate

endmodule
