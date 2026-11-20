{%- if cpuif.is_interface -%}
`ifndef SYNTHESIS
    initial begin
        assert_bad_addr_width: assert($bits({{cpuif.signal("adr")}}) >= {{cpuif.addr_width}})
            else $error("Interface address width of %0d is too small. Shall be at least %0d bits", $bits({{cpuif.signal("adr")}}), {{cpuif.addr_width}});
        assert_bad_data_width: assert($bits({{cpuif.signal("odat")}}) == {{ds.package_name}}::{{ds.module_name.upper()}}_DATA_WIDTH)
            else $error("Interface data width of %0d is incorrect. Shall be %0d bits", $bits({{cpuif.signal("odat")}}), {{ds.package_name}}::{{ds.module_name.upper()}}_DATA_WIDTH);
    end
`endif

{% endif -%}

// Request — pulse cpuif_req like APB. Combinational stb cannot be used with
// cpuif_req_masked / external_pending: stb stays high until ack while stall
// would drop the CDC request mid-handshake.
logic is_active;
always_ff {{get_always_ff_event(cpuif.reset)}} begin
    if({{get_resetsignal(cpuif.reset)}}) begin
        is_active <= '0;
        cpuif_req <= '0;
        cpuif_req_is_wr <= '0;
        cpuif_addr <= '0;
        cpuif_wr_data <= '0;
        cpuif_wr_biten <= '0;
    end else begin
        if(~is_active) begin
            if({{cpuif.signal("cyc")}} & {{cpuif.signal("stb")}}) begin
                is_active <= '1;
                cpuif_req <= '1;
                cpuif_req_is_wr <= {{cpuif.signal("we")}};
                {%- if cpuif.data_width_bytes == 1 %}
                cpuif_addr <= {{cpuif.signal("adr")}}[{{cpuif.addr_width-1}}:0];
                {%- else %}
                cpuif_addr <= { {{cpuif.signal("adr")}}[{{cpuif.addr_width-1}}:{{clog2(cpuif.data_width_bytes)}}], {{clog2(cpuif.data_width_bytes)}}'b0};
                {%- endif %}
                cpuif_wr_data <= {{cpuif.signal("odat")}};
                for(int i=0; i<{{cpuif.data_width_bytes}}; i++) begin
                    cpuif_wr_biten[i*8 +: 8] <= {8{ {{cpuif.signal("sel")}}[i]}};
                end
            end
        end else begin
            cpuif_req <= '0;
            if(cpuif_rd_ack || cpuif_wr_ack) begin
                is_active <= '0;
            end
        end
    end
end

// Stall through reset. Pipelined Wishbone (this master has a stall pin) treats
// stall=0 as an accepted cycle and drops stb. Reset swallows that cycle, so
// the request must stay stalled until the slave can capture it.
// After accept, ~is_active drops stall so a pending CDC transfer does not
// hold the master in _wait_stall.
assign {{cpuif.signal("stall")}} = {{get_resetsignal(cpuif.reset)}}
                                | (~is_active
                                & ((cpuif_req_stall_rd & ~{{cpuif.signal("we")}})
                                | (cpuif_req_stall_wr & {{cpuif.signal("we")}})));

// Response
assign {{cpuif.signal("ack")}} = is_active & (cpuif_rd_ack | cpuif_wr_ack);
assign {{cpuif.signal("idat")}} = cpuif_rd_data;
assign {{cpuif.signal("err")}} = is_active & (cpuif_rd_err | cpuif_wr_err);
