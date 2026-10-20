`timescale 1ns/1ps
// Stop-and-wait transport: one quote, one response. No quote queue.
module nanoquant_core #(parameter CLKS_PER_BIT=234, TIMEOUT_CLKS=270000)(
    input wire clk, rst, uart_rx_pin,
    output wire uart_tx_pin,
    output reg error_latched,
    output wire killed,
    output wire action_valid,
    output wire signed [31:0] action_order
);
    wire [7:0] rx_data;
    wire rx_valid, framing_error, quote_valid, packet_error;
    wire [31:0] quote_sequence, price;
    wire [15:0] quantity;
    wire kill;
    reg active;
    wire result_valid;
    wire signed [31:0] order, position;
    assign action_valid=result_valid;
    assign action_order=order;
    reg [31:0] accepted_sequence;
    uart_rx #(.CLKS_PER_BIT(CLKS_PER_BIT)) receiver(
        clk,rst,uart_rx_pin,rx_data,rx_valid,framing_error);
    packet_rx #(.TIMEOUT_CLKS(TIMEOUT_CLKS)) parser(
        clk,rst,rx_valid,framing_error,rx_data,quote_valid,packet_error,
        quote_sequence,price,quantity,kill);
    engine trading(clk,rst,quote_valid && !active,price,quantity,kill,
                   result_valid,order,position,killed);
    reg [159:0] response;
    reg [4:0] tx_index;
    reg [1:0] send_state;
    reg tx_start;
    reg [7:0] tx_data;
    wire tx_busy;
    uart_tx #(.CLKS_PER_BIT(CLKS_PER_BIT)) transmitter(
        clk,rst,tx_start,tx_data,uart_tx_pin,tx_busy);
    function [15:0] response_crc;
        input [143:0] bytes;
        reg [15:0] c;
        integer i,j;
        begin
            c=16'hffff;
            for (i=0;i<18;i=i+1) begin
                c=c ^ {bytes[i*8 +: 8],8'b0};
                for (j=0;j<8;j=j+1) c=c[15] ? (c<<1)^16'h1021 : c<<1;
            end
            response_crc=c;
        end
    endfunction
    wire [143:0] response_body={16'd1,position,order,accepted_sequence,
                               7'b0,killed,8'd1,16'h524e};
    always @(posedge clk) begin
        tx_start<=0;
        if (rst) begin
            active<=0; error_latched<=0; accepted_sequence<=0;
            response<=0; tx_index<=0; send_state<=0; tx_start<=0; tx_data<=0;
        end else begin
            if (framing_error || packet_error || (quote_valid && active)) error_latched<=1;
            if (quote_valid && !active) begin active<=1; accepted_sequence<=quote_sequence; end
            if (result_valid) begin
                response<={response_crc(response_body),response_body};
                tx_index<=0; send_state<=1;
            end
            case (send_state)
                1: if (!tx_busy) begin
                    tx_data<=response[tx_index*8 +: 8]; tx_start<=1; send_state<=2;
                end
                2: if (tx_busy) send_state<=3;
                3: if (!tx_busy) begin
                    if (tx_index==19) begin send_state<=0; active<=0; end
                    else begin tx_index<=tx_index+5'd1; send_state<=1; end
                end
            endcase
        end
    end
endmodule
