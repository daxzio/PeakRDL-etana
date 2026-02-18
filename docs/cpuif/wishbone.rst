Wishbone B4 Classic
===================

Wishbone B4 is an open, flexible interconnect bus protocol. This implementation
provides a single-cycle, non-pipelined Classic slave interface suitable for
register block connectivity.

Wishbone Protocol Overview
--------------------------

Wishbone B4 Classic uses a simple handshake:

**Request Phase:**
  - Master asserts ``cyc`` (cycle) and ``stb`` (strobe) to indicate a valid transaction
  - ``we`` indicates write (1) or read (0)
  - ``adr`` carries the address
  - ``dat_wr`` and ``sel`` provide write data and byte strobes

**Response Phase:**
  - Slave asserts ``ack`` on successful completion
  - Slave asserts ``err`` on error (optional, mutually exclusive with ``ack``)
  - ``dat_rd`` provides read data

Wishbone-Flat
-------------

Implements the register block using a Wishbone B4 Classic CPU interface with
**flattened signal interface** (individual input/output ports).

* Command line: ``--cpuif wishbone-flat``
* Class: :class:`peakrdl_etana.cpuif.wishbone.Wishbone_Cpuif_flattened`

Signal Interface
~~~~~~~~~~~~~~~~

**Inputs:**

* ``s_wb_cyc`` - Cycle valid (input)
* ``s_wb_stb`` - Strobe (input)
* ``s_wb_we`` - Write enable (input)
* ``s_wb_adr`` - Address (input)
* ``s_wb_dat_wr`` - Write data (input)
* ``s_wb_sel`` - Byte strobes (input)

**Outputs:**

* ``s_wb_ack`` - Acknowledge (output)
* ``s_wb_err`` - Error response (output)
* ``s_wb_dat_rd`` - Read data (output)

Features
--------

**Single-Cycle Transactions:**
  Non-pipelined B4 Classic mode; each transaction completes in one cycle after
  the request is captured.

**Byte Strobes:**
  Per-byte write enables through the ``sel`` signal enable partial word writes.

**Optional Error Signaling:**
  When ``--err-if-bad-addr`` or ``--err-if-bad-rw`` is enabled, ``err`` is
  asserted for error conditions per Wishbone B4 spec (ACK and ERR mutually exclusive).

Error Response Support
----------------------

The Wishbone interface supports error signaling via the ``s_wb_err`` signal. When
error response options are enabled:

**--err-if-bad-addr**
    Asserts ``s_wb_err`` when software accesses an unmapped address

**--err-if-bad-rw**
    Asserts ``s_wb_err`` when:

    - Writing to a read-only register
    - Reading from a write-only register

Usage Example
-------------

.. code-block:: bash

   # Generate register block with Wishbone interface
   peakrdl etana my_registers.rdl --cpuif wishbone-flat -o output_dir/

   # Enable error responses
   peakrdl etana my_registers.rdl --cpuif wishbone-flat \
       --err-if-bad-addr --err-if-bad-rw -o output_dir/

Integration Notes
-----------------

* The interface follows Wishbone B4 (Classic) specification
* Address is byte-addressed and aligned to the data width
* ACK and ERR are mutually exclusive per B4 spec
* Requires ``cocotbext-wishbone`` for Cocotb-based testing

.. note::
    PeakRDL-etana uses flattened signals exclusively. There are no SystemVerilog
    struct-based interface options.
