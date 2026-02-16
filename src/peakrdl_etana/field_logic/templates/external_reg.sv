{% if retime -%}


always_ff {{get_always_ff_event(resetsignal)}} begin
    if({{get_resetsignal(resetsignal)}}) begin
        {{prefix}}_req <= '0;
        {{prefix}}_req_is_wr <= '0;
    {%- if has_sw_writable %}
    {%- for inst_name in inst_names %}
        {{prefix}}_wr_data{{inst_name[0]}} <= '0;
        {{prefix}}_wr_biten{{inst_name[0]}} <= '0;
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
        // Zero-extend to CPUIF width to avoid Verilator width warnings.
        {{prefix}}_wr_data{{inst_name[0]}}{{index_str}} <= {{cpuif_data_width}}'(decoded_wr_data{{inst_name[1]}});
        {{prefix}}_wr_biten{{inst_name[0]}}{{index_str}} <= {{cpuif_data_width}}'(decoded_wr_biten{{inst_name[1]}});
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
assign {{prefix}}_req_is_wr{{index_str}} = decoded_req_is_wr;
{%- if has_sw_writable %}
{%- for inst_name in inst_names %}
// Zero-extend to CPUIF width to avoid Verilator width warnings.
assign {{prefix}}_wr_data{{inst_name[0]}}{{index_str}} = {{cpuif_data_width}}'(decoded_wr_data{{inst_name[1]}});
assign {{prefix}}_wr_biten{{inst_name[0]}}{{index_str}} = {{cpuif_data_width}}'(decoded_wr_biten{{inst_name[1]}});
{%- endfor %}
{%- endif %}


{%- endif %}
