`timescale 1ns / 1ps

// Controller FSM for one matrix multiply transaction across K MAC cycles.
module dla_controller #(
    parameter K       = 4,
    parameter K_IDX_W = (K <= 1) ? 1 : $clog2(K)
) (
    input                      clk,
    input                      rst_n,
    input                      start,
    output reg                 clear_pe,
    output reg                 en_pe,
    output reg [K_IDX_W-1:0]   k_idx,
    output reg                 done,
    output reg                 busy
);

    localparam [1:0] S_IDLE    = 2'b00;
    localparam [1:0] S_CLEAR   = 2'b01;
    localparam [1:0] S_COMPUTE = 2'b10;
    localparam [1:0] S_DONE    = 2'b11;

    reg [1:0] state;
    reg [1:0] next_state;

    // Next-state logic.
    always @* begin
        next_state = state;

        case (state)
            S_IDLE: begin
                if (start) begin
                    next_state = S_CLEAR;
                end
            end

            S_CLEAR: begin
                next_state = S_COMPUTE;
            end

            S_COMPUTE: begin
                if (k_idx == (K-1)) begin
                    next_state = S_DONE;
                end
            end

            S_DONE: begin
                if (!start) begin
                    next_state = S_IDLE;
                end
            end

            default: begin
                next_state = S_IDLE;
            end
        endcase
    end

    // State and k-index update.
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= S_IDLE;
            k_idx <= {K_IDX_W{1'b0}};
        end else begin
            state <= next_state;

            if ((state == S_IDLE) || (state == S_CLEAR)) begin
                k_idx <= {K_IDX_W{1'b0}};
            end else if ((state == S_COMPUTE) && (k_idx != (K-1))) begin
                k_idx <= k_idx + 1'b1;
            end
        end
    end

    // Control outputs are purely combinational from state.
    always @* begin
        clear_pe = (state == S_CLEAR);
        en_pe    = (state == S_COMPUTE);
        done     = (state == S_DONE);
        busy     = ((state == S_CLEAR) || (state == S_COMPUTE));
    end

endmodule
