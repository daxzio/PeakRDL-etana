module blockmem_dp (
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

    //(* ram_style = "block" *) reg [G_MEMWIDTH-1:0] f_ram [G_MEMDEPTH-1:0];
    (* ram_style = "block" *) reg [G_MEMWIDTH-1:0] f_ram [G_MEMDEPTH];
    reg [G_MEMWIDTH-1:0] f_douta;
    reg [G_MEMWIDTH-1:0] f_doutb;

    initial begin
        // synthesis translate_off
        for(integer x=0; x<G_MEMDEPTH; x=x+1) begin
            f_ram[x] = 0;
        end
        // synthesis translate_on
        if (G_INIT_FILE != "") begin
            $readmemh(G_INIT_FILE, f_ram);
        end
    end

    generate
    genvar a;
        for (a = 0 ; a < G_MEMWIDTH/8 ; a=a+1)
        begin : g_write_mema
            always @(posedge clka)
            begin
                if (ena & wea[a])
                    f_ram[addra][(8*a)+7:8*a] <= dina[(8*a)+7:8*a];
            end
        end
    endgenerate

    generate
    genvar b;
        for (b = 0 ; b < G_MEMWIDTH/8 ; b=b+1)
        begin : g_write_memb
            always @(posedge clkb)
            begin
                if (enb & web[b])
                    f_ram[addrb][(8*b)+7:8*b] <= dinb[(8*b)+7:8*b	];
            end
        end
    endgenerate

    always @(posedge clka) begin : g_read_mema
        // synthesis translate_off
        f_douta <= 0;
        // synthesis translate_on
        if (ena)
            f_douta <= f_ram[addra];
    end
    assign douta = f_douta;

    always @(posedge clkb) begin : g_read_memb
        // synthesis translate_off
        f_doutb <= 0;
        // synthesis translate_on
        if (enb)
            f_doutb <= f_ram[addrb];
    end
    assign doutb = f_doutb;

endmodule
