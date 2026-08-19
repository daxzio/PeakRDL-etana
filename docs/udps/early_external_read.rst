.. _early_external_read:

Early external read
===================

When ``early_external_read = true`` is set on an **external mem**, PeakRDL-etana
issues read requests to that memory combinationally during the CPU interface
address or SETUP phase, one cycle earlier than the default registered path.
This removes one wait state when the external slave is a block RAM with a
registered read port.

Compile the UDP definition from :download:`etana_udps.rdl <../../hdl-src/etana_udps.rdl>`
before your design, then enable it on the external memory:

.. code-block:: systemrdl

    external mem {
        early_external_read = true;
        memwidth = 32;
        mementries = 64;
        sw = rw;
    } ext_mem;

Default is ``false``. Designs without the UDP generate the same RTL as before.

Hardware contract
-----------------

When enabled, the user's external memory slave must obey:

- ``hwif_out_*_req`` for a read is a **single-cycle** strobe during the CPUIF
  address/SETUP phase.
- ``hwif_out_*_addr`` is valid in that same cycle.
- ``hwif_in_*_rd_ack`` and ``hwif_in_*_rd_data`` must be valid **exactly one
  cycle later**.
- Write behaviour is unchanged.

The latency contract is **exactly one** cycle, not "up to one". A
zero-latency (combinational) slave will deadlock in this mode.

Supported CPU interfaces
------------------------

Early read is only available on CPU interfaces that expose a stable address
phase before the registered request:

- APB3 / APB4
- OBI

Other CPU interfaces (AHB, AXI4-Lite, Avalon, passthrough, etc.) are rejected
at elaboration time if any mem enables this UDP.

Validation
----------

Export fails when:

- ``early_external_read`` is set on a component that is not an external ``mem``.
- The mem has no software-readable content.
- ``--rt-external mem`` is enabled for the same design.
- The selected CPU interface does not support early request.

A warning is emitted if read-path retiming (``--rt-read-fanin`` or
``--rt-read-response``) is also enabled, since that re-adds a cycle of read
latency.
