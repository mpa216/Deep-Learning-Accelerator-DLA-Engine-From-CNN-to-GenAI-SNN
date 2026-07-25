`timescale 1ns / 1ps

// ============================================================================
// gan_engine_top -- TAPEOUT BOUNDARY of the experimental full-GAN chip.
// ============================================================================
//
// Supersedes dla_engine_top as the hardened Stage-1 macro.  Where the main branch
// taped out a bare INT8 matrix-multiply engine and left the GAN itself to a
// simulation-only wrapper (g300_pipeline_top) and to the host, this block runs the
// whole thing:
//
//     z (64) --G--> 256 --G--> 256 --G--> 784 int8 pixels  (an MNIST digit)
//                                            |
//                                            +--D--> 256 --D--> 256 --D--> y
//     real digit from the host --------------+                        (sigmoid score)
//
// plus the BCE losses and the run statistics, so the host can plot a loss curve
// straight from chip registers.  Activations use the 9-segment piecewise-linear
// tanh/sigmoid of the UAS_VLSI reference design.
//
// SRAM macro budget: 16 x (256 x 8)
//     A buffer   4    weight tile rows        (inside dla_engine_top)
//     B buffer   4    shared input vector     (inside dla_engine_top)
//     C buffer   3    24-bit MAC results      (inside dla_engine_top)
//     ACT        1    layer output activations
//     IMG        4    the 784-pixel image
//
// Weights are NOT on chip: the two networks hold ~645 KB of int8 weights against
// 4.6 KB of SRAM, so the host streams one 4x256 tile at a time into the A buffer --
// the same arrangement the main-branch chip used, and the only one that fits.
// ============================================================================
module gan_engine_top (
    input                     clk,
    input                     rst_n,

    // ---- host data writes (accepted while !busy) ----
    input                     wr_en,
    input      [1:0]          wr_sel,      // WSEL_A / WSEL_B / WSEL_IMG / WSEL_ACT
    input      [9:0]          wr_addr,
    input  signed [7:0]       wr_data,

    // ---- host config-register writes ----
    input                     cfg_we,
    input      [3:0]          cfg_addr,
    input  signed [23:0]      cfg_data,

    // ---- host command ----
    input                     exec_req,    // 1-cycle pulse
    input      [3:0]          exec_op,
    input      [7:0]          exec_arg,

    // ---- host reads (1-cycle registered for IMG/ACT/C, combinational for MET) ----
    input                     rd_en,
    input      [1:0]          rd_sel,      // RSEL_MET / RSEL_IMG / RSEL_ACT / RSEL_C
    input      [9:0]          rd_addr,
    output reg signed [23:0]  rd_data,

    // ---- status ----
    output                    busy,
    output                    verdict,     // y_fake > 0.5: the generator fooled D
    output                    dla_busy,
    output                    dla_done
);

`include "gan_defs.vh"

    // ------------------------------------------------------------------
    // Config register file
    // ------------------------------------------------------------------
    reg signed [23:0] cfg [0:15];
    wire        dst_ptr_inc;
    wire [2:0]  cfg_nout = cfg[CFG_NOUT][2:0];

    integer ci;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (ci = 0; ci < 16; ci = ci + 1) cfg[ci] <= 24'sd0;
        end else begin
            if (cfg_we) begin
                cfg[cfg_addr] <= cfg_data;
            end
            // A flush advances the write pointer, so a whole layer needs one
            // CFG_DST_PTR write instead of one per tile.
            if (dst_ptr_inc) begin
                cfg[CFG_DST_PTR] <= cfg[CFG_DST_PTR] + {21'd0, cfg_nout};
            end
        end
    end

    wire signed [19:0] cfg_ma   = cfg[CFG_MA][19:0];
    wire signed [19:0] cfg_mb   = cfg[CFG_MB][19:0];
    wire [4:0]         cfg_s    = cfg[CFG_S][4:0];
    wire signed [19:0] cfg_mh   = cfg[CFG_MH][19:0];
    wire [4:0]         cfg_sh   = cfg[CFG_SH][4:0];
    wire [2:0]         cfg_func = cfg[CFG_FUNC][2:0];
    wire signed [7:0]  cfg_b0   = cfg[CFG_B0][7:0];
    wire signed [7:0]  cfg_b1   = cfg[CFG_B1][7:0];
    wire signed [7:0]  cfg_b2   = cfg[CFG_B2][7:0];
    wire signed [7:0]  cfg_b3   = cfg[CFG_B3][7:0];
    wire [9:0]         cfg_dptr = cfg[CFG_DST_PTR][9:0];
    wire [1:0]         cfg_dsel = cfg[CFG_DST_SEL][1:0];

    // ------------------------------------------------------------------
    // Sequencer <-> host arbitration for the shared write/read ports
    // ------------------------------------------------------------------
    wire        seq_busy;
    wire        seq_dla_start, seq_dla_wr_en, seq_dla_wr_sel;
    wire [9:0]  seq_dla_wr_addr;
    wire signed [7:0] seq_dla_wr_data;
    wire        seq_dla_rd_en;
    wire [3:0]  seq_dla_rd_addr;

    wire        seq_act_we, seq_img_we;
    wire [7:0]  seq_act_waddr, seq_act_wdata, seq_act_raddr;
    wire [9:0]  seq_img_waddr, seq_img_raddr;
    wire [7:0]  seq_img_wdata;

    wire host_w = wr_en && !seq_busy;

    wire        dla_wr_en   = seq_busy ? seq_dla_wr_en   : (host_w && (wr_sel == WSEL_A ||
                                                                        wr_sel == WSEL_B));
    wire        dla_wr_sel  = seq_busy ? seq_dla_wr_sel  : (wr_sel == WSEL_B);
    wire [9:0]  dla_wr_addr = seq_busy ? seq_dla_wr_addr : wr_addr;
    wire signed [7:0] dla_wr_data = seq_busy ? seq_dla_wr_data : wr_data;

    wire        dla_rd_en   = seq_busy ? seq_dla_rd_en   : (rd_en && (rd_sel == RSEL_C));
    wire [3:0]  dla_rd_addr = seq_busy ? seq_dla_rd_addr : rd_addr[3:0];

    wire        act_we    = seq_busy ? seq_act_we    : (host_w && (wr_sel == WSEL_ACT));
    wire [7:0]  act_waddr = seq_busy ? seq_act_waddr : wr_addr[7:0];
    wire [7:0]  act_wdata = seq_busy ? seq_act_wdata : wr_data;
    wire [7:0]  act_raddr = seq_busy ? seq_act_raddr : rd_addr[7:0];

    wire        img_we    = seq_busy ? seq_img_we    : (host_w && (wr_sel == WSEL_IMG));
    wire [9:0]  img_waddr = seq_busy ? seq_img_waddr : wr_addr;
    wire [7:0]  img_wdata = seq_busy ? seq_img_wdata : wr_data;
    wire [9:0]  img_raddr = seq_busy ? seq_img_raddr : rd_addr;

    // ------------------------------------------------------------------
    // The INT8 MAC engine (unchanged from the main-branch tapeout: 11 macros)
    // ------------------------------------------------------------------
    wire signed [23:0] dla_rd_data;
    wire               dla_wb_done;

    dla_engine_top #(
        .N            (4),
        .K            (256),
        .DATA_W       (8),
        .ACC_W        (24),
        .SRAM_LATENCY (1)
    ) u_dla (
        .clk     (clk),
        .rst_n   (rst_n),
        .start   (seq_dla_start),
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

    // ------------------------------------------------------------------
    // Activation and image SRAM banks (5 new macros)
    // ------------------------------------------------------------------
    wire [7:0] act_rdata, img_rdata;

    gan_act_buffer u_act (
        .clk     (clk),
        .wr_en   (act_we),
        .wr_addr (act_waddr),
        .wr_data (act_wdata),
        .rd_addr (act_raddr),
        .rd_data (act_rdata)
    );

    gan_img_buffer u_img (
        .clk     (clk),
        .wr_en   (img_we),
        .wr_addr (img_waddr),
        .wr_data (img_wdata),
        .rd_addr (img_raddr),
        .rd_data (img_rdata)
    );

    // ------------------------------------------------------------------
    // Post-processing (requant -> 9-segment PWL -> int8) and metrics
    // ------------------------------------------------------------------
    wire        pp_req, pp_skip, pp_vld, pp_sat_pre, pp_sat_out;
    wire signed [27:0] pp_acc;
    wire signed [7:0]  pp_bias, pp_q;
    wire signed [15:0] pp_pre, pp_act;

    gan_postproc u_pp (
        .clk        (clk),
        .rst_n      (rst_n),
        .req        (pp_req),
        .skip_quant (pp_skip),
        .acc        (pp_acc),
        .bias       (pp_bias),
        .ma         (cfg_ma),
        .mb         (cfg_mb),
        .s          (cfg_s),
        .mh         (cfg_mh),
        .sh         (cfg_sh),
        .func       (cfg_func),
        .pre_o      (pp_pre),
        .act_o      (pp_act),
        .q_o        (pp_q),
        .sat_pre_o  (pp_sat_pre),
        .sat_out_o  (pp_sat_out),
        .vld        (pp_vld)
    );

    wire        met_clr, met_score_vld, met_score_is_real, met_latch_loss;
    wire        met_ink_vld, met_sat_pre, met_sat_out, met_busy;
    wire [12:0] met_score_y;
    wire signed [15:0] met_logit;
    wire signed [7:0]  met_ink_pixel;
    wire signed [27:0] met_last_acc;
    wire signed [23:0] met_data;

    gan_metrics u_met (
        .clk           (clk),
        .rst_n         (rst_n),
        .clr           (met_clr),
        .score_vld     (met_score_vld),
        .score_y       (met_score_y),
        .score_is_real (met_score_is_real),
        .score_logit   (met_logit),
        .latch_loss    (met_latch_loss),
        .ink_vld       (met_ink_vld),
        .ink_pixel     (met_ink_pixel),
        .sat_pre       (met_sat_pre),
        .sat_out       (met_sat_out),
        .seq_busy      (seq_busy),
        .last_acc      (met_last_acc),
        .met_addr      (rd_addr[4:0]),
        .met_data      (met_data),
        .verdict       (verdict),
        .busy          (met_busy)
    );

    // ------------------------------------------------------------------
    // Sequencer
    // ------------------------------------------------------------------
    gan_sequencer u_seq (
        .clk         (clk),
        .rst_n       (rst_n),
        .exec_req    (exec_req),
        .exec_op     (exec_op),
        .exec_arg    (exec_arg),
        .busy        (seq_busy),

        .cfg_ma      (cfg_ma),
        .cfg_mb      (cfg_mb),
        .cfg_s       (cfg_s),
        .cfg_mh      (cfg_mh),
        .cfg_sh      (cfg_sh),
        .cfg_func    (cfg_func),
        .cfg_b0      (cfg_b0),
        .cfg_b1      (cfg_b1),
        .cfg_b2      (cfg_b2),
        .cfg_b3      (cfg_b3),
        .cfg_dst_ptr (cfg_dptr),
        .cfg_dst_sel (cfg_dsel),
        .cfg_nout    (cfg_nout),
        .dst_ptr_inc (dst_ptr_inc),

        .dla_start   (seq_dla_start),
        .dla_wr_en   (seq_dla_wr_en),
        .dla_wr_sel  (seq_dla_wr_sel),
        .dla_wr_addr (seq_dla_wr_addr),
        .dla_wr_data (seq_dla_wr_data),
        .dla_rd_en   (seq_dla_rd_en),
        .dla_rd_addr (seq_dla_rd_addr),
        .dla_rd_data (dla_rd_data),
        .dla_wb_done (dla_wb_done),

        .act_we      (seq_act_we),
        .act_waddr   (seq_act_waddr),
        .act_wdata   (seq_act_wdata),
        .act_raddr   (seq_act_raddr),
        .act_rdata   (act_rdata),

        .img_we      (seq_img_we),
        .img_waddr   (seq_img_waddr),
        .img_wdata   (seq_img_wdata),
        .img_raddr   (seq_img_raddr),
        .img_rdata   (img_rdata),

        .pp_req      (pp_req),
        .pp_skip     (pp_skip),
        .pp_acc      (pp_acc),
        .pp_bias     (pp_bias),
        .pp_vld      (pp_vld),
        .pp_pre      (pp_pre),
        .pp_act      (pp_act),
        .pp_q        (pp_q),
        .pp_sat_pre  (pp_sat_pre),
        .pp_sat_out  (pp_sat_out),

        .met_clr           (met_clr),
        .met_score_vld     (met_score_vld),
        .met_score_y       (met_score_y),
        .met_score_is_real (met_score_is_real),
        .met_logit         (met_logit),
        .met_latch_loss    (met_latch_loss),
        .met_ink_vld       (met_ink_vld),
        .met_ink_pixel     (met_ink_pixel),
        .met_sat_pre       (met_sat_pre),
        .met_sat_out       (met_sat_out),
        .met_last_acc      (met_last_acc),
        .met_busy          (met_busy)
    );

    assign busy = seq_busy;

    // ------------------------------------------------------------------
    // Host read mux
    // ------------------------------------------------------------------
    always @* begin
        case (rd_sel)
            RSEL_MET: rd_data = met_data;
            RSEL_IMG: rd_data = {{16{img_rdata[7]}}, img_rdata};
            RSEL_ACT: rd_data = {{16{act_rdata[7]}}, act_rdata};
            default:  rd_data = dla_rd_data;
        endcase
    end

endmodule
