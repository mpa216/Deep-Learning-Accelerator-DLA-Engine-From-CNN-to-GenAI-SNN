`timescale 1ns / 1ps

// FP16 multiply / FP32 accumulate PE -- STUDY ONLY, NOT PART OF THE TAPEOUT.
//
// Deliberately kept OUTSIDE rtl/ so that no `iverilog rtl/*.v` or LibreLane glob can
// ever pull it into a build.  Its only purpose is to put a measured number against the
// reviewer's question "why INT8 and not FP16?": scripts/quant_tradeoff_study.py
// synthesises 16 of these against the same 3.3 V standard-cell library used for the
// tapeout and compares the cell area with the real `dla_pe_array`.
//
// It is the direct FP counterpart of rtl/dla_pe.v: one multiply and one accumulate per
// enabled cycle, with a synchronous clear.  INT8 accumulates into 24 fixed-point bits;
// this accumulates into IEEE-754 binary32, which is what an FP16 array would have to do
// to hold a 256-deep dot product without losing the smallest terms.
//
// SIMPLIFICATIONS, all of which make this an UNDER-estimate of a production FP16 MAC:
//   * subnormal inputs and results are flushed to zero
//   * no NaN / Inf handling at all -- no special-case decode, no exception flags
//   * exponent underflow flushes to zero, overflow saturates silently
//   * single-cycle combinational datapath, so no pipeline registers are counted
// A real FP16 unit needs all of the above.  The area reported is therefore a floor, and
// the conclusion it supports ("FP16 costs several times INT8") only gets stronger if the
// missing logic is added.
//
// Verified bit-exact against a Python model of this exact algorithm by
// study/fp16_mac_tb.sv; that model's fidelity to true IEEE arithmetic is separately
// characterised in the same testbench's report.
module fp16_mac (
    input             clk,
    input             rst_n,
    input             clear,
    input             en,
    input      [15:0] a_in,      // IEEE-754 binary16
    input      [15:0] b_in,      // IEEE-754 binary16
    output reg [31:0] acc_out    // IEEE-754 binary32
);

    // ---- unpack the two FP16 operands ------------------------------------
    wire        sa = a_in[15];
    wire [4:0]  ea = a_in[14:10];
    wire [9:0]  ma = a_in[9:0];
    wire        sb = b_in[15];
    wire [4:0]  eb = b_in[14:10];
    wire [9:0]  mb = b_in[9:0];

    wire a_zero = (ea == 5'd0);            // flush-to-zero on subnormals
    wire b_zero = (eb == 5'd0);
    wire p_zero = a_zero | b_zero;

    wire [10:0] sig_a = {1'b1, ma};
    wire [10:0] sig_b = {1'b1, mb};

    // ---- the multiply: 11 x 11 -> 22 bits (2 integer + 20 fraction) ------
    wire [21:0] pm_raw = sig_a * sig_b;
    wire        ps     = sa ^ sb;

    // Exponent in binary32 bias: (ea-15) + (eb-15) + 127 = ea + eb + 97
    wire signed [9:0] pe_base = $signed({1'b0, ea}) + $signed({1'b0, eb}) + 10'sd97;

    // Normalise: pm_raw[21] set means the product landed in [2,4).
    wire [20:0]       p_sig = pm_raw[21] ? pm_raw[21:1] : pm_raw[20:0];
    wire signed [9:0] p_exp = pm_raw[21] ? pe_base + 10'sd1 : pe_base;

    // ---- unpack the accumulator ------------------------------------------
    wire        sc = acc_out[31];
    wire [7:0]  ec = acc_out[30:23];
    wire [22:0] mc = acc_out[22:0];
    wire        c_zero = (ec == 8'd0);
    wire [23:0] sig_c  = {1'b1, mc};

    // ---- align: both significands with the leading 1 at bit 47 -----------
    wire [47:0] c_ext = {sig_c, 24'd0};
    wire [47:0] p_ext = {p_sig, 27'd0};

    wire signed [9:0] c_exp = $signed({2'b00, ec});
    wire signed [9:0] ediff = p_exp - c_exp;
    wire        p_bigger = (ediff > 0);
    wire [9:0]  shamt_r  = p_bigger ? ediff[9:0] : (-ediff);
    wire [5:0]  shamt    = (shamt_r > 10'd48) ? 6'd48 : shamt_r[5:0];

    wire [47:0] hi_ext   = p_bigger ? p_ext : c_ext;
    wire [47:0] lo_ext = p_bigger ? c_ext : p_ext;
    wire        hi_s = p_bigger ? ps : sc;
    wire        lo_s = p_bigger ? sc : ps;
    wire signed [9:0] res_exp0 = p_bigger ? p_exp : c_exp;

    wire [47:0] lo_al = lo_ext >> shamt;

    // ---- add or subtract magnitudes --------------------------------------
    // hi_ext holds the larger EXPONENT, which is not the same as the larger magnitude:
    // when the exponents are equal the shift is zero and either side can be bigger, so
    // the difference must be taken in magnitude order or it wraps.
    wire same_sign = (hi_s == lo_s);
    wire        lo_gt   = (lo_al > hi_ext);
    wire [48:0] sum_add = {1'b0, hi_ext} + {1'b0, lo_al};
    wire [48:0] sum_sub = lo_gt ? ({1'b0, lo_al} - {1'b0, hi_ext})
                                : ({1'b0, hi_ext} - {1'b0, lo_al});
    wire [48:0] sum_raw = same_sign ? sum_add : sum_sub;
    wire        res_sign = same_sign ? hi_s : (lo_gt ? lo_s : hi_s);

    // ---- normalise -------------------------------------------------------
    integer i;
    reg [5:0]  lz;
    always @* begin                       // leading-zero count over sum_raw[47:0]
        lz = 6'd48;
        for (i = 47; i >= 0; i = i - 1)
            if (lz == 6'd48 && sum_raw[i]) lz = 6'd47 - i[5:0];
    end

    wire [48:0] norm = sum_raw[48] ? (sum_raw >> 1) : (sum_raw << lz);
    wire signed [9:0] norm_exp = sum_raw[48] ? (res_exp0 + 10'sd1)
                                             : (res_exp0 - $signed({4'd0, lz}));

    // ---- round to nearest, ties to even ----------------------------------
    wire [23:0] sig_r  = norm[47:24];
    wire        rbit   = norm[23];
    wire        sticky = |norm[22:0];
    wire        round_up = rbit & (sticky | sig_r[0]);
    wire [24:0] sig_rnd = {1'b0, sig_r} + {24'd0, round_up};

    wire [23:0] sig_fin = sig_rnd[24] ? sig_rnd[24:1] : sig_rnd[23:0];
    wire signed [9:0] exp_fin = sig_rnd[24] ? norm_exp + 10'sd1 : norm_exp;

    // ---- assemble --------------------------------------------------------
    wire sum_is_zero = (sum_raw[47:0] == 48'd0);
    wire underflow   = (exp_fin <= 10'sd0);
    wire overflow    = (exp_fin >= 10'sd255);

    wire [31:0] packed_result =
        (sum_is_zero | underflow) ? 32'd0 :
        overflow                  ? {res_sign, 8'hFE, 23'h7FFFFF} :
                                    {res_sign, exp_fin[7:0], sig_fin[22:0]};

    // Product or accumulator being zero short-circuits the adder entirely.
    wire [31:0] p_as_fp32 =
        (p_exp <= 10'sd0)   ? 32'd0 :
        (p_exp >= 10'sd255) ? {ps, 8'hFE, 23'h7FFFFF} :
                              {ps, p_exp[7:0], p_sig[19:0], 3'd0};

    wire [31:0] next_acc = p_zero ? acc_out
                         : c_zero ? p_as_fp32
                                  : packed_result;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)     acc_out <= 32'd0;
        else if (clear) acc_out <= 32'd0;
        else if (en)    acc_out <= next_acc;
    end

endmodule


// N x N grid of FP16 MACs, the structural counterpart of rtl/dla_pe_array.v.
module fp16_mac_array #(
    parameter N = 4
) (
    input                    clk,
    input                    rst_n,
    input                    clear,
    input                    en,
    input  [(N*16)-1:0]      a_bus,
    input  [(N*16)-1:0]      b_bus,
    output [(N*N*32)-1:0]    c_bus
);
    genvar i, j;
    generate
        for (i = 0; i < N; i = i + 1) begin : ROW
            for (j = 0; j < N; j = j + 1) begin : COL
                fp16_mac u_mac (
                    .clk(clk), .rst_n(rst_n), .clear(clear), .en(en),
                    .a_in(a_bus[(i*16) +: 16]),
                    .b_in(b_bus[(j*16) +: 16]),
                    .acc_out(c_bus[(((i*N)+j)*32) +: 32])
                );
            end
        end
    endgenerate
endmodule
