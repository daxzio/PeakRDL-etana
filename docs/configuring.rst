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

    Select the CPU interface protocol. All interfaces use **flattened signals** (individual ports)
    rather than SystemVerilog structs.

    Available options:

    * ``apb3-flat`` - AMBA APB3 interface (flattened signals)
    * ``apb4-flat`` - AMBA APB4 interface (flattened signals) **[default]**
    * ``ahb-flat`` - AMBA AHB interface (flattened signals)
    * ``axi4-lite-flat`` - AMBA AXI4-Lite interface (flattened signals)
    * ``avalon-mm-flat`` - Avalon Memory-Mapped interface (flattened signals)
    * ``passthrough`` - Direct internal protocol passthrough

    .. note::
        PeakRDL-etana **only supports flattened signal interfaces**. This is the key
        architectural difference from PeakRDL-regblock. All ``-flat`` variants use
        individual signal ports (e.g., ``s_apb_psel``, ``s_apb_pready``) instead of
        SystemVerilog interface types.

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

Error Response Configuration
----------------------------

.. option:: --err-if-bad-addr

    Generate error responses for accesses to unmapped addresses.

    When enabled, the CPU interface will signal an error (e.g., SLVERR, PSLVERR, HRESP)
    when software attempts to access an address that is not mapped to any register or memory.

    **Default:** Disabled (unmapped addresses return 0 for reads, ignore writes)

    **Supported CPU Interfaces:**

    * APB4: Asserts ``pslverr``
    * AXI4-Lite: Returns ``SLVERR`` on ``rresp``/``bresp``
    * AHB: Asserts ``hresp`` (ERROR response)
    * Passthrough: Asserts ``rd_err``/``wr_err``

    **Example:**

    .. code-block:: bash

        peakrdl etana design.rdl --cpuif apb4-flat --err-if-bad-addr -o output/

    **Use Cases:**

    * Debug invalid software access patterns
    * Enforce strict address map compliance
    * Detect software bugs at runtime
    * Meet safety-critical requirements

.. option:: --err-if-bad-rw

    Generate error responses for forbidden read/write operations.

    When enabled, the CPU interface will signal an error when:

    * Software attempts to **read** a write-only register
    * Software attempts to **write** a read-only register

    **Default:** Disabled (forbidden reads return 0, forbidden writes are ignored)

    **Supported CPU Interfaces:**

    * APB4: Asserts ``pslverr``
    * AXI4-Lite: Returns ``SLVERR`` on ``rresp``/``bresp``
    * AHB: Asserts ``hresp`` (ERROR response)
    * Passthrough: Asserts ``rd_err``/``wr_err``

    **Example:**

    .. code-block:: bash

        peakrdl etana design.rdl --cpuif apb4-flat --err-if-bad-rw -o output/

    **Use Cases:**

    * Catch software register access violations
    * Enforce register access policies
    * Validate software against hardware constraints
    * Improve system robustness

.. option:: --err-if-bad-addr --err-if-bad-rw

    Both options can be combined for comprehensive error checking:

    .. code-block:: bash

        peakrdl etana design.rdl --cpuif apb4-flat --err-if-bad-addr --err-if-bad-rw -o output/

    This configuration provides maximum error detection, signaling:

    * Unmapped address accesses
    * Forbidden read operations (write-only registers)
    * Forbidden write operations (read-only registers)

    **Testing:** Use the ``test_cpuif_err_rsp`` test to validate error response behavior
    across different CPU interfaces.

Advanced Options
----------------

.. option:: --allow-wide-field-subwords

    Allow software-writable fields to span multiple subwords without write buffering.
    This bypasses SystemRDL specification rule 10.6.1-f and enables non-atomic writes
    to wide registers.
