Wishbone Bus
============

Implements the register block using a
`Wishbone B4 <https://cdn.opencores.org/downloads/wbspec_b4.pdf>`_
CPU interface.

PeakRDL-etana uses flattened signals exclusively (no SystemVerilog interface
port option).

Flattened inputs/outputs
    Flattens the interface into discrete input and output ports.

    * Command line: ``--cpuif wishbone-flat``
    * Class: :class:`peakrdl_etana.cpuif.wishbone.Wishbone_Cpuif_flattened`

Signal Interface
----------------

**Inputs:**

* ``wb_cyc`` - Cycle (input, not connected; placeholder per B4 Classic)
* ``wb_stb`` - Strobe (input)
* ``wb_we`` - Write enable (input)
* ``wb_adr`` - Address (input)
* ``wb_odat`` - Write data (input)
* ``wb_sel`` - Byte strobes (input)

**Outputs:**

* ``wb_stall`` - Stall (output)
* ``wb_ack`` - Acknowledge (output)
* ``wb_err`` - Error response (output)
* ``wb_idat`` - Read data (output)

Implementation Details
----------------------
This implementation of the Wishbone protocol has the following features:

* Classic Wishbone operations (SINGLE_READ and SINGLE_WRITE)
* Stall and error optional output signals

Note that the ``cyc`` signal is not connected and it is a placeholder, since it
is redundant in wishbone classic operations. Commands are captured based on
``stb``.

Error Response Support
----------------------

When ``--err-if-bad-addr`` or ``--err-if-bad-rw`` is enabled, ``wb_err`` is
asserted for error conditions.

Usage Example
-------------

.. code-block:: bash

   peakrdl etana my_registers.rdl --cpuif wishbone-flat -o output_dir/

   peakrdl etana my_registers.rdl --cpuif wishbone-flat \
       --err-if-bad-addr --err-if-bad-rw -o output_dir/

Integration Notes
-----------------

* Requires ``cocotbext-wishbone`` for Cocotb-based testing
* **Known issue (tracked):** On error responses, generated RTL currently asserts both
  ``wb_ack`` and ``wb_err``, which violates Wishbone B4 mutual-exclusion rules.
  Etana Cocotb tests use a wrapper workaround; see ``UPSTREAM_SYNC_STATUS.md`` item 30
  for upstream feedback details.
