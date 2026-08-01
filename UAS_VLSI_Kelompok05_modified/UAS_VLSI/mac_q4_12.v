`timescale 1ns / 1ps

module mac_q4_12 (
    input wire signed [15:0] a,       // Input (Q4.12)
    input wire signed [15:0] b,       // Weight (Q4.12)
    input wire signed [31:0] c,       // Accumulator (Q8.24) -> Presisi Tinggi
    output wire signed [31:0] out     // Result (Q8.24)
);
    
    // a * b menghasilkan 32-bit Q8.24 (karena 12 frac + 12 frac = 24 frac)
    // Kita tambahkan langsung ke c tanpa shifting agar tidak ada data yang hilang
    assign out = c + (a * b);

endmodule