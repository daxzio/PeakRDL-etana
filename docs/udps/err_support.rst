.. _err_support:

External Memory Error Support
==============================

When using an external memory (e.g., backing store with ECC), the memory may
detect errors (uncorrectable ECC, access failures, etc.) that should be
reported to the CPU interface. The ``err_support`` property enables error
propagation for external memories by adding ``rd_err`` and ``wr_err`` input
ports and an internal ``inflight_value`` signal for request tracking.

Properties
----------
This UDP is defined in :download:`etana_udps.rdl <../../hdl-src/etana_udps.rdl>`.
Compile that file (along with any other UDP files) before your design.

.. describe:: err_support

    **Component:** mem

    **Type:** boolean

    When set on an external memory, enables the following:

    * **Input ports** – The external block can signal errors back:

      * ``hwif_in_<name>_rd_err`` – Assert when ``rd_ack`` is high to indicate
        a read error (e.g., ECC uncorrectable)
      * ``hwif_in_<name>_wr_err`` – Assert when ``wr_ack`` is high to indicate
        a write error

    * **Internal signal** – ``<name>_inflight_value`` – A flopped signal that
      stays high from address decode strobe until the corresponding ack. Used
      to qualify error propagation (only report errors for in-flight requests).

    These ports and logic are generated only when ``err_support`` is true on
    the memory. When omitted or false, they are not generated.

Address-Range Semantics
-----------------------

Error propagation is **address-range aware**:

* **Memory with err_support** – When you read or write an address in this
  memory's range and the external block signals an error (with ack), the
  bus error response is asserted (e.g., APB ``pslverr``, AHB ``hresp``).

* **Memory without err_support** – Accesses to this memory's range *never*
  trigger a bus error response, regardless of any other conditions.

This ensures that only memories explicitly configured for error reporting
can drive bus error signals.

Propagation Logic
-----------------

**Read errors:** Propagated when ``rd_ack``, ``rd_err``, and ``inflight_value``
are all high. The ``inflight_value`` qualification prevents spurious errors
from being reported when no request was in flight.

**Write errors:** Propagated when ``wr_ack`` and ``wr_err`` are both high.

The ``inflight_value`` signal is generated per memory with ``err_support``.
It is set when the address decode strobe (``decoded_reg_strb_<name>``) is
asserted, and cleared when the corresponding ack is received. For read-only
memories, it clears on ``rd_ack``; for write-only, on ``wr_ack``; for
read-write memories, on ``rd_ack | wr_ack``.

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

    input logic [31:0] hwif_in_ecc_rd_data,
    input logic hwif_in_ecc_rd_ack,
    input logic hwif_in_ecc_rd_err,   // when err_support
    input logic hwif_in_ecc_wr_ack,
    input logic hwif_in_ecc_wr_err,  // when err_support

And internal logic:

.. code-block:: systemverilog

    logic ecc_inflight_value;
    always_ff @(posedge clk) begin
        if (rst) begin
            ecc_inflight_value <= 1'h0;
        end else if (hwif_in_ecc_rd_ack | hwif_in_ecc_wr_ack) begin
            ecc_inflight_value <= 1'h0;
        end else if (decoded_reg_strb_ecc) begin
            ecc_inflight_value <= 1'h1;
        end
    end

**Propagation:** When asserted (and qualified), these signals propagate to
``cpuif_rd_err``/``cpuif_wr_err`` and thus to the bus error responses
(e.g., APB ``pslverr``, AXI ``SLVERR``, AHB ``hresp``).
