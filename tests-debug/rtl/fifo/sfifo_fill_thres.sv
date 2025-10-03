module sfifo_fill_thres #(
      integer G_FWFT         = 0
    , integer G_MAX_MEMDEPTH = 1024
    , integer G_ADDRWIDTH    = $clog2(G_MAX_MEMDEPTH)
) (
      input                    clk
    , input                    rst
    , input                    wr_en
    , input                    rd_en
    , input  [G_ADDRWIDTH-1:0] memdepth
    , input  [G_ADDRWIDTH-1:0] prog
    , output                   full
    , output                   prog_level
    , output                   overflow
    , output                   empty
    , output                   underflow
    , output [G_ADDRWIDTH-1:0] raddr
    , output [G_ADDRWIDTH-1:0] waddr
);
    logic [  G_ADDRWIDTH:0] f_fill_level;
    logic [  G_ADDRWIDTH:0] d_fill_level;
    logic                   f_empty_dly;
    logic                   f_empty;
    logic                   d_empty;
    logic                   f_underflow;
    logic                   d_underflow;
    logic                   f_full;
    logic                   d_full;
    logic                   f_prog_level;
    logic                   d_prog_level;
    logic                   f_overflow;
    logic                   d_overflow;
    logic [G_ADDRWIDTH-1:0] f_raddr;
    logic [G_ADDRWIDTH-1:0] d_raddr;
    logic [G_ADDRWIDTH-1:0] f_waddr;
    logic [G_ADDRWIDTH-1:0] d_waddr;


    always @(posedge clk) begin
        if (~rst) begin
            f_fill_level <= 0;
            f_empty      <= 1;
            f_empty_dly  <= 1;
            f_underflow  <= 0;
        end else begin
            f_fill_level <= d_fill_level;
            f_empty      <= d_empty;
            f_empty_dly  <= f_empty;
            f_underflow  <= d_underflow;
        end
    end

    always @(posedge clk) begin
        if (~rst) begin
            f_full       <= 0;
            f_prog_level <= 0;
            f_overflow   <= 0;
        end else begin
            f_full       <= d_full;
            f_prog_level <= d_prog_level;
            f_overflow   <= d_overflow;
        end
    end

    always @(posedge clk) begin
        if (~rst) begin
            f_raddr <= 0;
            f_waddr <= 0;
        end else begin
            f_raddr <= d_raddr;
            f_waddr <= d_waddr;
        end
    end

    always @* begin
        d_fill_level = f_fill_level;
        d_raddr      = f_raddr;
        d_waddr      = f_waddr;

        if (rd_en && wr_en)
            if (0 == f_fill_level) begin
                d_fill_level = f_fill_level + 1;
                if (f_waddr == memdepth) d_waddr = 0;
                else d_waddr = f_waddr + 1;
            end else if (f_fill_level >= memdepth) begin
                d_fill_level = f_fill_level - 1;
                if (f_raddr == memdepth) d_raddr = 0;
                else d_raddr = f_raddr + 1;
            end else begin
                d_fill_level = f_fill_level;
                if (f_raddr == memdepth) d_raddr = 0;
                else d_raddr = f_raddr + 1;
                if (f_waddr == memdepth) d_waddr = 0;
                else d_waddr = f_waddr + 1;
            end
        else if (rd_en)
            if (0 == f_fill_level) d_fill_level = f_fill_level;
            else begin
                d_fill_level = f_fill_level - 1;
                if (f_waddr == memdepth) d_waddr = 0;
                else d_waddr = f_waddr + 1;
            end
        else if (wr_en)
            if (f_fill_level < memdepth) begin
                d_fill_level = f_fill_level + 1;
                if (f_raddr == memdepth) d_raddr = 0;
                else d_raddr = f_raddr + 1;
            end
        //else
        //    d_fill_level = f_fill_level;

    end

    always @* begin
        d_underflow = 0;
        if (rd_en && 0 == f_fill_level) d_underflow = 1;
    end

    always @* begin
        d_overflow = 0;
        if (wr_en && f_fill_level >= memdepth) d_overflow = 1;
    end

    always @* begin
        d_empty = f_empty;
        if (0 == d_fill_level) d_empty = 1;
        else d_empty = 0;
    end
    always @* begin
        d_full = f_full;
        if (d_fill_level >= memdepth) d_full = 1;
        else d_full = 0;
    end
    always @* begin
        d_prog_level = f_prog_level;
        if (d_fill_level >= prog) d_prog_level = 1;
        else d_prog_level = 0;
    end

    assign full       = f_full;
    assign prog_level = f_prog_level;
    assign overflow   = f_overflow;
    generate
        if (G_FWFT == 0) begin
            assign empty = f_empty;
        end else begin
            assign empty = f_empty | f_empty_dly;
        end
    endgenerate

    assign underflow = f_underflow;

    assign raddr     = f_raddr;
    assign waddr     = f_waddr;

endmodule
