{% if retime -%}


always_ff {{get_always_ff_event(resetsignal)}} begin
    if({{get_resetsignal(resetsignal)}}) begin
        {{prefix}}_req <= '0;
        {{prefix}}_addr <= '0;
{%- if is_sw_writable %}
        {{prefix}}_req_is_wr <= '0;
{%- for inst_name in inst_names %}
        {{prefix}}{{inst_name}}_wr_data <= '0;
        {{prefix}}{{inst_name}}_wr_biten <= '0;
{%- endfor %}
{%- endif %}
    end else begin
        {{prefix}}_req <= {{strb.path}};
        {{prefix}}_addr <= decoded_addr[{{addr_width-1}}:0];
{%- if is_sw_writable %}
        {{prefix}}_req_is_wr <= decoded_req_is_wr;
{%- for inst_name in inst_names %}
        {{prefix}}{{inst_name}}_wr_data <= decoded_wr_data;
        {{prefix}}{{inst_name}}_wr_biten <= decoded_wr_biten;
{%- endfor %}
{%- endif %}
    end
end


{%- else -%}

{%- if early %}
// early_external_read: read req is a single-cycle SETUP-phase strobe; rd_ack/rd_data
// must be valid exactly one cycle later. Zero-latency slaves will deadlock.
{%- endif %}

{%- if early %}
assign {{prefix}}_addr = {{early_strb.path}} ? cpuif_early_addr[{{addr_width-1}}:0]
                                        : decoded_addr[{{addr_width-1}}:0];
assign {{prefix}}_req = {{early_strb.path}} | ({{strb.path}} & decoded_req_is_wr);
{%- else %}
assign {{prefix}}_addr = decoded_addr[{{addr_width-1}}:0];
assign {{prefix}}_req = {{strb.path}};
{%- endif %}
{%- if is_sw_writable %}
assign {{prefix}}_req_is_wr = {{strb.path}} & decoded_req_is_wr;
{%- for inst_name in inst_names %}
assign {{prefix}}{{inst_name}}_wr_data = decoded_wr_data;
assign {{prefix}}{{inst_name}}_wr_biten = decoded_wr_biten;
{%- endfor %}
{%- endif %}


{%- endif %}
