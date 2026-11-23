// Safety properties for dla_link_sel (LVDS receiver integration, branch
// lvds-integration).  Formal WRAPPER (this module is the proof top and
// instantiates the RTL), like dla_controller_props: Yosys 0.64's open-source
// frontend parses a `bind` directive but silently drops it, so a bound property
// module elaborates to nothing and the proof passes vacuously.  Every property
// here is stated on the module's ports plus observer counters, no internals.
// Immediate-assertion-in-clocked-always form, as the other proofs here.
// Proven with SymbiYosys k-induction (formal/dla_link_sel.sby, task prove);
// task cover shows the switch to LVDS and back is reachable.
module dla_link_sel_props #(
    parameter integer WAKE_CLKS = 64
) (
    input clk,
    input rst_n,
    input link_sel_pad
);
    wire lvds_en, lvds_active;

    dla_link_sel #(.WAKE_CLKS(WAKE_CLKS)) dut (
        .clk          (clk),
        .rst_n        (rst_n),
        .link_sel_pad (link_sel_pad),
        .lvds_en      (lvds_en),
        .lvds_active  (lvds_active)
    );

    // reason about post-reset behaviour (same convention as dla_controller_props)
    reg f_init = 1'b1;
    always @(posedge clk) f_init <= 1'b0;
    always @(*) if (f_init) assume (!rst_n);

    // observer counters (saturating), updated with the pre-edge values
    reg [7:0] f_en_run = 8'd0;   // consecutive clocks lvds_en has been high
    reg [7:0] f_ls_run = 8'd0;   // consecutive clocks the strap was sampled high out of reset
    reg [1:0] f_lo_run = 2'd0;   // consecutive clocks the strap was low or reset held (sat. at 3)
    always @(posedge clk) begin
        if (!rst_n || !lvds_en)      f_en_run <= 8'd0;
        else if (f_en_run != 8'hff)  f_en_run <= f_en_run + 8'd1;
        if (!rst_n || !link_sel_pad) f_ls_run <= 8'd0;
        else if (f_ls_run != 8'hff)  f_ls_run <= f_ls_run + 8'd1;
        if (rst_n && link_sel_pad)   f_lo_run <= 2'd0;
        else if (f_lo_run != 2'd3)   f_lo_run <= f_lo_run + 2'd1;
    end

    always @(*) begin
        // EN is held LOW while the chip is in reset (macro rule D-008 via rst_n)
        if (!rst_n) a_reset_en_off : assert (!lvds_en && !lvds_active);
        // the bridge never reads the receiver while the receiver is off
        a_active_needs_en : assert (!lvds_active || lvds_en);
    end

    always @(posedge clk) if (rst_n && !f_init) begin
        // the bridge switches only after EN has been high for the full wake time
        if (lvds_active) a_wake_respected : assert (f_en_run >= WAKE_CLKS);
        // the strap held high for WAKE+2 clocks always completes the switch (no stuck
        // state; 2 = the synchroniser): with a_wake_respected this pins the latency
        if (f_ls_run >= WAKE_CLKS + 2) a_switch_completes : assert (lvds_active);
        // EN follows the strap through the 2-FF synchroniser, both ways
        if (f_ls_run >= 2) a_en_follows_high : assert (lvds_en);
        if (f_lo_run >= 2) a_en_follows_low  : assert (!lvds_en && !lvds_active);
    end

    // reachability (task cover): LVDS selected, and back off again afterwards
    reg f_seen_active = 1'b0;
    always @(posedge clk) if (lvds_active) f_seen_active <= 1'b1;
    always @(*) begin
        c_active   : cover (lvds_active);
        c_back_off : cover (f_seen_active && rst_n && !lvds_en && !lvds_active);
    end
endmodule
