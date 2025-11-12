// Field: {{node.get_path()}}
{% if node.width > 1 %}
reg [{{node.width-1}}:0] {{field_logic.get_storage_identifier(node, True)}};
{% else %}
reg {{field_logic.get_storage_identifier(node, True)}};
{% endif %}
{%- if node.get_property('paritycheck') %}
reg {{field_logic.get_parity_identifier(node, True)}};
{%- endif %}
{%- if field_logic.has_next_q(node) %}
{% if node.width > 1 %}
reg [{{node.width-1}}:0] {{field_logic.get_next_q_identifier(node, True)}};
{% else %}
reg {{field_logic.get_next_q_identifier(node, True)}};
{% endif %}
{%- endif %}
{% if node.width > 1 %}
reg [{{node.width-1}}:0] {{field_logic.get_field_combo_identifier(node, "next", True)}};
{% else %}
reg {{field_logic.get_field_combo_identifier(node, "next", True)}};
{% endif %}
reg {{field_logic.get_field_combo_identifier(node, "load_next", True)}};
{%- if node.get_property('paritycheck') %}
reg {{field_logic.get_parity_error_identifier(node, True)}};
{%- endif %}
{%- for signal in extra_combo_signals %}
{% if signal.width > 1 %}
reg [{{signal.width-1}}:0] {{field_logic.get_field_combo_identifier(node, signal.name, True)}};
{% else %}
reg {{field_logic.get_field_combo_identifier(node, signal.name, True)}};
{% endif %}
{%- endfor %}
{%- if node.is_up_counter %}
{%- if not field_logic.counter_incrsaturates(node) %}
reg {{field_logic.get_field_combo_identifier(node, "overflow", True)}};
{%- endif %}
reg {{field_logic.get_field_combo_identifier(node, "incrthreshold", True)}};
{%- if field_logic.counter_incrsaturates(node) %}
reg {{field_logic.get_field_combo_identifier(node, "incrsaturate", True)}};
{%- endif %}
{%- endif %}
{%- if node.is_down_counter %}
{%- if not field_logic.counter_decrsaturates(node) %}
reg {{field_logic.get_field_combo_identifier(node, "underflow", True)}};
{%- endif %}
reg {{field_logic.get_field_combo_identifier(node, "decrthreshold", True)}};
{%- if field_logic.counter_decrsaturates(node) %}
reg {{field_logic.get_field_combo_identifier(node, "decrsaturate", True)}};
{%- endif %}
{%- endif %}
