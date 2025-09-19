logic {{wbuf_prefix}}_pending;
logic [{{regwidth-1}}:0] {{wbuf_prefix}}_data;
logic [{{regwidth-1}}:0] {{wbuf_prefix}}_biten;
logic {{wbuf_prefix}}_trigger_q;
always_ff {{get_always_ff_event(cpuif.reset)}} begin
    if({{get_resetsignal(cpuif.reset)}}) begin
        {{wbuf_prefix}}_pending <= '0;
        {{wbuf_prefix}}_data <= '0;
        {{wbuf_prefix}}_biten <= '0;
        {%- if is_own_trigger %}
        {{wbuf_prefix}}_trigger_q <= '0;
        {%- endif %}
    end else begin
        if({{wbuf.get_trigger(node)}}) begin
            {{wbuf_prefix}}_pending <= '0;
            {{wbuf_prefix}}_data <= '0;
            {{wbuf_prefix}}_biten <= '0;
        end
        {%- for segment in segments %}
        if({{segment.strobe}} && decoded_req_is_wr) begin
            {{wbuf_prefix}}_pending <= '1;
            {%- if node.inst.is_msb0_order %}
            {{wbuf_prefix}}_data{{segment.bslice}} <= ({{wbuf_prefix}}_data{{segment.bslice}} & ~decoded_wr_biten_bswap) | (decoded_wr_data_bswap & decoded_wr_biten_bswap);
            {{wbuf_prefix}}_biten{{segment.bslice}} <= {{wbuf_prefix}}_biten{{segment.bslice}} | decoded_wr_biten_bswap;
            {%- else %}
            {{wbuf_prefix}}_data{{segment.bslice}} <= ({{wbuf_prefix}}_data{{segment.bslice}} & ~decoded_wr_biten) | (decoded_wr_data & decoded_wr_biten);
            {{wbuf_prefix}}_biten{{segment.bslice}} <= {{wbuf_prefix}}_biten{{segment.bslice}} | decoded_wr_biten;
            {%- endif %}
        end
        {%- endfor %}
        {%- if is_own_trigger %}
        {{wbuf_prefix}}_trigger_q <= {{wbuf.get_raw_trigger(node)}};
        {%- endif %}
    end
end
