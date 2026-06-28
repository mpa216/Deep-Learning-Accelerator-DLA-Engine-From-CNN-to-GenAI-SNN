`timescale 1ns / 1ps

module sram_weights_c1_1024x32 (
    input wire clk,
    input wire en,              // Chip Enable (Active High)
    input wire we,              // Write Enable (Active High)
    input wire [9:0] addr,      // Alamat 10-bit untuk kedalaman 1024
    input wire [31:0] data_in,  // Data bobot 32-bit dari CPU
    output wire [31:0] data_out // Data bobot 32-bit ke Hardware BNN
);

    // Konversi ke sinyal Active-Low untuk macro fisik GF180
    wire cen_b  = ~en;
    wire gwen_b = ~we;
    wire [7:0] wen_b = 8'b00000000; // Aktifkan penulisan 1 byte

    wire [7:0] q0, q1, q2, q3;

    // Instansiasi 4 Bank untuk 32-bit
    // Bank 0: Bit [7:0]
    gf180mcu_ocd_ip_sram__sram1024x8m8wm1 bank0 (
        .CLK(clk), .CEN(cen_b), .GWEN(gwen_b), .WEN(wen_b), 
        .A(addr), .D(data_in[7:0]), .Q(q0)
    );

    // Bank 1: Bit [15:8]
    gf180mcu_ocd_ip_sram__sram1024x8m8wm1 bank1 (
        .CLK(clk), .CEN(cen_b), .GWEN(gwen_b), .WEN(wen_b), 
        .A(addr), .D(data_in[15:8]), .Q(q1)
    );

    // Bank 2: Bit [23:16]
    gf180mcu_ocd_ip_sram__sram1024x8m8wm1 bank2 (
        .CLK(clk), .CEN(cen_b), .GWEN(gwen_b), .WEN(wen_b), 
        .A(addr), .D(data_in[23:16]), .Q(q2)
    );

    // Bank 3: Bit [31:24]
    gf180mcu_ocd_ip_sram__sram1024x8m8wm1 bank3 (
        .CLK(clk), .CEN(cen_b), .GWEN(gwen_b), .WEN(wen_b), 
        .A(addr), .D(data_in[31:24]), .Q(q3)
    );

    // Gabungkan kembali
    assign data_out = {q3, q2, q1, q0};

endmodule