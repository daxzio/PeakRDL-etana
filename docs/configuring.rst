.. _peakrdl_cfg:

Configuring PeakRDL-etana
=========================

If using the `PeakRDL command line tool <https://peakrdl.readthedocs.io/>`_,
some aspects of the ``regblock`` command have additional configuration options
available via the PeakRDL TOML file.

All regblock-specific options are defined under the ``[regblock]`` TOML heading.

.. data:: cpuifs

    Mapping of additional CPU Interface implementation classes to load.
    The mapping's key indicates the cpuif's name.
    The value is a string that describes the import path and cpuif class to
    load.

    For example:

    .. code-block:: toml

        [regblock]
        cpuifs.my-cpuif-name = "my_cpuif_module:MyCPUInterfaceClass"


.. data:: default_reset

    Choose the default style of reset signal if not explicitly
    specified by the SystemRDL design. If unspecified, the default reset
    is active-high and synchronous.

    Choice of:

        * ``rst`` (default)
        * ``rst_n``
        * ``arst``
        * ``arst_n``

    For example:

    .. code-block:: toml

        [regblock]
        default_reset = "arst"


Command Line Options
====================

The following command-line options are available when using the PeakRDL command line tool:

CPU Interface Selection
-----------------------

.. option:: --cpuif <interface>

    Select the CPU interface protocol. Available options include:

    * ``apb3`` / ``apb3-flat`` - AMBA APB3 interface
    * ``apb4`` / ``apb4-flat`` - AMBA APB4 interface
    * ``ahb-flat`` - AMBA AHB interface
    * ``axi4-lite`` / ``axi4-lite-flat`` - AMBA AXI4-Lite interface
    * ``avalon-mm`` / ``avalon-mm-flat`` - Avalon Memory-Mapped interface
    * ``passthrough`` - Direct internal protocol passthrough

    The ``-flat`` suffix indicates flattened input/output ports instead of SystemVerilog interfaces.

Hardware Interface Customization
---------------------------------

.. option:: --in-str <prefix>

    Customize the prefix for hardware interface input signals. Default is ``hwif_in``.

    Example:

    .. code-block:: bash

        peakrdl etana design.rdl --in-str my_hw_in -o output/

.. option:: --out-str <prefix>

    Customize the prefix for hardware interface output signals. Default is ``hwif_out``.

    Example:

    .. code-block:: bash

        peakrdl etana design.rdl --out-str my_hw_out -o output/

Reset Configuration
-------------------

.. option:: --default-reset <style>

    Choose the default style of reset signal if not explicitly specified by the SystemRDL design.

    Choices:

    * ``rst`` - Synchronous, active-high (default)
    * ``rst_n`` - Synchronous, active-low
    * ``arst`` - Asynchronous, active-high
    * ``arst_n`` - Asynchronous, active-low

Pipeline Optimization
---------------------

.. option:: --rt-read-response

    Enable additional retiming stage between readback fan-in and CPU interface.
    This can improve timing for high-speed designs.

.. option:: --rt-external <targets>

    Retime outputs to external components. Specify a comma-separated list of targets:
    ``reg``, ``regfile``, ``mem``, ``addrmap``, or ``all``.

Address Map Configuration
-------------------------

.. option:: --flatten-nested-blocks

    Flatten nested ``regfile`` and ``addrmap`` components into the parent address space
    instead of treating them as external interfaces. Memory (``mem``) blocks always remain
    external per SystemRDL specification.

    When this option is enabled:

    * Nested regfile and addrmap components are integrated directly into the parent module
    * No external bus interfaces are generated for these components
    * All registers become directly accessible through the top-level CPU interface
    * Simplifies integration and improves tool compatibility
    * Reduces interface complexity for deeply nested designs

    **Example:**

    .. code-block:: systemrdl

        regfile config_regs {
            reg setting1 @ 0x0;
            reg setting2 @ 0x4;
        };

        addrmap top {
            config_regs cfg @ 0x1000;  // Without --flatten: external interface
                                        // With --flatten: integrated registers
        };

    **Use Cases:**

    * Simpler designs that don't need hierarchical external interfaces
    * Legacy tool compatibility where external interfaces cause issues
    * Flat address space requirements
    * Reduced port count in top-level module

    **Note:** Memory blocks (``mem``) are always treated as external regardless of this option,
    as they require specialized memory interfaces per SystemRDL specification.

Advanced Options
----------------

.. option:: --allow-wide-field-subwords

    Allow software-writable fields to span multiple subwords without write buffering.
    This bypasses SystemRDL specification rule 10.6.1-f and enables non-atomic writes
    to wide registers.
