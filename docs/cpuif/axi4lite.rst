.. _cpuif_axi4lite:

AMBA AXI4-Lite
==============

Implements the register block using an
`AMBA AXI4-Lite <https://developer.arm.com/documentation/ihi0022/e/AMBA-AXI4-Lite-Interface-Specification>`_
CPU interface with **flattened signal interface** (individual input/output ports).

* Command line: ``--cpuif axi4-lite-flat``
* Class: :class:`peakrdl_etana.cpuif.axi4lite.AXI4Lite_Cpuif_flattened`

.. note::
    PeakRDL-etana uses flattened signals exclusively. There are no SystemVerilog
    struct-based interface options.


Pipelined Performance
---------------------
This implementation of the AXI4-Lite interface supports transaction pipelining
which can significantly improve performance of back-to-back transfers.

In order to support transaction pipelining, the CPU interface will accept multiple
concurrent transactions. The number of outstanding transactions allowed is automatically
determined based on the register file pipeline depth (affected by retiming options),
and influences the depth of the internal transaction response skid buffer.

Error Response Support
----------------------

AXI4-Lite supports error signaling via the ``RRESP`` and ``BRESP`` response signals.
When error response options are enabled:

**--err-if-bad-addr**
    Returns ``SLVERR`` (0b10) on ``RRESP``/``BRESP`` when software accesses an unmapped address

**--err-if-bad-rw**
    Returns ``SLVERR`` (0b10) when:

    * Software attempts to read a write-only register (``RRESP``)
    * Software attempts to write a read-only register (``BRESP``)

**Example:**

.. code-block:: bash

    peakrdl etana design.rdl --cpuif axi4-lite-flat --err-if-bad-addr --err-if-bad-rw -o output/

**Response Values:**

* ``0b00`` (OKAY) - Normal successful completion
* ``0b10`` (SLVERR) - Error response (when error options enabled)

**Testing:** The ``test_cpuif_err_rsp`` test validates AXI4-Lite error responses
across various error scenarios.
