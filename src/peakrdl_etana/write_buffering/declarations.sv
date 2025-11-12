reg {{wbuf_prefix}}_pending;
{% if regwidth > 1 %}
reg [{{regwidth-1}}:0] {{wbuf_prefix}}_data;
reg [{{regwidth-1}}:0] {{wbuf_prefix}}_biten;
{% else %}
reg {{wbuf_prefix}}_data;
reg {{wbuf_prefix}}_biten;
{% endif %}
{%- if is_own_trigger %}
reg {{wbuf_prefix}}_trigger_q;
{%- endif %}
