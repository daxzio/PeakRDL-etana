logic {{wbuf_prefix}}_pending;
logic [{{regwidth-1}}:0] {{wbuf_prefix}}_data;
logic [{{regwidth-1}}:0] {{wbuf_prefix}}_biten;
{%- if is_own_trigger %}
logic {{wbuf_prefix}}_trigger_q;
{%- endif %}
