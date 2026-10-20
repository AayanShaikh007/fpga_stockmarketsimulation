`timescale 1ns/1ps
module engine #(
    parameter [31:0] FAIR = 10000,
    parameter [31:0] THRESHOLD = 5,
    parameter [15:0] MAX_ORDER = 20,
    parameter signed [31:0] LIMIT = 100
)(
    input wire clk, input wire rst,
    input wire in_valid, input wire [31:0] price,
    input wire [15:0] quantity, input wire kill,
    output reg out_valid, output reg signed [31:0] order,
    output reg signed [31:0] position, output reg killed
);
    reg signed [32:0] delta;
    reg signed [32:0] room;
    reg signed [32:0] amount;
    reg signed [31:0] next_order;
    always @* begin
        delta = $signed({1'b0, FAIR}) - $signed({1'b0, price});
        room = 0;
        amount = 0;
        next_order = 0;
        if (!killed && !kill) begin
            if (delta >= $signed({1'b0, THRESHOLD}))
                room = $signed({1'b0, LIMIT}) - $signed(position);
            else if (delta <= -$signed({1'b0, THRESHOLD}))
                room = $signed({1'b0, LIMIT}) + $signed(position);
            amount = {17'b0, quantity};
            if (amount > $signed({17'b0, MAX_ORDER})) amount = {17'b0, MAX_ORDER};
            if (amount > room) amount = room;
            if (delta >= $signed({1'b0, THRESHOLD})) next_order = amount;
            else if (delta <= -$signed({1'b0, THRESHOLD})) next_order = -amount;
        end
    end
    always @(posedge clk) begin
        if (rst) begin
            position <= 0;
            killed <= 0;
            order <= 0;
            out_valid <= 0;
        end else begin
            out_valid <= in_valid;
            if (in_valid) begin
                order <= next_order;
                position <= position + next_order;
                killed <= killed | kill;
            end
        end
    end
endmodule
