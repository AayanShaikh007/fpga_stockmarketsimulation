`timescale 1ns/1ps
module nanoquant_top(
    input wire clk, rst_n, uart_rx,
    output wire uart_tx,
    output wire [5:0] led
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
    wire action_valid;
    wire signed [31:0] action_order;
    nanoquant_core core(clk,rst,uart_rx,uart_tx,error_latched,killed,
                        action_valid,action_order);
    action_leds indicators(clk,rst,action_valid,action_order,killed,error_latched,led);
endmodule

`timescale 1ns/1ps
// Tang Nano 9K LEDs are active low. Stretch one-cycle results to 200 ms.
module action_leds #(parameter PULSE_CLKS=5400000)(
    input wire clk, rst, action_valid,
    input wire signed [31:0] action_order,
    input wire killed, error_latched,
    output wire [5:0] led
);
    localparam WIDTH = (PULSE_CLKS < 2) ? 1 : $clog2(PULSE_CLKS+1);
    reg [WIDTH-1:0] activity_left, buy_left, sell_left, hold_left;
    always @(posedge clk) begin
        if (rst) begin
            activity_left<=0; buy_left<=0; sell_left<=0; hold_left<=0;
        end else begin
            if (activity_left!=0) activity_left<=activity_left-1'b1;
            if (buy_left!=0) buy_left<=buy_left-1'b1;
            if (sell_left!=0) sell_left<=sell_left-1'b1;
            if (hold_left!=0) hold_left<=hold_left-1'b1;
            if (action_valid) begin
                activity_left<=PULSE_CLKS;
                if (!killed) begin
                    if (action_order>0) buy_left<=PULSE_CLKS;
                    else if (action_order<0) sell_left<=PULSE_CLKS;
                    else hold_left<=PULSE_CLKS;
                end
            end
        end
    end
    assign led=~{(!rst && error_latched),(!rst && killed),
                 (hold_left!=0),(sell_left!=0),(buy_left!=0),(activity_left!=0)};
endmodule
