module blockmem_dp_wrapper (
     clka
    ,ena
    ,wea
    ,addra
    ,dina
    ,douta
    ,clkb
    ,enb
    ,web
    ,addrb
    ,dinb
    ,doutb
    );
    parameter  integer G_MEMWIDTH  = 32;
    parameter  integer G_MEMDEPTH  = 1024;
    parameter          G_INIT_FILE = "" ;
    parameter  integer G_USEIP     = 0 ;
    localparam integer G_ADDRWIDTH = $clog2(G_MEMDEPTH);
    localparam integer G_WEWIDTH   = ((G_MEMWIDTH-1)/8)+1;

    input                    clka;
    input                    ena;
    input  [G_WEWIDTH-1:0]   wea;
    input  [G_ADDRWIDTH-1:0] addra;
    input  [G_MEMWIDTH-1:0]  dina;
    output [G_MEMWIDTH-1:0]  douta;
    input                    clkb;
    input                    enb;
    input  [G_WEWIDTH-1:0]   web;
    input  [G_ADDRWIDTH-1:0] addrb;
    input  [G_MEMWIDTH-1:0]  dinb;
    output [G_MEMWIDTH-1:0]  doutb;


    if (0 == G_USEIP) begin
        blockmem_dp #(
            .G_MEMWIDTH  (G_MEMWIDTH),
            .G_MEMDEPTH  (G_MEMDEPTH),
            .G_INIT_FILE (G_INIT_FILE)
        )
        i_blockmem_dp (
            .clka       ( clka  ),
            .ena        ( ena   ),
            .wea        ( wea   ),
            .addra      ( addra ),
            .dina       ( dina  ),
            .douta      ( douta ),
            .clkb       ( clkb  ),
            .enb        ( enb   ),
            .web        ( web   ),
            .addrb      ( addrb ),
            .dinb       ( dinb  ),
            .doutb      ( doutb )
        );
    end else begin
        blockmem_dp #(
            .G_MEMWIDTH  (G_MEMWIDTH),
            .G_MEMDEPTH  (G_MEMDEPTH),
            .G_INIT_FILE (G_INIT_FILE)
        )
        i_blockmem_dp (
            .clka       ( clka  ),
            .ena        ( ena   ),
            .wea        ( wea   ),
            .addra      ( addra ),
            .dina       ( dina  ),
            .douta      ( douta ),
            .clkb       ( clkb  ),
            .enb        ( enb   ),
            .web        ( web   ),
            .addrb      ( addrb ),
            .dinb       ( dinb  ),
            .doutb      ( doutb )
        );
    end

endmodule
