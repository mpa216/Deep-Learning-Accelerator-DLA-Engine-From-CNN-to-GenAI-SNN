`timescale 1ns / 1ps

// 9-segment piecewise-linear activation unit, Q4.12.
//
// Ported from UAS_VLSI_Kelompok05_modified/UAS_VLSI/pla_activations.v: an
// 8-comparison threshold ladder picks one of nine (m, c) pairs and the output is
//
//     y = clamp( ((m * x) >>> 12) + c )
//
// The tanh and sigmoid coefficients are that file's values verbatim.  The same
// datapath also covers ReLU, LeakyReLU(0.2), identity and a log2-mantissa fit, so
// the whole chip needs exactly one activation datapath.  The reference kept a
// separate always-block (and multiplier) per function; folding them into one
// func-selected table is what makes six activations affordable in silicon.
//
// Two differences from the reference, both deliberate:
//   * one shared multiplier instead of one per function;
//   * the output is clamped to each function's mathematical range.  The reference's
//     outer sigmoid segments have a non-zero slope, so it drifts outside [0, 1] for
//     |x| > 8 (e.g. y = -38 at x = -32768).  A negative "probability" would corrupt
//     the BCE loss in gan_nlog, so tanh clamps to +-1.0 and sigmoid/log2 to [0, 1].
//
// Latency: 2 clocks from `req` to `vld`, matching the reference's 2-stage pipeline.
module gan_pwl_act (
    input                     clk,
    input                     rst_n,
    input                     req,        // 1-cycle request pulse
    input      [2:0]          func,       // GF_* from gan_defs.vh
    input  signed [15:0]      x,          // Q4.12
    output reg signed [15:0]  y,          // Q4.12
    output reg                vld         // 1-cycle valid pulse
);

`include "gan_defs.vh"
`include "gan_pwl_tables.vh"

    // ---- threshold ladder select --------------------------------------------
    // tanh/sigmoid share one ladder; the homogeneous functions split at zero;
    // log2 has its own ladder across the mantissa range [1.0, 2.0).
    wire use_tanh_thr = (func == GF_TANH) || (func == GF_SIGMOID);
    wire use_log_thr  = (func == GF_LOG2M);

    // Every branch assigns all eight entries explicitly.  A `for` loop over an
    // `integer` here would leave the loop variable itself unassigned in the other two
    // branches, and Yosys duly infers a latch on it (harmless, but it shows up in the
    // flow's latch report and in the tapeout netlist).
    reg signed [15:0] thr [0:7];
    always @* begin
        if (use_tanh_thr) begin
            thr[0] = PWL_THR_TANH_0; thr[1] = PWL_THR_TANH_1;
            thr[2] = PWL_THR_TANH_2; thr[3] = PWL_THR_TANH_3;
            thr[4] = PWL_THR_TANH_4; thr[5] = PWL_THR_TANH_5;
            thr[6] = PWL_THR_TANH_6; thr[7] = PWL_THR_TANH_7;
        end else if (use_log_thr) begin
            thr[0] = PWL_THR_LOG2M_0; thr[1] = PWL_THR_LOG2M_1;
            thr[2] = PWL_THR_LOG2M_2; thr[3] = PWL_THR_LOG2M_3;
            thr[4] = PWL_THR_LOG2M_4; thr[5] = PWL_THR_LOG2M_5;
            thr[6] = PWL_THR_LOG2M_6; thr[7] = PWL_THR_LOG2M_7;
        end else begin
            // RELU / LRELU / IDENT: a single split at zero.
            thr[0] = 16'sd0; thr[1] = 16'sd0; thr[2] = 16'sd0; thr[3] = 16'sd0;
            thr[4] = 16'sd0; thr[5] = 16'sd0; thr[6] = 16'sd0; thr[7] = 16'sd0;
        end
    end

    reg [3:0] seg;
    always @* begin
        if      (x < thr[0]) seg = 4'd0;
        else if (x < thr[1]) seg = 4'd1;
        else if (x < thr[2]) seg = 4'd2;
        else if (x < thr[3]) seg = 4'd3;
        else if (x < thr[4]) seg = 4'd4;
        else if (x < thr[5]) seg = 4'd5;
        else if (x < thr[6]) seg = 4'd6;
        else if (x < thr[7]) seg = 4'd7;
        else                 seg = 4'd8;
    end

    // ---- coefficient lookup --------------------------------------------------
    reg signed [15:0] m_sel, c_sel;
    always @* begin
        case (func)
        GF_TANH: case (seg)
            4'd0: begin m_sel = PWL_M_TANH_0; c_sel = PWL_C_TANH_0; end
            4'd1: begin m_sel = PWL_M_TANH_1; c_sel = PWL_C_TANH_1; end
            4'd2: begin m_sel = PWL_M_TANH_2; c_sel = PWL_C_TANH_2; end
            4'd3: begin m_sel = PWL_M_TANH_3; c_sel = PWL_C_TANH_3; end
            4'd4: begin m_sel = PWL_M_TANH_4; c_sel = PWL_C_TANH_4; end
            4'd5: begin m_sel = PWL_M_TANH_5; c_sel = PWL_C_TANH_5; end
            4'd6: begin m_sel = PWL_M_TANH_6; c_sel = PWL_C_TANH_6; end
            4'd7: begin m_sel = PWL_M_TANH_7; c_sel = PWL_C_TANH_7; end
            default: begin m_sel = PWL_M_TANH_8; c_sel = PWL_C_TANH_8; end
        endcase
        GF_SIGMOID: case (seg)
            4'd0: begin m_sel = PWL_M_SIGMOID_0; c_sel = PWL_C_SIGMOID_0; end
            4'd1: begin m_sel = PWL_M_SIGMOID_1; c_sel = PWL_C_SIGMOID_1; end
            4'd2: begin m_sel = PWL_M_SIGMOID_2; c_sel = PWL_C_SIGMOID_2; end
            4'd3: begin m_sel = PWL_M_SIGMOID_3; c_sel = PWL_C_SIGMOID_3; end
            4'd4: begin m_sel = PWL_M_SIGMOID_4; c_sel = PWL_C_SIGMOID_4; end
            4'd5: begin m_sel = PWL_M_SIGMOID_5; c_sel = PWL_C_SIGMOID_5; end
            4'd6: begin m_sel = PWL_M_SIGMOID_6; c_sel = PWL_C_SIGMOID_6; end
            4'd7: begin m_sel = PWL_M_SIGMOID_7; c_sel = PWL_C_SIGMOID_7; end
            default: begin m_sel = PWL_M_SIGMOID_8; c_sel = PWL_C_SIGMOID_8; end
        endcase
        GF_RELU: begin
            m_sel = (seg == 4'd0) ? PWL_M_RELU_0 : PWL_M_RELU_8;
            c_sel = (seg == 4'd0) ? PWL_C_RELU_0 : PWL_C_RELU_8;
        end
        GF_LRELU: begin
            m_sel = (seg == 4'd0) ? PWL_M_LRELU_0 : PWL_M_LRELU_8;
            c_sel = (seg == 4'd0) ? PWL_C_LRELU_0 : PWL_C_LRELU_8;
        end
        GF_LOG2M: case (seg)
            4'd0: begin m_sel = PWL_M_LOG2M_0; c_sel = PWL_C_LOG2M_0; end
            4'd1: begin m_sel = PWL_M_LOG2M_1; c_sel = PWL_C_LOG2M_1; end
            4'd2: begin m_sel = PWL_M_LOG2M_2; c_sel = PWL_C_LOG2M_2; end
            4'd3: begin m_sel = PWL_M_LOG2M_3; c_sel = PWL_C_LOG2M_3; end
            4'd4: begin m_sel = PWL_M_LOG2M_4; c_sel = PWL_C_LOG2M_4; end
            4'd5: begin m_sel = PWL_M_LOG2M_5; c_sel = PWL_C_LOG2M_5; end
            4'd6: begin m_sel = PWL_M_LOG2M_6; c_sel = PWL_C_LOG2M_6; end
            4'd7: begin m_sel = PWL_M_LOG2M_7; c_sel = PWL_C_LOG2M_7; end
            default: begin m_sel = PWL_M_LOG2M_8; c_sel = PWL_C_LOG2M_8; end
        endcase
        default: begin       // GF_IDENT
            m_sel = PWL_M_IDENT_0;
            c_sel = PWL_C_IDENT_0;
        end
        endcase
    end

    // ---- per-function output clamp ------------------------------------------
    reg signed [15:0] lo_sel, hi_sel;
    always @* begin
        case (func)
            GF_TANH:               begin lo_sel = -GAN_Q_ONE; hi_sel = GAN_Q_ONE;  end
            GF_SIGMOID, GF_LOG2M:  begin lo_sel =  16'sd0;    hi_sel = GAN_Q_ONE;  end
            default:               begin lo_sel = -16'sd32768; hi_sel = 16'sd32767; end
        endcase
    end

    // ---- 2-stage pipeline ----------------------------------------------------
    reg signed [15:0] x_d, m_d, c_d, lo_d, hi_d;
    reg               s1_vld;
    // Explicit sign extension on the 16-bit operands: the arithmetic is 32-bit so
    // that a saturating result is detected before it is truncated.
    wire signed [31:0] prod = m_d * x_d;
    wire signed [31:0] c_ext  = {{16{c_d[15]}},  c_d};
    wire signed [31:0] lo_ext = {{16{lo_d[15]}}, lo_d};
    wire signed [31:0] hi_ext = {{16{hi_d[15]}}, hi_d};
    wire signed [31:0] sum  = (prod >>> GAN_Q_FRAC) + c_ext;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            x_d <= 16'sd0; m_d <= 16'sd0; c_d <= 16'sd0;
            lo_d <= 16'sd0; hi_d <= 16'sd0;
            s1_vld <= 1'b0; vld <= 1'b0; y <= 16'sd0;
        end else begin
            s1_vld <= req;
            if (req) begin
                x_d  <= x;
                m_d  <= m_sel;
                c_d  <= c_sel;
                lo_d <= lo_sel;
                hi_d <= hi_sel;
            end

            vld <= s1_vld;
            if (s1_vld) begin
                if      (sum < lo_ext) y <= lo_d;
                else if (sum > hi_ext) y <= hi_d;
                else                   y <= sum[15:0];
            end
        end
    end

endmodule
