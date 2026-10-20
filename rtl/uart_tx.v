`timescale 1ns/1ps
// start is accepted only when busy=0; data is latched on that edge.
module uart_tx #(parameter CLKS_PER_BIT=234)(
    input wire clk, rst, start, input wire [7:0] data,
    output reg tx, output reg busy
);
    reg [9:0] frame;
    reg [3:0] bit_index;
    reg [31:0] count;
    always @(posedge clk) begin
        if (rst) begin tx<=1; busy<=0; count<=0; bit_index<=0; frame<=10'h3ff; end
        else if (!busy) begin
            tx<=1;
            if (start) begin
                frame<={1'b1,data,1'b0}; tx<=0; busy<=1;
                bit_index<=0; count<=CLKS_PER_BIT-1;
            end
        end else if (count!=0) count<=count-1;
        else if (bit_index==9) begin busy<=0; tx<=1; end
        else begin
            bit_index<=bit_index+1;
            tx<=frame[bit_index+1]; count<=CLKS_PER_BIT-1;
        end
    end
endmodule
