create_clock -name clk -period 37.037 [get_ports {clk}]
# Async external signals enter synchronizers; paths between synchronizer stages remain timed.
set_false_path -from [get_ports {uart_rx rst_n}]
