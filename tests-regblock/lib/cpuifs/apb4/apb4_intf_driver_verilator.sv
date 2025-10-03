module apb4_intf_driver #(
        parameter DATA_WIDTH = 32,
        parameter ADDR_WIDTH = 32
    )(
        input wire clk,
        input wire rst,
        // APB4 interface signals (Verilator-compatible)
        output logic PSEL,
        output logic PENABLE,
        output logic PWRITE,
        output logic [2:0] PPROT,
        output logic [ADDR_WIDTH-1:0] PADDR,
        output logic [DATA_WIDTH-1:0] PWDATA,
        output logic [DATA_WIDTH/8-1:0] PSTRB,
        input wire [DATA_WIDTH-1:0] PRDATA,
        input wire PREADY,
        input wire PSLVERR
    );

    timeunit 1ps;
    timeprecision 1ps;

    task automatic reset();
        PSEL <= '0;
        PENABLE <= '0;
        PWRITE <= '0;
        PPROT <= '0;
        PADDR <= '0;
        PWDATA <= '0;
        PSTRB <= '0;
    endtask

    task automatic write(logic [ADDR_WIDTH-1:0] addr, logic [DATA_WIDTH-1:0] data, logic [DATA_WIDTH/8-1:0] strb = {DATA_WIDTH/8{1'b1}});
        // Verilator-compatible: use blocking assignments and wait for clock
        PSEL = '1;
        PENABLE = '0;
        PWRITE = '1;
        PPROT = '0;
        PADDR = addr;
        PWDATA = data;
        PSTRB = strb;

        // Wait for clock edge
        @(posedge clk);

        // Active phase
        PENABLE = '1;
        @(posedge clk);

        // Wait for response
        while(PREADY !== 1'b1) @(posedge clk);
        reset();
    endtask

    task automatic read(logic [ADDR_WIDTH-1:0] addr, output logic [DATA_WIDTH-1:0] data);
        // Verilator-compatible: use blocking assignments and wait for clock
        PSEL = '1;
        PENABLE = '0;
        PWRITE = '0;
        PPROT = '0;
        PADDR = addr;
        PWDATA = '0;
        PSTRB = '0;

        // Wait for clock edge
        @(posedge clk);

        // Active phase
        PENABLE = '1;
        @(posedge clk);

        // Wait for response
        while(PREADY !== 1'b1) @(posedge clk);
        assert(!$isunknown(PRDATA)) else $error("Read from 0x%0x returned X's on PRDATA", addr);
        data = PRDATA;
        reset();
    endtask

    task automatic assert_read(logic [ADDR_WIDTH-1:0] addr, logic [DATA_WIDTH-1:0] expected, logic [DATA_WIDTH-1:0] mask = {DATA_WIDTH{1'b1}});
        logic [DATA_WIDTH-1:0] actual;
        read(addr, actual);
        if ((actual & mask) !== (expected & mask)) begin
            $error("Read from 0x%0x returned 0x%0x. Expected 0x%0x", addr, actual, expected);
            $stop;
        end
    endtask

    // Initialize on reset
    initial begin
        reset();
    end

endmodule
