`timescale 1ns / 1ps

// GAN sequencer: turns a handful of host opcodes into the full generator ->
// discriminator dataflow, with no host round-trip per neuron.
//
// The host still streams weights (the two networks hold 538 KiB of int8 weights and
// biases against 4.6 KB of on-chip SRAM -- they cannot live on the die), but everything
// else runs here:
//
//   per layer :   OP_LOADB_ACT | OP_LOADB_IMG    input vector -> DLA B buffer
//   per tile  :   host writes 4x256 weights into the DLA A buffer
//                 OP_CLR_ACC
//                 OP_TILE            x1 (or x4 for the 784-deep D input layer)
//                 OP_FLUSH           requant + activation + write-back, ptr += NOUT
//   per sample:   OP_LATCH_LOSS      BCE losses from the two sigmoid scores
//
// K-tiling (OP_TILE called repeatedly before one OP_FLUSH) is what lets a 784-input
// layer run on a K=256 MAC array: each pass contributes a 24-bit partial sum and the
// 28-bit accumulators here add them up.  The main branch had no such mode -- it could
// only ever evaluate contractions of exactly 256.
module gan_sequencer (
    input                     clk,
    input                     rst_n,

    // ---- command interface ----
    input                     exec_req,
    input      [3:0]          exec_op,
    input      [7:0]          exec_arg,
    output                    busy,

    // ---- config registers ----
    input  signed [19:0]      cfg_ma,
    input  signed [19:0]      cfg_mb,
    input      [4:0]          cfg_s,
    input  signed [19:0]      cfg_mh,
    input      [4:0]          cfg_sh,
    input      [2:0]          cfg_func,
    input  signed [7:0]       cfg_b0,
    input  signed [7:0]       cfg_b1,
    input  signed [7:0]       cfg_b2,
    input  signed [7:0]       cfg_b3,
    input      [9:0]          cfg_dst_ptr,
    input      [1:0]          cfg_dst_sel,
    input      [2:0]          cfg_nout,
    output reg                dst_ptr_inc,

    // ---- DLA engine ----
    output reg                dla_start,
    output reg                dla_wr_en,
    output reg                dla_wr_sel,
    output reg [9:0]          dla_wr_addr,
    output reg signed [7:0]   dla_wr_data,
    output                    dla_rd_en,
    output     [3:0]          dla_rd_addr,
    input  signed [23:0]      dla_rd_data,
    input                     dla_wb_done,

    // ---- activation buffer ----
    output reg                act_we,
    output reg [7:0]          act_waddr,
    output reg [7:0]          act_wdata,
    output     [7:0]          act_raddr,
    input      [7:0]          act_rdata,

    // ---- image buffer ----
    output reg                img_we,
    output reg [9:0]          img_waddr,
    output reg [7:0]          img_wdata,
    output     [9:0]          img_raddr,
    input      [7:0]          img_rdata,

    // ---- post-processor ----
    output reg                pp_req,
    output                    pp_skip,
    output signed [27:0]      pp_acc,
    output signed [7:0]       pp_bias,
    input                     pp_vld,
    input  signed [15:0]      pp_pre,
    input  signed [15:0]      pp_act,
    input  signed [7:0]       pp_q,
    input                     pp_sat_pre,
    input                     pp_sat_out,

    // ---- metrics ----
    output reg                met_clr,
    output reg                met_score_vld,
    output reg [12:0]         met_score_y,
    output reg                met_score_is_real,
    output reg signed [15:0]  met_logit,
    output reg                met_latch_loss,
    output reg                met_ink_vld,
    output reg signed [7:0]   met_ink_pixel,
    output reg                met_sat_pre,
    output reg                met_sat_out,
    output signed [27:0]      met_last_acc,
    input                     met_busy
);

`include "gan_defs.vh"

    localparam [3:0]
        S_IDLE     = 4'd0,
        S_ZB       = 4'd1,
        S_LB       = 4'd2,
        S_TILE_GO  = 4'd3,
        S_TILE_WT  = 4'd4,
        S_TILE_RD0 = 4'd5,
        S_TILE_RD1 = 4'd6,
        S_FL_REQ   = 4'd7,
        S_FL_WT    = 4'd8,
        S_ZA       = 4'd9,
        S_ZI       = 4'd10,
        S_LOSS_GO  = 4'd11,
        S_LOSS_WT  = 4'd12,
        // Every buffered write is issued through a REGISTERED strobe, so it is still
        // in flight the cycle after the state that scheduled it.  gan_engine_top gates
        // the sequencer's write ports with `busy`, so returning straight to S_IDLE would
        // hand the port back to the host while that last write was still asserted and
        // silently drop it.  S_FIN holds ownership for exactly that one cycle.
        S_FIN      = 4'd13;

    reg [3:0]  state;
    reg [10:0] k;                     // 0..1024 element counter
    reg [1:0]  i;                     // 0..3 neuron index within a tile
    reg [1:0]  img_page;              // K-tile page for OP_LOADB_IMG
    reg        lb_from_img;

    reg signed [27:0] acc [0:3];

    // exec_req is included so `busy` is already high on the cycle after a command is
    // accepted -- a host polling busy immediately never sees a false "idle".
    assign busy = (state != S_IDLE) || met_busy || exec_req;

    // Buffer read addresses are combinational so the registered SRAM output lands
    // exactly one cycle later, on the next value of `k`.
    assign act_raddr = k[7:0];
    assign img_raddr = {img_page, k[7:0]};

    // Absolute image index being *written* to B this cycle (data for k-1).
    wire [10:0] km1     = k - 11'd1;
    wire [9:0]  img_abs = {img_page, km1[7:0]};
    wire        img_ok  = (img_abs < GAN_IMG_LEN[9:0]);
    wire [7:0]  lb_byte = lb_from_img ? (img_ok ? img_rdata : 8'd0) : act_rdata;

    // Post-processor operands (must be stable while pp_req is asserted).
    wire is_score = (cfg_dst_sel == DST_SCORE_FAKE) || (cfg_dst_sel == DST_SCORE_REAL);
    assign pp_skip = is_score;
    assign pp_acc  = acc[i];
    assign pp_bias = (i == 2'd0) ? cfg_b0
                   : (i == 2'd1) ? cfg_b1
                   : (i == 2'd2) ? cfg_b2
                                 : cfg_b3;
    assign met_last_acc = acc[0];

    assign dla_rd_en   = (state == S_TILE_RD0) || (state == S_TILE_RD1);
    assign dla_rd_addr = {i, 2'b00};                 // C[i][0] = flat address i*N

    integer n;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= S_IDLE;
            k <= 11'd0; i <= 2'd0; img_page <= 2'd0; lb_from_img <= 1'b0;
            dla_start <= 1'b0; dla_wr_en <= 1'b0; dla_wr_sel <= 1'b0;
            dla_wr_addr <= 10'd0; dla_wr_data <= 8'sd0;
            act_we <= 1'b0; act_waddr <= 8'd0; act_wdata <= 8'd0;
            img_we <= 1'b0; img_waddr <= 10'd0; img_wdata <= 8'd0;
            pp_req <= 1'b0; dst_ptr_inc <= 1'b0;
            met_clr <= 1'b0; met_score_vld <= 1'b0; met_score_y <= 13'd0;
            met_score_is_real <= 1'b0; met_logit <= 16'sd0; met_latch_loss <= 1'b0;
            met_ink_vld <= 1'b0; met_ink_pixel <= 8'sd0;
            met_sat_pre <= 1'b0; met_sat_out <= 1'b0;
            for (n = 0; n < 4; n = n + 1) acc[n] <= 28'sd0;
        end else begin
            // Single-cycle strobes default low.
            dla_wr_en <= 1'b0;
            act_we <= 1'b0;
            img_we <= 1'b0;
            pp_req <= 1'b0;
            dst_ptr_inc <= 1'b0;
            met_clr <= 1'b0;
            met_score_vld <= 1'b0;
            met_latch_loss <= 1'b0;
            met_ink_vld <= 1'b0;
            met_sat_pre <= 1'b0;
            met_sat_out <= 1'b0;

            case (state)
                // ------------------------------------------------------------
                S_IDLE: if (exec_req) begin
                    k <= 11'd0;
                    i <= 2'd0;
                    case (exec_op)
                        OP_ZERO_B:    state <= S_ZB;
                        OP_ZERO_ACT:  state <= S_ZA;
                        OP_ZERO_IMG:  state <= S_ZI;
                        OP_LOADB_ACT: begin lb_from_img <= 1'b0;            state <= S_LB; end
                        OP_LOADB_IMG: begin lb_from_img <= 1'b1;
                                            img_page    <= exec_arg[1:0];   state <= S_LB; end
                        OP_TILE:      state <= S_TILE_GO;
                        OP_FLUSH:     state <= S_FL_REQ;
                        OP_CLR_ACC:   for (n = 0; n < 4; n = n + 1) acc[n] <= 28'sd0;
                        OP_CLR_MET:   met_clr <= 1'b1;
                        OP_LATCH_LOSS: state <= S_LOSS_GO;
                        default:      ;                      // OP_NOP
                    endcase
                end

                // ---- clear B column 0 --------------------------------------
                S_ZB: begin
                    dla_wr_en   <= 1'b1;
                    dla_wr_sel  <= 1'b1;
                    dla_wr_addr <= {k[7:0], 2'b00};
                    dla_wr_data <= 8'sd0;
                    if (k == 11'd255) state <= S_FIN;
                    else              k <= k + 1'b1;
                end

                // ---- copy ACT[] or IMG[page] into B column 0 ---------------
                // At counter k the buffer output holds element k-1, so the write
                // trails the read address by one cycle and the loop runs to 256.
                S_LB: begin
                    if (k != 11'd0) begin
                        dla_wr_en   <= 1'b1;
                        dla_wr_sel  <= 1'b1;
                        dla_wr_addr <= {km1[7:0], 2'b00};
                        dla_wr_data <= lb_byte;
                    end
                    if (k == 11'd256) state <= S_FIN;
                    else              k <= k + 1'b1;
                end

                // ---- clear the activation buffer ---------------------------
                S_ZA: begin
                    act_we    <= 1'b1;
                    act_waddr <= k[7:0];
                    act_wdata <= 8'd0;
                    if (k == 11'd255) state <= S_FIN;
                    else              k <= k + 1'b1;
                end

                // ---- clear the image buffer --------------------------------
                S_ZI: begin
                    img_we    <= 1'b1;
                    img_waddr <= k[9:0];
                    img_wdata <= 8'd0;
                    if (k == 11'd1023) state <= S_FIN;
                    else               k <= k + 1'b1;
                end

                // ---- one MAC pass over the loaded A/B tiles ----------------
                S_TILE_GO: begin
                    dla_start <= 1'b1;
                    state     <= S_TILE_WT;
                end

                S_TILE_WT: if (dla_wb_done) begin
                    dla_start <= 1'b0;
                    i         <= 2'd0;
                    state     <= S_TILE_RD0;
                end

                S_TILE_RD0: state <= S_TILE_RD1;    // C read address settling

                S_TILE_RD1: begin
                    acc[i] <= acc[i] + {{4{dla_rd_data[23]}}, dla_rd_data};
                    if (i == 2'd3) state <= S_IDLE;
                    else begin
                        i     <= i + 1'b1;
                        state <= S_TILE_RD0;
                    end
                end

                // ---- post-process the accumulators -------------------------
                S_FL_REQ: begin
                    pp_req <= 1'b1;
                    state  <= S_FL_WT;
                end

                S_FL_WT: if (pp_vld) begin
                    met_sat_pre <= pp_sat_pre;
                    met_sat_out <= pp_sat_out;
                    case (cfg_dst_sel)
                        DST_ACT: begin
                            act_we    <= 1'b1;
                            act_waddr <= cfg_dst_ptr[7:0] + {6'd0, i};
                            act_wdata <= pp_q;
                        end
                        DST_IMG: begin
                            img_we        <= 1'b1;
                            img_waddr     <= cfg_dst_ptr + {8'd0, i};
                            img_wdata     <= pp_q;
                            met_ink_vld   <= 1'b1;
                            met_ink_pixel <= pp_q;
                        end
                        default: begin
                            met_score_vld     <= 1'b1;
                            met_score_y       <= pp_act[12:0];
                            met_score_is_real <= cfg_dst_sel[0];
                            met_logit         <= pp_pre;
                        end
                    endcase

                    if ({1'b0, i} == (cfg_nout - 3'd1)) begin
                        dst_ptr_inc <= 1'b1;
                        state       <= S_FIN;
                    end else begin
                        i     <= i + 1'b1;
                        state <= S_FL_REQ;
                    end
                end

                // ---- BCE losses --------------------------------------------
                S_LOSS_GO: begin
                    met_latch_loss <= 1'b1;
                    state          <= S_LOSS_WT;
                end

                S_LOSS_WT: if (met_busy) state <= S_IDLE;   // metrics unit owns it now

                S_FIN: state <= S_IDLE;    // let the last registered write drain

                default: state <= S_IDLE;
            endcase
        end
    end

endmodule
