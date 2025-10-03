module dut (
     clk
    ,resetn
    ,din
    ,wr_en
    ,rd_en
    ,dout
    ,full
    ,overflow
    ,empty
    ,underflow
    ,wr_rst_busy
    ,rd_rst_busy
    );

    input          clk;
    input          resetn;
    input  [15:0]  din;
    input          wr_en;
    input          rd_en;
    output  [15:0] dout;
    output         full;
    output         overflow;
    output         empty;
    output         underflow;
    output         wr_rst_busy;
    output         rd_rst_busy;

    wire srst;
    wire rst;

    assign srst =  ~resetn;
    assign rst =  ~resetn;

    fifo_wrapper
    #(
        .G_USE_IP    (1),
        .G_DATAWIDTH (16),
        .G_MEMDEPTH  (16)
    )
    i_fifo_wrapper (
        .*
    );

    `ifdef COCOTB_SIM
    initial begin
        $dumpfile ("dut.vcd");
        $dumpvars (0, dut);
        #1;
    end
    `endif


endmodule
