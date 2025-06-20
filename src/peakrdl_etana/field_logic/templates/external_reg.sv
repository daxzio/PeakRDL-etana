{% if retime -%}


always_ff {{get_always_ff_event(resetsignal)}} begin
    if({{get_resetsignal(resetsignal)}}) begin
        {{prefix}}_req <= '0;
        {{prefix}}_req_is_wr <= '0;
    {%- if has_sw_writable %}
    {%- for inst_name in inst_names %}
        {{prefix}}{{inst_name[0]}}_wr_data <= '0;
        {{prefix}}{{inst_name[0]}}_wr_biten <= '0;
    {%- endfor %}
    {%- endif %}
    end else begin
    {%- if has_sw_readable and has_sw_writable %}
        {{prefix}}_req{{index_str}} <= {{strb}};
    {%- elif has_sw_readable and not has_sw_writable %}
        {{prefix}}_req{{index_str}} <= !decoded_req_is_wr ? {{strb}}{{index_str}} : '0;
    {%- elif not has_sw_readable and has_sw_writable %}
        {{prefix}}_req{{index_str}} <= decoded_req_is_wr ? {{strb}}{{index_str}} : '0;
    {%- endif %}
        {{prefix}}_req_is_wr{{index_str}} <= decoded_req_is_wr;
    {%- if has_sw_writable %}
    {%- for inst_name in inst_names %}
        {{prefix}}{{inst_name[0]}}_wr_data{{index_str}} = decoded_wr_data{{inst_name[1]}};
        {{prefix}}{{inst_name[0]}}_wr_biten{{index_str}} = decoded_wr_biten{{inst_name[1]}};
    {%- endfor %}
    {%- endif %}
    end
end


{%- else -%}


{%- if has_sw_readable and has_sw_writable %}
assign {{prefix}}_req{{index_str}} = {{strb}}{{index_str}};
{%- elif has_sw_readable and not has_sw_writable %}
assign {{prefix}}_req{{index_str}} = !decoded_req_is_wr ? {{strb}}{{index_str}}: '0;
{%- elif not has_sw_readable and has_sw_writable %}
assign {{prefix}}_req{{index_str}} = decoded_req_is_wr ? {{strb}}{{index_str}} : '0;
{%- endif %}
{%- if has_sw_writable %}
assign {{prefix}}_req_is_wr{{index_str}} = decoded_req_is_wr;
{%- for inst_name in inst_names %}
assign {{prefix}}{{inst_name[0]}}_wr_data{{index_str}} = decoded_wr_data{{inst_name[1]}};
assign {{prefix}}{{inst_name[0]}}_wr_biten{{index_str}} = decoded_wr_biten{{inst_name[1]}};
{%- endfor %}
{%- endif %}


{%- endif %}
