AMBA AHB
========

Implements the register block using an AMBA AHB (Advanced High-performance Bus) CPU
interface. The AHB interface is intended for **shared bus systems** where multiple
masters and slaves connect through an arbiter. It supports pipelined transfers with
stall handling via ``HREADY``.

The AHB CPU interface provides **flattened signal interface** (individual input/output
ports):

* Command line: ``--cpuif ahb-flat``
* Class: :class:`peakrdl_etana.cpuif.ahb.AHB_Cpuif_flattened`

.. note::
    PeakRDL-etana uses flattened signals exclusively. There are no SystemVerilog
    struct-based interface options.

.. warning::
    Like other CPU interfaces in this exporter, the AHB ``HADDR`` input is interpreted
    as a byte-address. Address values should be byte-aligned according to the data
    width being used (e.g., for 32-bit transfers, addresses increment in steps of 4).

Supported Signals
-----------------

The AHB interface includes the following signals (prefix ``s_ahb_``):

Request signals (inputs):
    * ``s_ahb_hsel`` - Slave select (from decoder)
    * ``s_ahb_htrans[1:0]`` - Transfer type (NONSEQ, SEQ, IDLE, BUSY)
    * ``s_ahb_hwrite`` - Write enable (1 = write, 0 = read)
    * ``s_ahb_hsize[2:0]`` - Transfer size
    * ``s_ahb_haddr`` - Byte address
    * ``s_ahb_hwdata`` - Write data bus

Response signals (outputs):
    * ``s_ahb_hready`` - Transfer complete; when low, the transfer is extended (stalled)
    * ``s_ahb_hrdata`` - Read data bus
    * ``s_ahb_hresp`` - Transfer response (0 = OKAY, 1 = ERROR)

HREADY and Stall Handling
-------------------------

The slave drives ``HREADY`` low when it cannot complete the transfer in the current
cycle (e.g., waiting for external register/memory acknowledgements, or for write data).
When ``HREADY`` is low, the master must hold address and control signals stable. For
shared bus systems, proper stall handling is essential. See the standalone AHB
interface specification document for detailed requirements.

Error Response Support
---------------------

The AHB interface supports error signaling via the ``HRESP`` response signal. When error
response options are enabled:

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

Testing
-------

The ``test_ahb_pipeline`` test validates the AHB interface, including read/write
operations to internal and external registers and multi-cycle external memory access.

References
----------

* `AMBA 3 AHB-Lite Protocol Specification (ARM IHI 0033) <https://developer.arm.com/documentation/ihi0033/latest/>`_
* `AMBA 5 AHB Protocol Specification <https://developer.arm.com/documentation/ihi0033/latest/>`_
