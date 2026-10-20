`timescale 1ns/1ps
// 8N1 receiver. CLKS_PER_BIT must be >= 4. Input is synchronized.
module uart_rx #(parameter CLKS_PER_BIT=234)(
    input wire clk, rst, rx,
    output reg [7:0] data, output reg valid, output reg framing_error
);
    reg sync1=1, sync2=1;
    reg [1:0] state;
    reg [31:0] count;
    reg [2:0] bit_index;
    reg [7:0] shift;
    always @(posedge clk) begin
        sync1 <= rx;
        sync2 <= sync1;
        valid <= 0;
        framing_error <= 0;
        if (rst) begin
            state<=0; count<=0; bit_index<=0; shift<=0; data<=0;
            sync1<=1; sync2<=1;
        end else case (state)
            0: if (!sync2) begin state<=1; count<=CLKS_PER_BIT/2-1; end
            1: if (count!=0) count<=count-1;
               else if (sync2) state<=0; // reject false start
               else begin state<=2; count<=CLKS_PER_BIT-1; bit_index<=0; end
            2: if (count!=0) count<=count-1;
               else begin
                   shift[bit_index]<=sync2; count<=CLKS_PER_BIT-1;
                   if (bit_index==7) state<=3;
                   else bit_index<=bit_index+3'd1;
               end
            3: if (count!=0) count<=count-1;
               else begin
                   if (sync2) begin data<=shift; valid<=1; end
                   else framing_error<=1;
                   state<=0;
               end
        endcase
    end
endmodule
