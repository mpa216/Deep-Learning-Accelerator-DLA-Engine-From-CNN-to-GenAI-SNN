`timescale 1ns / 1ps

module simple_gan_generator (
    input wire clk,
    input wire rst,
    input wire start,
    input wire signed [15:0] z0_in,
    input wire signed [15:0] z1_in,
    output reg signed [15:0] pixel_0, pixel_1, pixel_2,
    output reg signed [15:0] pixel_3, pixel_4, pixel_5,
    output reg signed [15:0] pixel_6, pixel_7, pixel_8,
    output reg done
);
    // --- Memory ---
    reg signed [15:0] rom_w1 [0:5];   // 3 Neurons * 2 Inputs
    reg signed [15:0] rom_b1 [0:2];   // 3 Biases
    reg signed [15:0] rom_w2 [0:26];  // 9 Neurons * 3 Inputs
    reg signed [15:0] rom_b2 [0:8];   // 9 Biases

    initial begin
        $readmemh("rom_g_w1.mem", rom_w1);
        $readmemh("rom_g_b1.mem", rom_b1);
        $readmemh("rom_g_w2.mem", rom_w2);
        $readmemh("rom_g_b2.mem", rom_b2);
    end

    // --- Signals ---
    reg signed [15:0] layer1_out [0:2];
    reg signed [15:0] layer2_out [0:8];
    
    // MAC Signals
    reg signed [15:0] mac_a, mac_b;
    reg signed [31:0] mac_acc;       // Accumulator Q8.24
    wire signed [31:0] mac_res;      // Output dari modul MAC
    
    // PWL Signals
    reg signed [15:0] pwl_in;
    wire signed [15:0] tanh_out, sigmoid_out;
    
    // Modules
    // MAC: out = c + (a*b)
    mac_q4_12 u_mac (.a(mac_a), .b(mac_b), .c(mac_acc), .out(mac_res));
    
    pla_tanh    u_tanh  (.clk(clk), .rst(rst), .data_in(pwl_in), .data_out(tanh_out));
    pla_sigmoid u_sigm  (.clk(clk), .rst(rst), .data_in(pwl_in), .data_out(sigmoid_out));

    // Control
    integer n_idx, i_idx;
    reg [2:0] wait_cnt;
    reg [3:0] state;

    localparam S_IDLE       = 0;
    localparam S_L1_LOAD    = 1;
    localparam S_L1_CALC    = 2;
    localparam S_L1_WAIT    = 3;
    localparam S_L2_LOAD    = 4;
    localparam S_L2_CALC    = 5;
    localparam S_L2_WAIT    = 6;
    localparam S_DONE       = 7;

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            state <= S_IDLE;
            done <= 0;
            mac_acc <= 0; mac_a <= 0; mac_b <= 0;
        end else begin
            case (state)
                S_IDLE: begin
                    done <= 0;
                    if (start) begin
                        n_idx <= 0;
                        state <= S_L1_LOAD;
                    end
                end

                // --- LAYER 1 (Tanh) ---
                S_L1_LOAD: begin
                    // Load Bias (Shift Q4.12 -> Q8.24)
                    mac_acc <= {{4{rom_b1[n_idx][15]}}, rom_b1[n_idx], 12'b0};
                    i_idx <= 0;
                    state <= S_L1_CALC;
                end

                S_L1_CALC: begin
                    if (i_idx < 2) begin
                        // Set input untuk MAC (Logic Combinational MAC akan hitung a*b+c)
                        mac_a <= (i_idx == 0) ? z0_in : z1_in;
                        mac_b <= rom_w1[n_idx*2 + i_idx];
                        
                        // NOTE: Jika i_idx > 0, kita harus ambil hasil akumulasi sebelumnya.
                        // Di cycle pertama (i_idx=0), mac_acc sudah diisi bias.
                        // Namun karena mac_a/b baru di-set SEKARANG, hasil mac_res baru valid CYCLE DEPAN.
                        // Kita perlu delay state atau pipelining. 
                        // Cara termudah dalam FSM sederhana: Gunakan blocking atau tambah state.
                        // Disini saya gunakan pendekatan: Update mac_acc di cycle berikutnya.
                        
                        // Modifikasi flow agar sinkron:
                        // Cycle ini: Set A & B.
                        // Cycle depan: Latch mac_res ke mac_acc.
                        // Karena logic ini kompleks dalam satu state, kita pakai simple approach:
                        // Asumsi module mac combinational delay cukup kecil.
                    end 
                    
                    // Logic Akumulasi (Pipeline-friendly)
                    if (i_idx > 0) begin
                         mac_acc <= mac_res; // Ambil hasil perhitungan (A*B + Acc_prev)
                    end

                    if (i_idx == 2) begin // Selesai input 0 & 1
                         // Ambil hasil terakhir
                         mac_acc <= mac_res; 
                         state <= S_L1_WAIT; // Transisi ke activation
                         wait_cnt <= 0;
                    end else begin
                         i_idx <= i_idx + 1;
                    end
                end

                S_L1_WAIT: begin
                    if (wait_cnt == 0) begin
                        // Potong balik ke Q4.12 untuk input activation
                        pwl_in <= mac_acc[27:12]; 
                        wait_cnt <= 1;
                    end else if (wait_cnt < 4) begin
                        // Tunggu latency module PLA (min 2 cycle)
                        wait_cnt <= wait_cnt + 1;
                    end else begin
                        layer1_out[n_idx] <= tanh_out;
                        if (n_idx < 2) begin
                            n_idx <= n_idx + 1;
                            state <= S_L1_LOAD;
                        end else begin
                            n_idx <= 0;
                            state <= S_L2_LOAD;
                        end
                    end
                end

                // --- LAYER 2 (Sigmoid) ---
                S_L2_LOAD: begin
                    mac_acc <= {{4{rom_b2[n_idx][15]}}, rom_b2[n_idx], 12'b0};
                    i_idx <= 0;
                    state <= S_L2_CALC;
                end

                S_L2_CALC: begin
                    if (i_idx < 3) begin
                        mac_a <= layer1_out[i_idx];
                        mac_b <= rom_w2[n_idx*3 + i_idx];
                    end

                    if (i_idx > 0) mac_acc <= mac_res;

                    if (i_idx == 3) begin
                        mac_acc <= mac_res;
                        state <= S_L2_WAIT;
                        wait_cnt <= 0;
                    end else begin
                        i_idx <= i_idx + 1;
                    end
                end

                S_L2_WAIT: begin
                    if (wait_cnt == 0) begin
                        pwl_in <= mac_acc[27:12];
                        wait_cnt <= 1;
                    end else if (wait_cnt < 4) begin
                        wait_cnt <= wait_cnt + 1;
                    end else begin
                        layer2_out[n_idx] <= sigmoid_out;
                        if (n_idx < 8) begin
                            n_idx <= n_idx + 1;
                            state <= S_L2_LOAD;
                        end else begin
                            state <= S_DONE;
                        end
                    end
                end

                S_DONE: begin
                    done <= 1;
                    pixel_0 <= layer2_out[0]; pixel_1 <= layer2_out[1]; pixel_2 <= layer2_out[2];
                    pixel_3 <= layer2_out[3]; pixel_4 <= layer2_out[4]; pixel_5 <= layer2_out[5];
                    pixel_6 <= layer2_out[6]; pixel_7 <= layer2_out[7]; pixel_8 <= layer2_out[8];
                    state <= S_IDLE;
                end
            endcase
        end
    end
endmodule