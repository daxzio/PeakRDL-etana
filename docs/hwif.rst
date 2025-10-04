Hardware Interface
------------------

The generated register block presents the hardware interface using **flattened signal ports** instead of SystemVerilog structs. Each field input, output, and signal becomes an individual port with a descriptive name.

This flattened approach has the following benefits:

* **No struct dependencies** - Easier integration with tools that don't support SystemVerilog structs
* **Clear signal naming** - Each signal has a self-descriptive hierarchical name
* **Tool compatibility** - Works with all synthesis and simulation tools
* **Direct connectivity** - Signals can be connected directly without struct unpacking
* **Simplified debugging** - Individual signals are easier to trace in waveforms

Signal Naming Convention
^^^^^^^^^^^^^^^^^^^^^^^^^

Signals follow the pattern: ``{direction}_{hierarchical_path}_{feature}``

* **Direction**: ``hwif_in`` for inputs to the register block, ``hwif_out`` for outputs (customizable via ``--in-str`` and ``--out-str``)
* **Hierarchical path**: Underscore-separated path through the design hierarchy
* **Feature**: Signal purpose (value, we, wr_ack, etc.)

Customizing Signal Prefixes
""""""""""""""""""""""""""""

The default prefixes (``hwif_in`` and ``hwif_out``) can be customized using command-line options:

.. code-block:: bash

    # Use custom prefixes
    peakrdl etana design.rdl --in-str my_in --out-str my_out -o output/

    # Results in signals like:
    # input wire [7:0] my_in_reg_field,
    # output logic [7:0] my_out_reg_data,

**Options:**

* ``--in-str <prefix>`` - Customize the prefix for input signals (default: ``hwif_in``)
* ``--out-str <prefix>`` - Customize the prefix for output signals (default: ``hwif_out``)

Example
^^^^^^^

For a simple design such as:

.. code-block:: systemrdl

        addrmap my_design {
            reg {
                field {
                    sw = rw;
                    hw = rw;
                    we;
                } my_field[7:0];
            } my_reg[2];
        };

... results in the following individual signal ports:

.. code-block:: systemverilog

    // Field value outputs (hardware can read current value)
    output logic [7:0] hwif_out_my_reg_0_my_field,
    output logic [7:0] hwif_out_my_reg_1_my_field,

    // Field value inputs (hardware can write next value)
    input wire [7:0] hwif_in_my_reg_0_my_field,
    input wire [7:0] hwif_in_my_reg_1_my_field,

    // Write enable inputs
    input wire hwif_in_my_reg_0_my_field_we,
    input wire hwif_in_my_reg_1_my_field_we,

Signal Types
^^^^^^^^^^^^

Field Value Signals
"""""""""""""""""""
* **Output (hwif_out_*)**: Current stored value of the field (if hardware readable)
* **Input (hwif_in_*)**: Next value for the field (if hardware writable)

Control Signals
"""""""""""""""
* **Write Enable (hwif_in_*_we)**: Enables hardware write to field
* **Clear/Set (hwif_in_*_hwclr/hwset)**: Hardware clear/set strobes
* **Counter (hwif_in_*_incr/decr)**: Counter increment/decrement strobes

Event Signals
"""""""""""""
* **Access Events (hwif_out_*_swacc/swmod)**: Software access/modify strobes
* **Reductions (hwif_out_*_anded/ored/xored)**: Bitwise reduction outputs

External Signals
""""""""""""""""
User-defined signals are included with their original names (with keyword filtering if needed).

MSB0 Field Support
^^^^^^^^^^^^^^^^^^

Fields with MSB0 bit ordering (``[low:high]`` notation) are automatically handled with appropriate bit swapping logic. The hardware interface signals maintain the same width and meaning regardless of internal bit ordering.

For brevity in this documentation, hwif features will be described using shorthand
notation that omits the hierarchical path: ``hwif_out_*`` and ``hwif_in_*``
