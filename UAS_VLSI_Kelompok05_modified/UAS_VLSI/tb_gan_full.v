`timescale 1ns / 1ps

`include "simple_gan_generator.v"
`include "simple_gan_discriminator.v"
`include "mac_q4_12.v"
`include "pla_activations.v" 

module tb_gan_full;
    reg clk;
    reg rst;
    reg start_gen;
    reg signed [15:0] z0_in, z1_in;
    wire done_gen;
    wire signed [15:0] w_px0, w_px1, w_px2, w_px3, w_px4, w_px5, w_px6, w_px7, w_px8;
    
    reg start_disc;
    wire signed [15:0] disc_score;
    wire done_disc;
    reg signed [15:0] input_z_rom [0:9];
    
    integer img_file;     
    integer i;

    // Instantiate Modules
    simple_gan_generator gen_inst (
        .clk(clk), .rst(rst), .start(start_gen),
        .z0_in(z0_in), .z1_in(z1_in),
        .pixel_0(w_px0), .pixel_1(w_px1), .pixel_2(w_px2),
        .pixel_3(w_px3), .pixel_4(w_px4), .pixel_5(w_px5),
        .pixel_6(w_px6), .pixel_7(w_px7), .pixel_8(w_px8),
        .done(done_gen)
    );

    simple_gan_discriminator disc_inst (
        .clk(clk), .rst(rst), .start(start_disc),
        .px0(w_px0), .px1(w_px1), .px2(w_px2),
        .px3(w_px3), .px4(w_px4), .px5(w_px5),
        .px6(w_px6), .px7(w_px7), .px8(w_px8),
        .decision_out(disc_score),
        .done(done_disc)
    );

    always #5 clk = ~clk;

    // --- FUNCTION: Q4.12 to 0-255 ---
    function [7:0] q4_12_to_byte;
        input signed [15:0] val;
        reg [31:0] temp;
        begin
            if (val < 0) val = 0; 
            // Rumus: val * 255 / 4096. 
            temp = (val * 255) >>> 12;
            if (temp > 255) temp = 255;
            q4_12_to_byte = temp[7:0];
        end
    endfunction

    initial begin
        $dumpfile("gan_full_wave.vcd");
        $dumpvars(0, tb_gan_full);

        clk = 0; rst = 1;
        start_gen = 0; start_disc = 0;
        z0_in = 0; z1_in = 0;
        
        // Load Test Vectors
        $readmemh("input_z.mem", input_z_rom);

        #100; rst = 0; #20;

        $display("===========================================");
        $display("=== STARTING GAN VERIFICATION SIMULATION ===");
        $display("===========================================\n");
        
        // Loop 5 kali sesuai jumlah test vector
        for (i = 0; i < 5; i = i + 1) begin
            // ------------------------------------------------
            // 1. RUN GENERATOR
            // ------------------------------------------------
            z0_in = input_z_rom[i*2];
            z1_in = input_z_rom[i*2 + 1];
            
            start_gen = 1; 
            #10; 
            start_gen = 0;
            
            wait(done_gen == 1);
            #10; 

            // ------------------------------------------------
            // 2. RUN DISCRIMINATOR
            // ------------------------------------------------
            start_disc = 1;
            #10; start_disc = 0;
            wait(done_disc == 1);
            #10;

            // ------------------------------------------------
            // 3. ANALISIS HASIL (VERDICT & ASCII ART)
            // ------------------------------------------------
            $display("--- Test Case %0d ---", i);
            
            
            // B. Cek Score Discriminator
            $display("\nDiscriminator Analysis:");
            $display("Score (Hex) : %h", disc_score);
            $display("Score (Dec) : %0d (out of 4096)", disc_score);
            
            // Threshold 0.5 dalam Q4.12 adalah 2048 (4096 / 2)
            if (disc_score > 2048) begin
                $display(">>> VERDICT : REAL (PASS) <<<");
                $display("    (Generator successfully fooled the Discriminator)");
            end else begin
                $display(">>> VERDICT : FAKE (FAIL) <<<");
                $display("    (Generator failed, image looks fake)");
            end
            $display("-------------------------------------------\n");

            // ------------------------------------------------
            // 4. SIMPAN KE FILE PGM
            // ------------------------------------------------
            img_file = $fopen($sformatf("gen_img_%0d.pgm", i), "w");
            $fwrite(img_file, "P2\n3 3\n255\n");
            $fwrite(img_file, "%0d %0d %0d\n", q4_12_to_byte(w_px0), q4_12_to_byte(w_px1), q4_12_to_byte(w_px2));
            $fwrite(img_file, "%0d %0d %0d\n", q4_12_to_byte(w_px3), q4_12_to_byte(w_px4), q4_12_to_byte(w_px5));
            $fwrite(img_file, "%0d %0d %0d\n", q4_12_to_byte(w_px6), q4_12_to_byte(w_px7), q4_12_to_byte(w_px8));
            $fclose(img_file);

            #50; // Delay antar test case
        end

        $finish;
    end

endmodule