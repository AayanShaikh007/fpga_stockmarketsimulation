`timescale 1ns/1ps
module tb_action_leds;
    reg clk=0, rst=1, valid=0, killed=0, error_latched=0;
    reg signed [31:0] order=0;
    wire [5:0] led;
    always #5 clk=~clk;
    action_leds #(.PULSE_CLKS(3)) dut(clk,rst,valid,order,killed,error_latched,led);
    task tick;
        begin @(posedge clk); #1; end
    endtask
    task expect_led;
        input [5:0] expected;
        begin
            if (led!==expected) $fatal(1,"LED mismatch: got %b expected %b",led,expected);
        end
    endtask
    initial begin
        tick; expect_led(6'b111111);
        @(negedge clk); rst=0; valid=1; order=20;
        tick; expect_led(6'b111100); // buy + activity
        @(negedge clk); valid=0;
        tick; expect_led(6'b111100);
        tick; expect_led(6'b111100);
        tick; expect_led(6'b111111); // pulse expires
        @(negedge clk); valid=1; order=-20;
        tick; expect_led(6'b111010); // sell + activity
        @(negedge clk); order=0;
        tick; expect_led(6'b110010); // independent hold and sell pulses
        @(negedge clk); rst=1;
        tick; expect_led(6'b111111);
        @(negedge clk); rst=0; killed=1;
        tick; expect_led(6'b101110); // killed result is activity, not hold
        @(negedge clk); valid=0; error_latched=1;
        repeat(3) tick;
        expect_led(6'b001111); // persistent kill + error
        @(negedge clk); rst=1;
        tick; expect_led(6'b111111);
        $display("LED checks passed"); $finish;
    end
endmodule
