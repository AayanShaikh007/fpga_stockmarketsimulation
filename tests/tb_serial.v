`timescale 1ns/1ps
module tb_serial;
    parameter CPB=16;
    parameter HOST_CPB=CPB;
    localparam TIMEOUT=CPB*40;
    reg clk=0, rst=1, rx=1;
    always #5 clk=~clk;
    wire tx,error_latched,killed;
    nanoquant_core #(.CLKS_PER_BIT(CPB),.TIMEOUT_CLKS(TIMEOUT)) dut(
        clk,rst,rx,tx,error_latched,killed);
    integer fd,status,cmd,value,i;
    reg [1023:0] path;
    task send_byte;
        input [7:0] b;
        input good_stop;
        integer k;
        begin
            rx=0; repeat(HOST_CPB) @(negedge clk);
            for(k=0;k<8;k=k+1) begin rx=b[k]; repeat(HOST_CPB) @(negedge clk); end
            rx=good_stop; repeat(HOST_CPB) @(negedge clk);
            rx=1;
        end
    endtask
    // Independent host-side bit sampler, not another instance of uart_rx.
    reg [7:0] captured;
    integer b;
    initial forever begin
        @(negedge tx);
        repeat(CPB+CPB/2) @(posedge clk);
        for(b=0;b<8;b=b+1) begin
            captured[b]=tx;
            repeat(CPB) @(posedge clk);
        end
        if(tx!==1) $fatal(1,"TX stop bit invalid");
        $display("BYTE %02x",captured);
    end
    always @(posedge clk) begin
        if(!rst && dut.result_valid)
            $display("ENGINE %0d %0d %0d",dut.order,dut.position,killed);
    end
    initial begin
        if(!$value$plusargs("INPUT=%s",path)) $fatal(1,"missing input");
        fd=$fopen(path,"r"); if(!fd) $fatal(1,"input open failed");
        repeat(5) @(negedge clk); rst=0;
        while(!$feof(fd)) begin
            status=$fscanf(fd,"%d %d\n",cmd,value);
            if(status!=2) $fatal(1,"invalid command");
            case(cmd)
                0: send_byte(value,1);
                1: repeat(value) @(negedge clk);
                2: begin rst=1; repeat(5) @(negedge clk); rst=0; end
                3: send_byte(value,0);
                4: begin rx=0; @(negedge clk); rx=1; repeat(CPB*2) @(negedge clk); end
                default: $fatal(1,"unknown command");
            endcase
        end
        repeat(CPB*250) @(negedge clk);
        $display("ERROR %0d",error_latched);
        $finish;
    end
endmodule
