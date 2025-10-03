module tb;
    timeunit 1ps;
    timeprecision 1ps;

    // Clock and reset
    logic clk = 0;
    logic rst = 1;

    // HWIF signals - flattened for PeakRDL-etana
    {%- for signal in exporter.hwif.logic %}
    {%- if "input" in signal %}
    {%- set signal_name = signal.split()[3] %}
    {%- set signal_width = signal.split()[2] %}
    logic {{signal_width}} {{signal_name}};
    {%- endif %}
    {%- endfor %}
    {%- for signal in exporter.hwif.logic %}
    {%- if "output" in signal %}
    {%- set signal_name = signal.split()[3] %}
    {%- set signal_width = signal.split()[2] %}
    logic {{signal_width}} {{signal_name}};
    {%- endif %}
    {%- endfor %}

    // CPU interface signals (Icarus-compatible)
    wire s_apb_psel;
    wire s_apb_penable;
    wire s_apb_pwrite;
    wire [2:0] s_apb_pprot;
    wire [4:0] s_apb_paddr;
    wire [31:0] s_apb_pwdata;
    wire [3:0] s_apb_pstrb;
    wire s_apb_pready;
    wire [31:0] s_apb_prdata;
    wire s_apb_pslverr;

    // APB4 driver module (Icarus-compatible)
    apb4_intf_driver #(
        .DATA_WIDTH(32),
        .ADDR_WIDTH(5)
    ) cpuif (
        .clk(clk),
        .rst(rst),
        .PSEL(s_apb_psel),
        .PENABLE(s_apb_penable),
        .PWRITE(s_apb_pwrite),
        .PPROT(s_apb_pprot),
        .PADDR(s_apb_paddr),
        .PWDATA(s_apb_pwdata),
        .PSTRB(s_apb_pstrb),
        .PRDATA(s_apb_prdata),
        .PREADY(s_apb_pready),
        .PSLVERR(s_apb_pslverr)
    );

    // DUT instantiation
    regblock dut (
        .clk(clk),
        .rst(rst),
        // HWIF signals (flattened for PeakRDL-etana)
        {%- for signal in exporter.hwif.logic %}
        {%- set signal_name = signal.split()[3] %}
        .{{signal_name}}({{signal_name}}),
        {%- endfor %}
        // CPU interface signals (Icarus-compatible - explicit connections)
        .s_apb_psel(s_apb_psel),
        .s_apb_pwrite(s_apb_pwrite),
        .s_apb_penable(s_apb_penable),
        .s_apb_pprot(s_apb_pprot),
        .s_apb_paddr(s_apb_paddr),
        .s_apb_pwdata(s_apb_pwdata),
        .s_apb_pstrb(s_apb_pstrb),
        .s_apb_pready(s_apb_pready),
        .s_apb_prdata(s_apb_prdata),
        .s_apb_pslverr(s_apb_pslverr)
    );
    `line 99 "lib/tb_base.sv" 0

    // Test sequence - Verilator-compatible (no timing delays)
    initial begin
        // Initialize HWIF signals
        {%- for signal in exporter.hwif.logic %}
        {%- if "input" in signal %}
        {%- set signal_name = signal.split()[3] %}
        {{signal_name}} <= '0;
        {%- endif %}
        {%- endfor %}

        // Wait for reset to be released by C++ main
        wait(rst == 0);

        // Test sequence
        begin
            {%- filter indent(8) %}
            {%- block seq %}
            {%- endblock %}
            {%- endfilter %}
        end

        // Finish simulation
        $finish();
    end

    // Monitor for timeout - Verilator-compatible
    initial begin
        repeat(5000) @(posedge clk);
        $fatal(1, "Test timed out after 5000 clock cycles");
    end

    // VCD dump - Verilator-compatible
    initial begin
        if ($test$plusargs("vcd")) begin
            $dumpfile("tb.vcd");
            $dumpvars(0, tb);
        end
    end

endmodule
