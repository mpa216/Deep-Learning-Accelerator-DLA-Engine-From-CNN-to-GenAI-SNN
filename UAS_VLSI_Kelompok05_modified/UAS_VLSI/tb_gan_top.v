`timescale 1ns / 1ps
`include "pla_activations.v"
`include "simple_gan_generator.v"

module tb_gan_top;

    reg clk, rst, start;
    reg signed [15:0] z0, z1;
    wire signed [15:0] px[0:8];
    wire done;

    // Mapping output array ke wire individual jika perlu
    wire signed [15:0] p0 = px[0];
    
    // Instantiation
    simple_gan_generator uut (
        .clk(clk), .rst(rst), .start(start),
        .z0_in(z0), .z1_in(z1),
        .pixel_0(px[0]), .pixel_1(px[1]), .pixel_2(px[2]),
        .pixel_3(px[3]), .pixel_4(px[4]), .pixel_5(px[5]),
        .pixel_6(px[6]), .pixel_7(px[7]), .pixel_8(px[8]),
        .done(done)
    );

    // Clock generation
    always #5 clk = ~clk;

    // Helper untuk print float
    function real to_float;
        input signed [15:0] val;
        begin
            to_float = val / 4096.0;
        end
    endfunction

    reg signed [15:0] z_mem [0:9];
    integer i;

    initial begin
        clk = 0; rst = 1; start = 0; z0=0; z1=0;
        $readmemh("input_z.mem", z_mem); // Load test vectors

        #100 rst = 0;

        // Test Loop
        for (i=0; i<3; i=i+1) begin
            #20;
            z0 = z_mem[i*2];
            z1 = z_mem[i*2+1];
            
            $display("--- Test Case %0d : Z=[%f, %f] ---", i, to_float(z0), to_float(z1));
            start = 1;
            #10 start = 0;

            wait(done);
            #10;
            
            $display("Output Pixels (3x3):");
            $display("%f %f %f", to_float(px[0]), to_float(px[1]), to_float(px[2]));
            $display("%f %f %f", to_float(px[3]), to_float(px[4]), to_float(px[5]));
            $display("%f %f %f", to_float(px[6]), to_float(px[7]), to_float(px[8]));
        end
        
        $finish;
    end

endmodule