// Field: {{node.get_path()}}
logic [{{node.width-1}}:0] {{field_logic.get_storage_identifier(node, True)}};
{%- if node.get_property('paritycheck') %}
logic {{field_logic.get_parity_identifier(node, True)}};
{%- endif %}
logic [{{node.width-1}}:0] {{field_logic.get_field_combo_identifier(node, "next", True)}};
logic {{field_logic.get_field_combo_identifier(node, "load_next", True)}};
{%- if node.get_property('paritycheck') %}
logic {{field_logic.get_parity_error_identifier(node, True)}};
{%- endif %}
{%- for signal in extra_combo_signals %}
logic {{field_logic.get_field_combo_identifier(node, signal.name, True)}};
{%- endfor %}
{%- if node.is_up_counter %}
{%- if not field_logic.counter_incrsaturates(node) %}
logic {{field_logic.get_field_combo_identifier(node, "overflow", True)}};
{%- endif %}
logic {{field_logic.get_field_combo_identifier(node, "incrthreshold", True)}};
{%- if field_logic.counter_incrsaturates(node) %}
logic {{field_logic.get_field_combo_identifier(node, "incrsaturate", True)}};
{%- endif %}
{%- endif %}
{%- if node.is_down_counter %}
{%- if not field_logic.counter_decrsaturates(node) %}
logic {{field_logic.get_field_combo_identifier(node, "underflow", True)}};
{%- endif %}
logic {{field_logic.get_field_combo_identifier(node, "decrthreshold", True)}};
{%- if field_logic.counter_decrsaturates(node) %}
logic {{field_logic.get_field_combo_identifier(node, "decrsaturate", True)}};
{%- endif %}
{%- endif %}
