AMBA AHB
========

Implements the register block using an
`AMBA AHB <https://developer.arm.com/documentation/ihi0033/latest/>`_
(Advanced High-performance Bus) CPU interface.

.. note::
    The AHB interface implementation provides a simplified subset of the full AHB protocol,
    optimized for register access. It supports single transfers with configurable data widths.

The AHB CPU interface provides **flattened signal interface** (individual input/output ports):

* Command line: ``--cpuif ahb-flat``
* Class: :class:`peakrdl_etana.cpuif.ahb.AHB_Cpuif_flattened`

.. note::
    PeakRDL-etana uses flattened signals exclusively. There are no SystemVerilog
    struct-based interface options.

.. warning::
    Like other CPU interfaces in this exporter, the AHB ``HADDR`` input is interpreted
    as a byte-address. Address values should be byte-aligned according to the data width
    being used (e.g., for 32-bit transfers, addresses increment in steps of 4).

Supported Signals
-----------------

The AHB interface implementation includes the following signals:

Command signals (inputs):
    * ``HSEL`` - Slave select signal
    * ``HWRITE`` - Write enable (1 = write, 0 = read)
    * ``HTRANS[1:0]`` - Transfer type
    * ``HSIZE[2:0]`` - Transfer size
    * ``HADDR`` - Address bus
    * ``HWDATA`` - Write data bus

Response signals (outputs):
    * ``HRDATA`` - Read data bus
    * ``HREADY`` - Transfer complete indicator
    * ``HRESP`` - Transfer response (error status)

Error Response Support
----------------------

AHB supports error signaling via the ``HRESP`` response signal. When error response
options are enabled:

**--err-if-bad-addr**
    Asserts ``HRESP`` (ERROR = 1) when software accesses an unmapped address

**--err-if-bad-rw**
    Asserts ``HRESP`` (ERROR = 1) when:

    * Software attempts to read a write-only register
    * Software attempts to write a read-only register

**Example:**

.. code-block:: bash

    peakrdl etana design.rdl --cpuif ahb-flat --err-if-bad-addr --err-if-bad-rw -o output/

**Response Values:**

* ``HRESP = 0`` (OKAY) - Normal successful completion
* ``HRESP = 1`` (ERROR) - Error response (when error options enabled)

**Testing:** The ``test_cpuif_err_rsp`` test validates AHB error responses
across various error scenarios.
