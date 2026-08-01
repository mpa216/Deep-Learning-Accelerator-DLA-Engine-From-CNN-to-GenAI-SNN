`timescale 1ns / 1ps

// ================================================================
// Tanh Activation Module (Q4.12 Fixed Point)
// Latency: 2 Clock Cycles
// ================================================================
module pla_tanh (
    input wire clk,
    input wire rst,
    input wire signed [15:0] data_in,
    output reg signed [15:0] data_out
);
    reg signed [15:0] m, c, x_d;
    reg signed [31:0] mult_res;

    always @(posedge clk) begin
        if (rst) begin
            m <= 0; c <= 0; x_d <= 0;
            data_out <= 0;
        end else begin
            // --- Stage 1: Coefficient Lookup & Input Latch ---
            x_d <= data_in; // Simpan input untuk stage selanjutnya
            
            if (data_in < $signed(-20480))      begin m<=0;    c<=-4093; end 
            else if (data_in < $signed(-12288)) begin m<=10;   c<=-4046; end 
            else if (data_in < $signed(-6144))  begin m<=246;  c<=-3339; end 
            else if (data_in < $signed(-3072))  begin m<=1475; c<=-1496; end 
            else if (data_in < $signed(3072))   begin m<=3469; c<=0;     end     
            else if (data_in < $signed(6144))   begin m<=1475; c<=1496;  end  
            else if (data_in < $signed(12288))  begin m<=246;  c<=3339;  end   
            else if (data_in < $signed(20480))  begin m<=10;   c<=4046;  end    
            else                                begin m<=0;    c<=4093;  end 

            // --- Stage 2: Calculation ---
            // Menggunakan m, c, dan x_d dari cycle sebelumnya (Stage 1)
            // mult_res = Q4.12 * Q4.12 = Q8.24
            mult_res = m * x_d; 
            
            // Shift Q8.24 -> Q4.12 dan tambah C
            data_out <= (mult_res >>> 12) + c;
        end
    end
endmodule

// ================================================================
// Sigmoid Activation Module (Q4.12 Fixed Point)
// ================================================================
module pla_sigmoid (
    input wire clk,
    input wire rst,
    input wire signed [15:0] data_in,
    output reg signed [15:0] data_out
);
    reg signed [15:0] m, c, x_d;
    reg signed [31:0] mult_res;

    always @(posedge clk) begin
        if (rst) begin
            m <= 0; c <= 0; x_d <= 0;
            data_out <= 0;
        end else begin
            // --- Stage 1: Coefficient Lookup ---
            x_d <= data_in;

            if (data_in < $signed(-20480))      begin m<=21;  c<=130;  end
            else if (data_in < $signed(-12288)) begin m<=83;  c<=445;  end
            else if (data_in < $signed(-6144))  begin m<=369; c<=1300; end
            else if (data_in < $signed(-3072))  begin m<=756; c<=1881; end
            else if (data_in < $signed(3072))   begin m<=979; c<=2048; end
            else if (data_in < $signed(6144))   begin m<=756; c<=2215; end
            else if (data_in < $signed(12288))  begin m<=369; c<=2796; end
            else if (data_in < $signed(20480))  begin m<=83;  c<=3651; end
            else                                begin m<=21;  c<=3966; end

            // --- Stage 2: Calculation ---
            mult_res = m * x_d;
            data_out <= (mult_res >>> 12) + c;
        end
    end
endmodule