{% if retime -%}


always_ff {{get_always_ff_event(resetsignal)}} begin
    if({{get_resetsignal(resetsignal)}}) begin
        {{prefix}}_req <= '0;
        {{prefix}}_addr <= '0;
        {{prefix}}_req_is_wr <= '0;
{%- if is_sw_writable %}
{%- for inst_name in inst_names %}
        {{prefix}}{{inst_name}}_wr_data <= '0;
        {{prefix}}{{inst_name}}_wr_biten <= '0;
{%- endfor %}
{%- endif %}
    end else begin
        {{prefix}}_req <= {{strb.path}};
        {{prefix}}_addr <= decoded_addr[{{addr_width-1}}:0];
        {{prefix}}_req_is_wr <= decoded_req_is_wr;
{%- if is_sw_writable %}
{%- for inst_name in inst_names %}
        {{prefix}}{{inst_name}}_wr_data <= decoded_wr_data;
        {{prefix}}{{inst_name}}_wr_biten <= decoded_wr_biten;
{%- endfor %}
{%- endif %}
    end
end


{%- else -%}


always @(*) begin
    {{prefix}}_addr = decoded_addr[{{addr_width-1}}:0];
    {{prefix}}_req = {{strb.path}};
    {{prefix}}_req_is_wr = decoded_req_is_wr;
{%- if is_sw_writable %}
{%- for inst_name in inst_names %}
    {{prefix}}{{inst_name}}_wr_data = decoded_wr_data;
    {{prefix}}{{inst_name}}_wr_biten = decoded_wr_biten;
{%- endfor %}
{%- endif %}
end


{%- endif %}
