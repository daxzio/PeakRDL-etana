{% if retime -%}


always_ff {{get_always_ff_event(resetsignal)}} begin
    if({{get_resetsignal(resetsignal)}}) begin
        {{prefix}}_req{{index_str}} <= '0;
        {{prefix}}_addr{{index_str}} <= '0;
{%- if is_sw_writable %}
        {{prefix}}_req_is_wr{{index_str}} <= '0;
{%- for inst_name in inst_names %}
        {{prefix}}{{inst_name}}_wr_data{{index_str}} <= '0;
        {{prefix}}{{inst_name}}_wr_biten{{index_str}} <= '0;
{%- endfor %}
{%- endif %}
    end else begin
        {{prefix}}_req{{index_str}} <= {{strb.path}}{{index_str}};
        {{prefix}}_addr{{index_str}} <= decoded_addr[{{addr_width-1}}:0];
{%- if is_sw_writable %}
        {{prefix}}_req_is_wr{{index_str}} <= decoded_req_is_wr;
{%- for inst_name in inst_names %}
        {{prefix}}{{inst_name}}_wr_data{{index_str}} <= decoded_wr_data;
        {{prefix}}{{inst_name}}_wr_biten{{index_str}} <= decoded_wr_biten;
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
assign {{prefix}}_addr{{index_str}} = {{early_strb.path}}{{index_str}} ? cpuif_early_addr[{{addr_width-1}}:0]
                                        : decoded_addr[{{addr_width-1}}:0];
assign {{prefix}}_req{{index_str}} = {{early_strb.path}}{{index_str}} | ({{strb.path}}{{index_str}} & decoded_req_is_wr);
{%- else %}
assign {{prefix}}_addr{{index_str}} = decoded_addr[{{addr_width-1}}:0];
assign {{prefix}}_req{{index_str}} = {{strb.path}}{{index_str}};
{%- endif %}
{%- if is_sw_writable %}
assign {{prefix}}_req_is_wr{{index_str}} = {{strb.path}}{{index_str}} & decoded_req_is_wr;
{%- for inst_name in inst_names %}
assign {{prefix}}{{inst_name}}_wr_data{{index_str}} = decoded_wr_data;
assign {{prefix}}{{inst_name}}_wr_biten{{index_str}} = decoded_wr_biten;
{%- endfor %}
{%- endif %}


{%- endif %}
