module passthrough_driver #(
        parameter DATA_WIDTH = 32,
        parameter ADDR_WIDTH = 32
    )(
        input wire clk,
        input wire rst,

        output logic m_cpuif_req,
        output logic m_cpuif_req_is_wr,
        output logic [ADDR_WIDTH-1:0] m_cpuif_addr,
        output logic [DATA_WIDTH-1:0] m_cpuif_wr_data,
        output logic [DATA_WIDTH-1:0] m_cpuif_wr_biten,
        input wire m_cpuif_req_stall_wr,
        input wire m_cpuif_req_stall_rd,
        input wire m_cpuif_rd_ack,
        input wire m_cpuif_rd_err,
        input wire [DATA_WIDTH-1:0] m_cpuif_rd_data,
        input wire m_cpuif_wr_ack,
        input wire m_cpuif_wr_err
    );

    timeunit 1ps;
    timeprecision 1ps;

    task automatic reset();
        m_cpuif_req <= '0;
        m_cpuif_req_is_wr <= '0;
        m_cpuif_addr <= '0;
        m_cpuif_wr_data <= '0;
        m_cpuif_wr_biten <= '0;
    endtask

    task automatic write(input logic [ADDR_WIDTH-1:0] addr, input logic [DATA_WIDTH-1:0] data);
        @(posedge clk);
        m_cpuif_req <= '1;
        m_cpuif_req_is_wr <= '1;
        m_cpuif_addr <= addr;
        m_cpuif_wr_data <= data;
        m_cpuif_wr_biten <= {DATA_WIDTH{1'b1}};

        @(posedge clk);
        while (m_cpuif_req_stall_wr) begin
            @(posedge clk);
        end

        m_cpuif_req <= '0;
        m_cpuif_req_is_wr <= '0;
        m_cpuif_addr <= '0;
        m_cpuif_wr_data <= '0;
        m_cpuif_wr_biten <= '0;

        @(posedge clk);
        while (!m_cpuif_wr_ack && !m_cpuif_wr_err) begin
            @(posedge clk);
        end

        if (m_cpuif_wr_err) begin
            $error("Write transaction failed at address 0x%h", addr);
        end
    endtask

    task automatic read(input logic [ADDR_WIDTH-1:0] addr, output logic [DATA_WIDTH-1:0] data);
        @(posedge clk);
        m_cpuif_req <= '1;
        m_cpuif_req_is_wr <= '0;
        m_cpuif_addr <= addr;
        m_cpuif_wr_data <= '0;
        m_cpuif_wr_biten <= '0;

        @(posedge clk);
        while (m_cpuif_req_stall_rd) begin
            @(posedge clk);
        end

        m_cpuif_req <= '0;
        m_cpuif_req_is_wr <= '0;
        m_cpuif_addr <= '0;
        m_cpuif_wr_data <= '0;
        m_cpuif_wr_biten <= '0;

        @(posedge clk);
        while (!m_cpuif_rd_ack && !m_cpuif_rd_err) begin
            @(posedge clk);
        end

        if (m_cpuif_rd_err) begin
            $error("Read transaction failed at address 0x%h", addr);
            data = 'x;
        end else begin
            data = m_cpuif_rd_data;
        end
    endtask

    task automatic assert_read(input logic [ADDR_WIDTH-1:0] addr, input logic [DATA_WIDTH-1:0] expected_data, input logic [DATA_WIDTH-1:0] mask = {DATA_WIDTH{1'b1}});
        logic [DATA_WIDTH-1:0] actual_data;
        read(addr, actual_data);
        if ((actual_data & mask) !== (expected_data & mask)) begin
            $error("Read from 0x%h returned 0x%h. Expected 0x%h (mask 0x%h)", addr, actual_data, expected_data, mask);
        end
    endtask

endmodule
