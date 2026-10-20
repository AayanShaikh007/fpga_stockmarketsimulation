`timescale 1ns/1ps
// Fixed-size quote parser. A partial frame expires after TIMEOUT_CLKS.
module packet_rx #(parameter TIMEOUT_CLKS=270000)(
    input wire clk, rst, byte_valid, abort_frame,
    input wire [7:0] byte_data,
    output reg quote_valid, output reg packet_error,
    output reg [31:0] quote_sequence, price,
    output reg [15:0] quantity, output reg kill
);
    reg [4:0] index;
    reg [31:0] idle_count;
    reg [15:0] crc;
    reg [7:0] crc_low;
    reg header_ok;
    function [15:0] crc_byte;
        input [15:0] previous;
        input [7:0] value;
        reg [15:0] c;
        integer i;
        begin
            c=previous ^ {value,8'b0};
            for (i=0;i<8;i=i+1)
                c=c[15] ? (c<<1)^16'h1021 : c<<1;
            crc_byte=c;
        end
    endfunction
    always @(posedge clk) begin
        quote_valid<=0; packet_error<=0;
        if (rst) begin
            index<=0; idle_count<=0; crc<=16'hffff; crc_low<=0;
            header_ok<=0; quote_sequence<=0; price<=0; quantity<=0; kill<=0;
        end else if (abort_frame || (index!=0 && idle_count==TIMEOUT_CLKS-1 && !byte_valid)) begin
            index<=0; idle_count<=0; packet_error<=1;
        end else if (byte_valid) begin
            idle_count<=0;
            case (index)
                0: if (byte_data==8'h4e) begin
                    index<=1; crc<=crc_byte(16'hffff,byte_data); header_ok<=1;
                end
                1: if (byte_data==8'h51) begin
                    index<=2; crc<=crc_byte(crc,byte_data);
                end else if (byte_data==8'h4e) begin
                    crc<=crc_byte(16'hffff,byte_data); // overlapping N N Q
                end else begin index<=0; packet_error<=1; end
                default: begin
                    index<=index+1;
                    if (index<14) crc<=crc_byte(crc,byte_data);
                    case (index)
                        2: if (byte_data!=1) header_ok<=0;
                        3: begin kill<=byte_data[0]; if (byte_data[7:1]!=0) header_ok<=0; end
                        4,5,6,7: quote_sequence[(index-4)*8 +: 8]<=byte_data;
                        8,9,10,11: price[(index-8)*8 +: 8]<=byte_data;
                        12: quantity[7:0]<=byte_data;
                        13: quantity[15:8]<=byte_data;
                        14: crc_low<=byte_data;
                        15: begin
                            index<=0;
                            if (header_ok && {byte_data,crc_low}==crc) quote_valid<=1;
                            else packet_error<=1;
                        end
                    endcase
                end
            endcase
        end else if (index!=0) idle_count<=idle_count+1;
    end
endmodule
