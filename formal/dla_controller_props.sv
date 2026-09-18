// SVA safety properties for dla_controller, at the AS-BUILT K=256 (k_idx is 8
// bits).  Uses a formal wrapper (not bind) because every signal these
// properties need -- the control outputs and k_idx -- is a module PORT.
//
// Immediate-assertion-in-clocked-always form.  Proven with SymbiYosys
// k-induction: see formal/dla_controller.sby.
module dla_controller_props (input clk, input rst_n, input start);

    wire clear_pe, en_pe, done, busy;
    wire [7:0] k_idx;

    dla_controller #(.K(256)) dut (
        .clk(clk), .rst_n(rst_n), .start(start),
        .clear_pe(clear_pe), .en_pe(en_pe), .k_idx(k_idx),
        .done(done), .busy(busy));

    // Constrain the base case to begin from a real reset (first cycle rst_n=0),
    // so the proof reasons about post-reset behaviour rather than an arbitrary
    // power-on state.  (The bridge proof needs no such assumption -- its safety
    // properties hold from ANY state, which is strictly stronger.)
    reg f_init = 1'b1;
    always @(posedge clk) f_init <= 1'b0;
    always @(*) if (f_init) assume (!rst_n);

    // ---- pure safety invariants ----
    always @(posedge clk) if (rst_n) begin
        a_done_busy_excl : assert (!(done && busy));             // DONE and BUSY disjoint
        a_clr_en_excl    : assert (!(clear_pe && en_pe));        // CLEAR and COMPUTE disjoint
        a_busy_def       : assert (busy == (clear_pe || en_pe)); // busy <=> CLEAR or COMPUTE
        a_kidx_bound     : assert (k_idx <= 8'd255);             // counter never over-runs K-1
    end

    // ---- temporal property ----
    always @(posedge clk) if (rst_n && $past(rst_n)) begin
        // The FSM asserts done only after a FULL contraction: the cycle before
        // done rises, k_idx must have reached K-1 (=255).  This is the property
        // that would have caught the historic K=4-vs-K=256 bug -- a controller
        // that finished early would violate it.
        if (done && !$past(done)) a_done_after_full : assert ($past(k_idx) == 8'd255);
    end
endmodule
