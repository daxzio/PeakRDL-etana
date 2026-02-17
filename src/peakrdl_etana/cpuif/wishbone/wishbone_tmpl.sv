
// Wishbone B4 Classic slave: single-cycle, non-pipelined.
// When CYC_I & STB_I, capture request and drive cpuif_*; assert ACK_O on completion.
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
            if({{cpuif.signal("cyc")}} && {{cpuif.signal("stb")}}) begin
                is_active <= 1'b1;
                cpuif_req <= 1'b1;
                cpuif_req_is_wr <= {{cpuif.signal("we")}};
                {%- if cpuif.data_width_bytes == 1 %}
                cpuif_addr <= {{cpuif.signal("adr")}}[{{cpuif.addr_width-1}}:0];
                {%- else %}
                cpuif_addr <= { {{cpuif.signal("adr")}}[{{cpuif.addr_width-1}}:{{clog2(cpuif.data_width_bytes)}}], {{clog2(cpuif.data_width_bytes)}}'b0 };
                {%- endif %}
                cpuif_wr_data <= {{cpuif.signal("dat_wr")}};
                for(int i=0; i<{{cpuif.data_width_bytes}}; i++) begin
                    cpuif_wr_biten[i*8 +: 8] <= {8{ {{cpuif.signal("sel")}}[i] }};
                end
            end
        end else begin
            cpuif_req <= 1'b0;
            if(cpuif_rd_ack || cpuif_wr_ack) begin
                is_active <= 1'b0;
            end
        end
    end
end

// Response: ACK and ERR are mutually exclusive per Wishbone B4 spec
assign {{cpuif.signal("ack")}} = (cpuif_rd_ack | cpuif_wr_ack) & ~(cpuif_rd_err | cpuif_wr_err);
assign {{cpuif.signal("err")}} = cpuif_rd_err | cpuif_wr_err;
assign {{cpuif.signal("dat_rd")}} = cpuif_rd_data;
