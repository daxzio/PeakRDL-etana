.. _verilog_reg_only:

Vectorized Register Interface
==============================

By default, PeakRDL-etana generates individual hardware interface signals for each
field within a register. While this provides fine-grained control, it can result in
a large number of signals at the top-level interface, especially for registers with
many fields.

The ``verilog_reg_only`` property provides a way to simplify the top-level hardware
interface by grouping all fields within a register into a single vectorized signal.
This is particularly useful when:

* Integrating with external modules that expect register-level (not field-level) interfaces
* Reducing top-level signal count for registers with many small fields
* Matching existing hardware interfaces with vectorized register signals

Properties
----------
This UDP definition, along with others supported by PeakRDL-etana can be
enabled by compiling the following file along with your design:
:download:`regblock_udps.rdl <../../hdl-src/regblock_udps.rdl>`.

.. describe:: verilog_reg_only

    **Component:** reg

    **Type:** boolean

    If set to true on a register, the hardware interface generates a single vector
    signal for the entire register instead of individual signals for each field.

    **For hw-writable fields:** A single input vector ``hwif_in_<register>`` is
    generated with width equal to the highest field bit position + 1.

    **For hw-readable fields:** A single output vector ``hwif_out_<register>`` is
    generated with width equal to the highest field bit position + 1.

    Internally, the generator automatically creates the necessary logic to break up
    the input vector into individual field signals and combine individual field
    outputs into the output vector.


Example
-------

Without ``verilog_reg_only``:

.. code-block:: systemrdl

    reg config_reg {
        field {} power_off[1];
        field {} polarity[1];
        field {} response[1];
        field {} serial[1];
        field {} operation[1];
    };

Generates individual field signals:

.. code-block:: systemverilog

    module design (
        input  wire i_config_reg_power_off,
        input  wire i_config_reg_polarity,
        input  wire i_config_reg_response,
        input  wire i_config_reg_serial,
        input  wire i_config_reg_operation,
        // ...
    );

With ``verilog_reg_only``:

.. code-block:: systemrdl

    reg config_reg {
        verilog_reg_only;  // Enable vectorized interface
        field {} power_off[1];
        field {} polarity[1];
        field {} response[1];
        field {} serial[1];
        field {} operation[1];
    };

Generates a single vector signal:

.. code-block:: systemverilog

    module design (
        input  wire [4:0] i_config_reg,
        // ...
    );

    // Internal signal breakup (automatically generated)
    logic i_config_reg_power_off;
    logic i_config_reg_polarity;
    logic i_config_reg_response;
    logic i_config_reg_serial;
    logic i_config_reg_operation;

    assign i_config_reg_power_off  = i_config_reg[0];
    assign i_config_reg_polarity   = i_config_reg[1];
    assign i_config_reg_response   = i_config_reg[2];
    assign i_config_reg_serial     = i_config_reg[3];
    assign i_config_reg_operation  = i_config_reg[4];


Behavior
--------

**Vector Width:** The width of the generated vector is calculated based on the
highest bit position of the hw-writable (for inputs) or hw-readable (for outputs)
fields, not the full register width. This ensures the vector is only as wide as
necessary.

**Unused Bits:** If there are gaps in the field layout (unused bits), these are
automatically filled with ``1'b0`` in the output vector combination logic.

**Field Logic:** All field-level logic (counters, interrupts, sw access, etc.)
operates on the internal field signals, ensuring full compatibility with existing
field properties and behaviors.

**Array Registers:** The property works correctly with register arrays, generating
appropriate unpacked array dimensions for the vectorized signals.


Limitations
-----------

* The ``verilog_reg_only`` property only affects the top-level hardware interface.
  Internal register logic remains unchanged.
* External registers are not affected by this property as they use bus protocol
  interfaces instead of field-level signals.
* The property applies to the entire register - you cannot selectively vectorize
  individual fields within a register.
