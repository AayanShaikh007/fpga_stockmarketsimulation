`timescale 1ns/1ps
module tb_engine;
    reg clk=0;
    always #5 clk=~clk;
    reg rst=1, in_valid=0, kill=0;
    reg [31:0] price=0;
    reg [15:0] quantity=0;
    wire out_valid, killed;
    wire signed [31:0] order, position;
    engine dut(clk,rst,in_valid,price,quantity,kill,out_valid,order,position,killed);
    integer fd, status, r, v, k;
    reg [1023:0] path;
    initial begin
        if (!$value$plusargs("VECTORS=%s",path)) $fatal(1,"missing VECTORS");
        fd=$fopen(path,"r");
        if (!fd) $fatal(1,"cannot open vectors");
        @(negedge clk);
        while (!$feof(fd)) begin
            status=$fscanf(fd,"%d %d %d %d %d\n",r,v,price,quantity,k);
            if (status != 5) $fatal(1,"bad vector");
            rst=r; in_valid=v; kill=k;
            @(posedge clk); #1;
            $display("RESULT %0d %0d %0d %0d",out_valid,order,position,killed);
            @(negedge clk);
        end
        $fclose(fd);
        $finish;
    end
endmodule
