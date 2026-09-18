// SVA safety properties for dla_serial_bridge, attached by `bind` so the RTL
// stays pristine (no `ifdef FORMAL` in the tapeout source).  Reaches the
// bridge's INTERNAL state/bitcnt/cs_n_s -- the properties that make formal
// worthwhile (no illegal state is ever reachable; the frame bit-counter can
// never over-run) live on internal signals, not ports.
//
// Immediate-assertion-in-clocked-always form (portable across Yosys/Verilator).
// Proven with SymbiYosys k-induction: see formal/dla_serial_bridge.sby.
module dla_serial_bridge_props (
    input        clk,
    input        rst_n,
    input  [3:0] state,
    input  [4:0] bitcnt,
    input        cs_n_s,
    input        start,
    input        wr_en,
    input        rd_en
);
    localparam [3:0] S_IDLE = 4'd0;
    localparam [3:0] S_DONE = 4'd10;   // highest legal state encoding

    // ---- pure safety invariants (hold every cycle out of reset) ----
    always @(posedge clk) if (rst_n) begin
        // No unreachable/illegal FSM state is ever entered (4 bits hold 0..15;
        // only 0..10 are legal).  The headline "formal proves it" property.
        a_state_legal  : assert (state <= S_DONE);

        // The frame bit-counter never over-runs the widest field (24-bit
        // READ_C data-out walk, bitcnt 0..23; 5 bits hold 0..31).
        a_bitcnt_bound : assert (bitcnt <= 5'd23);

        // Control-output pulses are mutually exclusive (they live in disjoint
        // states), so the DLA never sees two commands at once.
        a_excl_start_wr: assert (!(start && wr_en));
        a_excl_start_rd: assert (!(start && rd_en));
        a_excl_wr_rd   : assert (!(wr_en  && rd_en));
    end

    // ---- one-cycle-history (temporal) properties ----
    always @(posedge clk) if (rst_n && $past(rst_n)) begin
        // Deasserting CS_N (synchronised high) always returns the FSM to IDLE
        // next cycle -- a host can abort any frame safely at any time.
        if ($past(cs_n_s)) a_abort_to_idle : assert (state == S_IDLE);

        // start and wr_en are strictly single-cycle pulses to the core.
        if ($past(start))  a_start_is_pulse : assert (!start);
        if ($past(wr_en))  a_wren_is_pulse  : assert (!wr_en);
    end
endmodule

// Attach to every instance of dla_serial_bridge, wiring the props ports to the
// bridge's internal signals of the same name.
bind dla_serial_bridge dla_serial_bridge_props u_props (
    .clk(clk), .rst_n(rst_n),
    .state(state), .bitcnt(bitcnt), .cs_n_s(cs_n_s),
    .start(start), .wr_en(wr_en), .rd_en(rd_en)
);
