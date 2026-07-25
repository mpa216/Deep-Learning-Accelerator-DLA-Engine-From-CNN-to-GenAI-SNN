`timescale 1ns / 1ps

// On-chip metric register file: the GAN losses plus the run statistics the host
// needs to plot a loss curve and judge quantisation health.
//
// The MATLAB reference (LSI_Contest_simple_gan_3x3_improved.m) logged
//     loss_D = -mean( ln y_real + ln(1 - y_fake) )
//     loss_G = -mean( ln y_fake )
// on the training host.  Here the chip evaluates the same two expressions itself,
// per sample, from the two sigmoid scores it produced -- gan_nlog does the logarithm.
// The host reads MET_* over the serial link and plots; nothing about the loss has to
// be recomputed off chip.
//
// Everything is a 24-bit read, matching the serial link's read payload width.
// Accumulators saturate rather than wrap, so a long sweep degrades gracefully.
module gan_metrics (
    input                     clk,
    input                     rst_n,

    input                     clr,           // OP_CLR_MET
    input                     score_vld,     // a discriminator score was produced
    input      [12:0]         score_y,       // Q4.12, 0..4096
    input                     score_is_real,
    input  signed [15:0]      score_logit,   // pre-sigmoid value
    input                     latch_loss,    // OP_LATCH_LOSS: fold y_real/y_fake in

    input                     ink_vld,       // a pixel was written to the image buffer
    input  signed [7:0]       ink_pixel,
    input                     sat_pre,
    input                     sat_out,
    input                     seq_busy,      // cycle counter enable
    input  signed [27:0]      last_acc,

    input      [4:0]          met_addr,
    output reg signed [23:0]  met_data,
    output                    verdict,       // y_fake > 0.5: the generator fooled D
    output                    busy           // loss pipeline in flight
);

`include "gan_defs.vh"

    localparam [23:0] SAT24 = 24'h7fffff;

    reg [23:0] y_fake, y_real, loss_g, loss_d;
    reg [23:0] acc_loss_g, acc_loss_d, acc_y_fake, acc_y_real;
    reg [23:0] n_samples, n_fooled, n_real_ok;
    reg [23:0] y_fake_min, y_fake_max;
    reg [23:0] ink, sat_pre_cnt, sat_out_cnt, cycles;
    reg signed [15:0] logit;
    reg signed [27:0] last_acc_r;

    // Saturating 24-bit add.
    function [23:0] sadd;
        input [23:0] a;
        input [23:0] b;
        reg   [24:0] s;
        begin
            s = {1'b0, a} + {1'b0, b};
            sadd = s[24] ? SAT24 : s[23:0];
        end
    endfunction

    // ---- BCE loss pipeline ---------------------------------------------------
    // Three sequential -ln() evaluations share one gan_nlog instance:
    //   loss_G = nlog(y_fake)
    //   loss_D = nlog(y_real) + nlog(1 - y_fake)
    localparam [2:0] L_IDLE = 3'd0, L_G = 3'd1, L_DR = 3'd2, L_DF = 3'd3, L_FIN = 3'd4;

    reg [2:0]  lstate;
    reg        nl_req;
    reg [12:0] nl_in;
    wire signed [23:0] nl_out;
    wire               nl_vld;
    reg  [23:0] loss_d_part;

    gan_nlog u_nlog (
        .clk   (clk),
        .rst_n (rst_n),
        .req   (nl_req),
        .y_q12 (nl_in),
        .nlog  (nl_out),
        .vld   (nl_vld)
    );

    assign busy    = (lstate != L_IDLE);
    assign verdict = (y_fake > 24'd2048);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            y_fake <= 24'd0; y_real <= 24'd0; loss_g <= 24'd0; loss_d <= 24'd0;
            acc_loss_g <= 24'd0; acc_loss_d <= 24'd0;
            acc_y_fake <= 24'd0; acc_y_real <= 24'd0;
            n_samples <= 24'd0; n_fooled <= 24'd0; n_real_ok <= 24'd0;
            y_fake_min <= 24'd4096; y_fake_max <= 24'd0;
            ink <= 24'd0; sat_pre_cnt <= 24'd0; sat_out_cnt <= 24'd0; cycles <= 24'd0;
            logit <= 16'sd0; last_acc_r <= 28'sd0;
            lstate <= L_IDLE; nl_req <= 1'b0; nl_in <= 13'd0; loss_d_part <= 24'd0;
        end else begin
            nl_req <= 1'b0;

            if (clr) begin
                y_fake <= 24'd0; y_real <= 24'd0; loss_g <= 24'd0; loss_d <= 24'd0;
                acc_loss_g <= 24'd0; acc_loss_d <= 24'd0;
                acc_y_fake <= 24'd0; acc_y_real <= 24'd0;
                n_samples <= 24'd0; n_fooled <= 24'd0; n_real_ok <= 24'd0;
                y_fake_min <= 24'd4096; y_fake_max <= 24'd0;
                ink <= 24'd0; sat_pre_cnt <= 24'd0; sat_out_cnt <= 24'd0;
                cycles <= 24'd0;
            end else begin
                if (seq_busy && (cycles != SAT24)) cycles <= cycles + 1'b1;
                if (sat_pre) sat_pre_cnt <= sadd(sat_pre_cnt, 24'd1);
                if (sat_out) sat_out_cnt <= sadd(sat_out_cnt, 24'd1);
                // Pixels are signed; gray level = pixel + 128.
                if (ink_vld) ink <= sadd(ink, {{16{ink_pixel[7]}}, ink_pixel} + 24'd128);

                if (score_vld) begin
                    logit      <= score_logit;
                    last_acc_r <= last_acc;
                    if (score_is_real) begin
                        y_real     <= {11'd0, score_y};
                        acc_y_real <= sadd(acc_y_real, {11'd0, score_y});
                        if (score_y > 13'd2048) n_real_ok <= sadd(n_real_ok, 24'd1);
                    end else begin
                        y_fake     <= {11'd0, score_y};
                        acc_y_fake <= sadd(acc_y_fake, {11'd0, score_y});
                        if (score_y > 13'd2048) n_fooled <= sadd(n_fooled, 24'd1);
                        if ({11'd0, score_y} < y_fake_min) y_fake_min <= {11'd0, score_y};
                        if ({11'd0, score_y} > y_fake_max) y_fake_max <= {11'd0, score_y};
                    end
                end
            end

            case (lstate)
                L_IDLE: if (latch_loss && !clr) begin
                    nl_in  <= y_fake[12:0];
                    nl_req <= 1'b1;
                    lstate <= L_G;
                end

                L_G: if (nl_vld) begin
                    loss_g     <= nl_out[23:0];
                    acc_loss_g <= sadd(acc_loss_g, nl_out[23:0]);
                    nl_in      <= y_real[12:0];
                    nl_req     <= 1'b1;
                    lstate     <= L_DR;
                end

                L_DR: if (nl_vld) begin
                    loss_d_part <= nl_out[23:0];
                    nl_in       <= 13'd4096 - y_fake[12:0];   // 1 - y_fake
                    nl_req      <= 1'b1;
                    lstate      <= L_DF;
                end

                L_DF: if (nl_vld) begin
                    loss_d     <= sadd(loss_d_part, nl_out[23:0]);
                    acc_loss_d <= sadd(acc_loss_d, sadd(loss_d_part, nl_out[23:0]));
                    lstate     <= L_FIN;
                end

                L_FIN: begin
                    n_samples <= sadd(n_samples, 24'd1);
                    lstate    <= L_IDLE;
                end

                default: lstate <= L_IDLE;
            endcase
        end
    end

    // ---- read mux ------------------------------------------------------------
    wire [23:0] status = {20'd0,
                          (sat_pre_cnt != 24'd0) || (sat_out_cnt != 24'd0),
                          (y_real > 24'd2048),
                          (y_fake > 24'd2048),
                          busy};

    always @* begin
        case (met_addr)
            MET_STATUS:     met_data = status;
            MET_Y_FAKE:     met_data = y_fake;
            MET_Y_REAL:     met_data = y_real;
            MET_LOSS_G:     met_data = loss_g;
            MET_LOSS_D:     met_data = loss_d;
            MET_ACC_LOSS_G: met_data = acc_loss_g;
            MET_ACC_LOSS_D: met_data = acc_loss_d;
            MET_N_SAMPLES:  met_data = n_samples;
            MET_N_FOOLED:   met_data = n_fooled;
            MET_N_REAL_OK:  met_data = n_real_ok;
            MET_Y_FAKE_MIN: met_data = y_fake_min;
            MET_Y_FAKE_MAX: met_data = y_fake_max;
            MET_ACC_Y_FAKE: met_data = acc_y_fake;
            MET_ACC_Y_REAL: met_data = acc_y_real;
            MET_INK:        met_data = ink;
            MET_SAT_PRE:    met_data = sat_pre_cnt;
            MET_SAT_OUT:    met_data = sat_out_cnt;
            MET_CYCLES:     met_data = cycles;
            MET_LOGIT:      met_data = {{8{logit[15]}}, logit};
            MET_LAST_ACC:   met_data = last_acc_r[23:0];
            default:        met_data = 24'd0;
        endcase
    end

endmodule
