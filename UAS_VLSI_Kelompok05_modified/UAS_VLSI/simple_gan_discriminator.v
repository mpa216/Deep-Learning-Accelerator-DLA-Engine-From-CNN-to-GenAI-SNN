module simple_gan_discriminator (
    input wire clk,
    input wire rst,
    input wire start,
    // 9 Pixel Input
    input wire signed [15:0] px0, px1, px2, px3, px4, px5, px6, px7, px8,
    output reg signed [15:0] decision_out, // Real vs Fake Score
    output reg done
);

    // ==========================================
    // Memory Definitions
    // ==========================================
    reg signed [15:0] rom_w1 [0:26]; // 9 inputs * 3 hidden = 27 weights
    reg signed [15:0] rom_b1 [0:2];  // 3 biases
    reg signed [15:0] rom_w2 [0:2];  // 3 hidden * 1 output = 3 weights
    reg signed [15:0] rom_b2 [0:0];  // 1 bias

    initial begin
        $readmemh("rom_d_w1.mem", rom_w1);
        $readmemh("rom_d_b1.mem", rom_b1);
        $readmemh("rom_d_w2.mem", rom_w2);
        $readmemh("rom_d_b2.mem", rom_b2);
    end

    // ==========================================
    // Internal Signals
    // ==========================================
    localparam S_IDLE = 0, S_L1_CALC = 1, S_L1_WAIT = 2, S_L2_CALC = 3, S_L2_WAIT = 4, S_DONE = 5;
    
    reg [2:0] state;
    reg [3:0] neuron_idx, input_idx;
    reg [2:0] pipeline_cnt;
    reg signed [31:0] acc;
    
    // Data Storage
    reg signed [15:0] input_pixels [0:8]; // Buffer input
    reg signed [15:0] hidden_layer [0:2]; // Buffer hidden
    
    // MAC & PWL Signals
    reg signed [15:0] mac_a, mac_b;
    wire signed [31:0] mac_res;
    reg signed [15:0] pwl_in;
    wire signed [15:0] pwl_out_tanh, pwl_out_sigmoid;

    mac_q4_12 mac_inst (.a(mac_a), .b(mac_b), .c(acc), .out(mac_res));
    pla_tanh tanh_inst (.clk(clk), .rst(rst), .data_in(pwl_in), .data_out(pwl_out_tanh));
    pla_sigmoid sig_inst (.clk(clk), .rst(rst), .data_in(pwl_in), .data_out(pwl_out_sigmoid));

    // ==========================================
    // FSM
    // ==========================================
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            state <= S_IDLE;
            done <= 0;
            neuron_idx <= 0; input_idx <= 0; pipeline_cnt <= 0; acc <= 0;
        end else begin
            case (state)
                S_IDLE: begin
                    done <= 0;
                    if (start) begin
                        state <= S_L1_CALC;
                        // Capture inputs
                        input_pixels[0] <= px0; input_pixels[1] <= px1; input_pixels[2] <= px2;
                        input_pixels[3] <= px3; input_pixels[4] <= px4; input_pixels[5] <= px5;
                        input_pixels[6] <= px6; input_pixels[7] <= px7; input_pixels[8] <= px8;
                    end
                    neuron_idx <= 0; input_idx <= 0; pipeline_cnt <= 0;
                end

                // --- LAYER 1: 9 Input -> 3 Hidden (Tanh) ---
                S_L1_CALC: begin
                    if (input_idx == 0) begin
                        acc <= {{16{rom_b1[neuron_idx][15]}}, rom_b1[neuron_idx]};
                    end 
                    
                    if (input_idx < 9) begin
                        if (input_idx > 0) acc <= mac_res;
                        mac_a <= input_pixels[input_idx];
                        // Addressing: Row major (9 kolom per baris)
                        // idx = input_idx + (neuron_idx * 9) <-- HATI-HATI: Struktur memori python
                        // Script python menyimpan: W_D1 flattened. Shape (9,3).
                        // Row 0 (input 0) connect ke neuron 0,1,2.
                        // Jadi urutan di memori: [w00, w01, w02, w10, w11...]
                        // Input i connect ke neuron j ada di index: i*3 + j
                        mac_b <= rom_w1[(input_idx * 3) + neuron_idx]; 
                        input_idx <= input_idx + 1;
                    end else begin
                        acc <= mac_res;
                        pwl_in <= mac_res[15:0];
                        state <= S_L1_WAIT;
                        pipeline_cnt <= 0;
                    end
                end

                S_L1_WAIT: begin
                    if (pipeline_cnt < 4) pipeline_cnt <= pipeline_cnt + 1;
                    else begin
                        hidden_layer[neuron_idx] <= pwl_out_tanh;
                        if (neuron_idx == 2) begin // 3 Neuron selesai
                            state <= S_L2_CALC; neuron_idx <= 0; input_idx <= 0;
                        end else begin
                            neuron_idx <= neuron_idx + 1; state <= S_L1_CALC; input_idx <= 0;
                        end
                    end
                end

                // --- LAYER 2: 3 Hidden -> 1 Output (Sigmoid) ---
                S_L2_CALC: begin
                    if (input_idx == 0) acc <= {{16{rom_b2[0][15]}}, rom_b2[0]}; // Hanya 1 bias
                    
                    if (input_idx < 3) begin
                        if (input_idx > 0) acc <= mac_res;
                        mac_a <= hidden_layer[input_idx];
                        // Weight (3,1). Flat: [w00, w10, w20]
                        mac_b <= rom_w2[input_idx];
                        input_idx <= input_idx + 1;
                    end else begin
                        acc <= mac_res;
                        pwl_in <= mac_res[15:0];
                        state <= S_L2_WAIT;
                        pipeline_cnt <= 0;
                    end
                end

                S_L2_WAIT: begin
                    if (pipeline_cnt < 4) pipeline_cnt <= pipeline_cnt + 1;
                    else begin
                        decision_out <= pwl_out_sigmoid;
                        state <= S_DONE;
                    end
                end

                S_DONE: begin
                    done <= 1;
                    state <= S_IDLE;
                end
            endcase
        end
    end
endmodule