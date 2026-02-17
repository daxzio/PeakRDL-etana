.. _err_support:

External Memory Error Support
==============================

When using an external memory (e.g., backing store with ECC), the memory may
detect errors (uncorrectable ECC, access failures, etc.) that should be
reported to the CPU interface. The ``err_support`` property adds ``rd_err`` and
``wr_err`` input ports to the external memory's hardware interface so the
external block can signal errors back.

Properties
---------
This UDP is defined in :download:`etana_udps.rdl <../../hdl-src/etana_udps.rdl>`.
Compile that file (along with any other UDP files) before your design.

.. describe:: err_support

    **Component:** mem

    **Type:** boolean

    When set on an external memory, adds the following input ports to the
    hardware interface:

    * ``hwif_in_<name>_rd_err`` – Asserted when ``rd_ack`` is high to indicate
      a read error (e.g., ECC uncorrectable)
    * ``hwif_in_<name>_wr_err`` – Asserted when ``wr_ack`` is high to indicate
      a write error

    These ports are valid only when ``err_support`` is true. When omitted or
    false, the ports are not generated.

Example
-------

.. code-block:: systemrdl

    external mem {
        memwidth = 64;
        mementries = 32768;
        err_support;
    } ECC @ 0x40000;

This generates ports:

.. code-block:: systemverilog

    input logic hwif_in_ecc_rd_data,
    input logic hwif_in_ecc_rd_ack,
    input logic hwif_in_ecc_rd_err,   // when err_support
    input logic hwif_in_ecc_wr_ack,
    input logic hwif_in_ecc_wr_err,  // when err_support

**Propagation:** When asserted (along with the corresponding ack), these signals
propagate to ``cpuif_rd_err``/``cpuif_wr_err`` and thus to the bus error
responses (e.g., APB ``pslverr``, AXI ``SLVERR``, AHB ``hresp``).
