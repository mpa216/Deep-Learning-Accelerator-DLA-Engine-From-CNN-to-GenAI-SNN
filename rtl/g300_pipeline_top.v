`timescale 1ns / 1ps

// G300 generator MLP (64 -> 256 -> 256 -> 784, ReLU/ReLU/Tanh) running on the DLA engine.
//
// The dense layers are evaluated as int8 matrix-vector products tiled onto the native
// 4x4 DLA array (N=4, K=256): each `start` computes 4 output neurons (their weight rows
// in the A buffer, the shared input activation in B column 0, results read from C[i][0]).
// Bias add, requantization, ReLU and the Q20 tanh LUT are handled here around the DLA.
//
// Requant constants and the int8 latent/golden come from scripts/gen_g300_int8_assets.py.
module g300_pipeline_top #(
    parameter integer FP_SHIFT = 20,
    parameter integer WEIGHT_W = 8,            // int8 weights now
    parameter integer ACC_W = 24,              // DLA accumulator width
    parameter integer LUT_SHIFT = 8,
    parameter string W0_MEMH = "weights_vh/mnist_gan_mlp/G300_0_weight.memh",
    parameter string B0_MEMH = "weights_vh/mnist_gan_mlp/G300_0_bias.memh",
    parameter string W2_MEMH = "weights_vh/mnist_gan_mlp/G300_2_weight.memh",
    parameter string B2_MEMH = "weights_vh/mnist_gan_mlp/G300_2_bias.memh",
    parameter string W4_MEMH = "weights_vh/mnist_gan_mlp/G300_4_weight.memh",
    parameter string B4_MEMH = "weights_vh/mnist_gan_mlp/G300_4_bias.memh",
    parameter string ZQ_MEMH = "tb/data/g300_int8/g300_zq.memh",
    parameter string TANH_LUT_MEMH = "tb/data/g300_fp/g300_tanh_lut_fp.memh"
) (
    input                           clk,
    input                           rst_n,
    input                           start,

    input                           rd_en,
    input  [9:0]                    rd_addr,
    output reg signed [7:0]         rd_data,

    output reg                      done,
    output                          busy
);

    // ---- Generated requant constants (G300_MA0, G300_MB0, ... , shifts). ----
    `include "g300_quant_params.vh"

    localparam integer L0_OUT = 256, L0_IN = 64;
    localparam integer L2_OUT = 256, L2_IN = 256;
    localparam integer L4_OUT = 784, L4_IN = 256;

    localparam integer N = 4;
    localparam integer K = 256;
    localparam integer AB_ADDR_W = 10;         // clog2(N*K) = clog2(1024)
    localparam integer C_ADDR_W  = 4;          // clog2(N*N) = clog2(16)

    localparam integer TANH_MAX_FP = (4 <<< FP_SHIFT);
    localparam integer LUT_SIZE = ((TANH_MAX_FP * 2) >>> LUT_SHIFT) + 1;

    // ---- Parameter/weight memories (simulation reg arrays loaded via $readmemh). ----
    reg signed [WEIGHT_W-1:0] w0 [0:(L0_OUT*L0_IN)-1];
    reg signed [WEIGHT_W-1:0] w2 [0:(L2_OUT*L2_IN)-1];
    reg signed [WEIGHT_W-1:0] w4 [0:(L4_OUT*L4_IN)-1];
    reg signed [WEIGHT_W-1:0] b0 [0:L0_OUT-1];
    reg signed [WEIGHT_W-1:0] b2 [0:L2_OUT-1];
    reg signed [WEIGHT_W-1:0] b4 [0:L4_OUT-1];
    reg signed [7:0]          zq [0:L0_IN-1];

    reg signed [WEIGHT_W-1:0] h0q [0:L0_OUT-1];   // int8 activations [0,127]
    reg signed [WEIGHT_W-1:0] h2q [0:L2_OUT-1];
    reg signed [7:0]          pix_mem [0:L4_OUT-1];

    reg signed [ACC_W-1:0] tanh_lut [0:LUT_SIZE-1];

    initial begin
        $readmemh(W0_MEMH, w0);
        $readmemh(B0_MEMH, b0);
        $readmemh(W2_MEMH, w2);
        $readmemh(B2_MEMH, b2);
        $readmemh(W4_MEMH, w4);
        $readmemh(B4_MEMH, b4);
        $readmemh(ZQ_MEMH, zq);
        $readmemh(TANH_LUT_MEMH, tanh_lut);
    end

    // ---- DLA engine instance (native 4x4, K=256). ----
    reg                       dla_start;
    reg                       dla_wr_en;
    reg                       dla_wr_sel;
    reg  [AB_ADDR_W-1:0]      dla_wr_addr;
    reg  signed [7:0]         dla_wr_data;
    wire signed [ACC_W-1:0]   dla_rd_data;
    wire                      dla_wb_done;
    wire                      dla_done;
    wire                      dla_busy;

    reg  [1:0]                rcnt;             // C read pointer (0..3)
    wire [C_ADDR_W-1:0]       dla_rd_addr;
    wire                      dla_rd_en;

`ifdef GLS
    // Post-layout GLS: the hardened netlist (as3v3_k256_d63) carries no
    // parameters -- its baked configuration (N=4/K=256/DATA_W=8/ACC_W=24/
    // SRAM_LATENCY=1) is exactly what this module assumes, so instantiate bare.
    dla_engine_top u_dla (
`else
    dla_engine_top #(
        .N(N),
        .K(K),
        .DATA_W(8),
        .ACC_W(ACC_W),
        .SRAM_LATENCY(1)
    ) u_dla (
`endif
        .clk(clk),
        .rst_n(rst_n),
        .start(dla_start),
        .wr_en(dla_wr_en),
        .wr_sel(dla_wr_sel),
        .wr_addr(dla_wr_addr),
        .wr_data(dla_wr_data),
        .rd_en(dla_rd_en),
        .rd_addr(dla_rd_addr),
        .rd_data(dla_rd_data),
        .wb_done(dla_wb_done),
        .done(dla_done),
        .busy(dla_busy)
    );

    // ---- Control FSM. ----
    localparam [3:0] S_IDLE       = 4'd0;
    localparam [3:0] S_LAYER_INIT = 4'd1;
    localparam [3:0] S_LOADB      = 4'd2;
    localparam [3:0] S_LOADA      = 4'd3;
    localparam [3:0] S_RUN_START  = 4'd4;
    localparam [3:0] S_RUN_WAIT   = 4'd5;
    localparam [3:0] S_READ_SET   = 4'd6;
    localparam [3:0] S_READ_GET   = 4'd7;
    localparam [3:0] S_REQ        = 4'd8;
    localparam [3:0] S_TILE_NEXT  = 4'd9;
    localparam [3:0] S_DONE       = 4'd10;

    reg [3:0]  state;
    reg [1:0]  layer;            // 0=L0, 1=L2, 2=L4
    reg [8:0]  in_dim;
    reg [9:0]  num_tiles;
    reg [9:0]  tile;
    reg [8:0]  k_cnt;
    reg [1:0]  row_cnt;
    reg signed [ACC_W-1:0] accv [0:3];

    assign busy        = (state != S_IDLE) && (state != S_DONE);
    assign dla_rd_en   = (state == S_READ_SET) || (state == S_READ_GET);
    assign dla_rd_addr = {{(C_ADDR_W-2){1'b0}}, rcnt, 2'b00}; // flat C addr = rcnt*N (col 0)

    // Helpers reused for the requant math.
    integer r;
    reg signed [63:0] t_acc;
    reg signed [63:0] pre_q20;
    reg [15:0]        lut_idx;
    reg signed [ACC_W-1:0] tanh_val;
    reg signed [63:0] tmp_pix;
    reg signed [63:0] pix_val;
    reg [9:0]         grow;
    reg signed [7:0]  inb;
    reg signed [WEIGHT_W-1:0] wsel;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state      <= S_IDLE;
            done       <= 1'b0;
            dla_start  <= 1'b0;
            dla_wr_en  <= 1'b0;
            dla_wr_sel <= 1'b0;
            dla_wr_addr<= {AB_ADDR_W{1'b0}};
            dla_wr_data<= 8'sd0;
            layer      <= 2'd0;
            tile       <= 10'd0;
            k_cnt      <= 9'd0;
            row_cnt    <= 2'd0;
            rcnt       <= 2'd0;
        end else begin
            case (state)
                S_IDLE: begin
                    done <= 1'b0;
                    if (start) begin
                        layer <= 2'd0;
                        state <= S_LAYER_INIT;
                    end
                end

                S_LAYER_INIT: begin
                    tile  <= 10'd0;
                    k_cnt <= 9'd0;
                    case (layer)
                        2'd0: begin in_dim <= L0_IN[8:0]; num_tiles <= (L0_OUT/N); end
                        2'd1: begin in_dim <= L2_IN[8:0]; num_tiles <= (L2_OUT/N); end
                        default: begin in_dim <= L4_IN[8:0]; num_tiles <= (L4_OUT/N); end
                    endcase
                    state <= S_LOADB;
                end

                // Load the shared input activation vector into B column 0 (addr = k*N).
                // Always write the full K depth, zero-padding past in_dim (the embedded
                // behavioral SRAM does not zero-initialize, so unused taps must be cleared).
                S_LOADB: begin
                    if (k_cnt < in_dim) begin
                        case (layer)
                            2'd0:    inb = zq[k_cnt[5:0]];
                            2'd1:    inb = h0q[k_cnt[7:0]];
                            default: inb = h2q[k_cnt[7:0]];
                        endcase
                    end else begin
                        inb = 8'sd0;
                    end
                    dla_wr_en   <= 1'b1;
                    dla_wr_sel  <= 1'b1;
                    dla_wr_addr <= {k_cnt, 2'b00};   // k*N (N=4)
                    dla_wr_data <= inb;
                    if (k_cnt == (K-1)) begin
                        k_cnt   <= 9'd0;
                        row_cnt <= 2'd0;
                        state   <= S_LOADA;
                    end else begin
                        k_cnt <= k_cnt + 1'b1;
                    end
                end

                // Load 4 weight rows of the current tile into the A buffer (full K, zero-padded).
                S_LOADA: begin
                    grow = {tile[7:0], 2'b00} | row_cnt; // tile*4 + row_cnt
                    if (k_cnt < in_dim) begin
                        case (layer)
                            2'd0:    wsel = w0[(grow * L0_IN) + k_cnt[5:0]];
                            2'd1:    wsel = w2[(grow * L2_IN) + k_cnt[7:0]];
                            default: wsel = w4[(grow * L4_IN) + k_cnt[7:0]];
                        endcase
                    end else begin
                        wsel = 8'sd0;
                    end
                    dla_wr_en   <= 1'b1;
                    dla_wr_sel  <= 1'b0;
                    dla_wr_addr <= {row_cnt, k_cnt[7:0]}; // row*K + k (K=256)
                    dla_wr_data <= wsel;
                    if (k_cnt == (K-1)) begin
                        k_cnt <= 9'd0;
                        if (row_cnt == (N-1)) begin
                            // Keep wr_en asserted so this final write lands;
                            // S_RUN_START deasserts it next cycle.
                            state <= S_RUN_START;
                        end else begin
                            row_cnt <= row_cnt + 1'b1;
                        end
                    end else begin
                        k_cnt <= k_cnt + 1'b1;
                    end
                end

                S_RUN_START: begin
                    dla_wr_en <= 1'b0;
                    dla_start <= 1'b1;        // clears dla_wb_done in the engine
                    state     <= S_RUN_WAIT;
                end

                S_RUN_WAIT: begin
                    if (dla_wb_done) begin
                        dla_start <= 1'b0;
                        rcnt      <= 2'd0;
                        state     <= S_READ_SET;
                    end
                end

                // Read C[rcnt][0] (1-cycle SRAM latency: address presented here, captured next).
                S_READ_SET: begin
                    state <= S_READ_GET;
                end

                S_READ_GET: begin
                    accv[rcnt] <= dla_rd_data;
                    if (rcnt == (N-1)) begin
                        state <= S_REQ;
                    end else begin
                        rcnt  <= rcnt + 1'b1;
                        state <= S_READ_SET;
                    end
                end

                // Requantize the 4 accumulators -> activations (ReLU) or pixels (tanh).
                S_REQ: begin
                    for (r = 0; r < N; r = r + 1) begin
                        grow = {tile[7:0], 2'b00} | r[1:0];
                        if (layer == 2'd0) begin
                            t_acc = accv[r] * G300_MA0 + b0[grow] * G300_MB0;
                            if (t_acc < 0) t_acc = 64'sd0;
                            t_acc = (t_acc + (64'sd1 <<< (G300_REQ_SHIFT-1))) >>> G300_REQ_SHIFT;
                            if (t_acc > 64'sd127) t_acc = 64'sd127;
                            h0q[grow] <= t_acc[7:0];
                        end else if (layer == 2'd1) begin
                            t_acc = accv[r] * G300_MA2 + b2[grow] * G300_MB2;
                            if (t_acc < 0) t_acc = 64'sd0;
                            t_acc = (t_acc + (64'sd1 <<< (G300_REQ_SHIFT-1))) >>> G300_REQ_SHIFT;
                            if (t_acc > 64'sd127) t_acc = 64'sd127;
                            h2q[grow] <= t_acc[7:0];
                        end else begin
                            pre_q20 = accv[r] * G300_MW4 + b4[grow] * G300_MB4;
                            pre_q20 = (pre_q20 + (64'sd1 <<< (G300_REQ_SHIFT_L4-1)))
                                          >>> G300_REQ_SHIFT_L4;
                            if (pre_q20 > TANH_MAX_FP)      pre_q20 = TANH_MAX_FP;
                            else if (pre_q20 < -TANH_MAX_FP) pre_q20 = -TANH_MAX_FP;
                            lut_idx  = (pre_q20 + TANH_MAX_FP) >>> LUT_SHIFT;
                            tanh_val = tanh_lut[lut_idx];
                            tmp_pix  = (tanh_val + (64'sd1 <<< FP_SHIFT)) * 64'sd255;
                            pix_val  = (tmp_pix + (64'sd1 <<< FP_SHIFT)) >>> (FP_SHIFT + 1);
                            if (pix_val < 0)        pix_val = 64'sd0;
                            else if (pix_val > 255) pix_val = 64'sd255;
                            pix_mem[grow] <= pix_val[7:0] - 8'sd128;
                        end
                    end
                    state <= S_TILE_NEXT;
                end

                S_TILE_NEXT: begin
                    if (tile == (num_tiles - 1)) begin
                        if (layer == 2'd2) begin
                            done  <= 1'b1;
                            state <= S_DONE;
                        end else begin
                            layer <= layer + 1'b1;
                            state <= S_LAYER_INIT;
                        end
                    end else begin
                        tile    <= tile + 1'b1;
                        k_cnt   <= 9'd0;
                        row_cnt <= 2'd0;
                        state   <= S_LOADA;   // B already loaded for this layer
                    end
                end

                S_DONE: begin
                    if (!start) begin
                        done  <= 1'b0;
                        state <= S_IDLE;
                    end
                end

                default: state <= S_IDLE;
            endcase
        end
    end

    // Output readback: host reads the 784 generated pixels.
    always @* begin
        rd_data = 8'sd0;
        if (rd_en) begin
            rd_data = pix_mem[rd_addr];
        end
    end

endmodule
