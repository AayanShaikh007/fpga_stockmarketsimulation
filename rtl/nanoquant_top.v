`timescale 1ns/1ps
module nanoquant_top(
    input wire clk, rst_n, uart_rx,
    output wire uart_tx
);
    // Gowin register initialization supplies power-on reset; release is synchronized.
    reg [7:0] startup=0;
    reg [1:0] reset_sync=0;
    always @(posedge clk) begin
        if (!(&startup)) startup<=startup+1'b1;
        reset_sync<={reset_sync[0],rst_n};
    end
    wire rst= !(&startup) || !reset_sync[1];
    wire error_latched, killed;
    nanoquant_core core(clk,rst,uart_rx,uart_tx,error_latched,killed);
endmodule
