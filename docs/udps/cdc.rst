.. _cdc:

CDC registers
=============

Registers in a different clock domain from the CPU interface use the ``cdc_clk``
property. Etana owns the storage flops in that domain and crosses each access
through one toggle-handshake cell per domain.

Compile the etana UDPs first, including ``cdc_clk``, ``cdc_fast``, and
``cdc_nstages``.

Properties
----------

cdc_clk
    ``reg`` reference to a ``signal``. Registers that share the same signal
    share one handshake cell and one reset synchronizer. The signal becomes a
    module clock input.

cdc_fast
    Optional boolean on the clock ``signal``. When true, the handshake cell acks
    without waiting for the return toggle. The destination clock must be fast
    enough that ``(NSTAGES + 1) * T_dst`` plus path delay fits in one bus cycle.

cdc_nstages
    Optional integer on the clock ``signal`` (default 2, minimum 2). Number of
    synchronizer stages in each toggle crossing.

Atomic groups
-------------

Write and read atomicity reuse ``buffer_writes`` / ``wbuffer_trigger`` and
``buffer_reads`` / ``rbuffer_trigger``. On CDC registers, triggers must be CDC
registers in the same domain.

Write groups keep a bus-domain shadow per member. A write to the trigger performs
a non-posted load of every member into the destination domain on one edge.

Read groups capture every member into bus-domain snapshot registers when the
trigger is read. Snapshots reset to zero; reads before the first capture return
zero.

Restrictions (phase 1)
----------------------

* ``regwidth`` must equal ``accesswidth``.
* Register arrays are not supported.
* No combination with ``external`` or ``--rt-external reg``.
* Simplified field access only (no counters, interrupts, ``swacc``, etc.).

Stopped clocks
--------------

If a destination clock stops, bus accesses to its registers stall with no
timeout.

CDC cells
---------

Blocks with CDC registers instantiate a handshake and a synchronizer whose names
follow the design reset from ``--default-reset``:

+-------------------+----------------------------+------------------------------+
| ``--default-reset`` | Handshake                | Synchronizer                 |
+===================+============================+==============================+
| ``rst``           | ``etana_cdc_rst``          | ``etana_cdc_sync_rst``       |
+-------------------+----------------------------+------------------------------+
| ``rst_n``         | ``etana_cdc_rst_n``        | ``etana_cdc_sync_rst_n``     |
+-------------------+----------------------------+------------------------------+
| ``arst``          | ``etana_cdc_arst``         | ``etana_cdc_sync_arst``      |
+-------------------+----------------------------+------------------------------+
| ``arst_n``        | ``etana_cdc_arst_n``       | ``etana_cdc_sync_arst_n``    |
+-------------------+----------------------------+------------------------------+

The bus-side reset port has that same name, and the bus-side flops use the same
sensitivity list as the rest of the regblock. ``rst`` and ``rst_n`` are
synchronous. ``arst`` is ``posedge``, ``arst_n`` is ``negedge``.

The toggle synchronizer into the destination clock, and the destination flops
inside the handshake, always use ``etana_cdc_sync_arst`` and ``dst_rst``.
``dst_rst`` is active-high: it is the inverted synchronizer output, so it is
asserted while the bus reset is asserted and releases ``G_STAGES`` destination
clocks later. A block that is not ``arst`` still needs ``etana_cdc_sync_arst.sv``
on the file list for that path.

The cells ship with the package in ``peakrdl_etana/cdc/``:

.. code-block:: bash

    python -c "import peakrdl_etana.cdc as c; print(c.CDC_CELL_DIR)"

Export does not write them by default. Pass ``--cdc-emit-cells`` to copy the
cells for this design's reset into the output directory. If several blocks are
exported with this flag, include only one copy of each file, or the simulator
will report duplicate modules.

To use your own synchronizer, leave out ``etana_cdc_sync_<reset>.sv`` and provide
a module with the same name, ports ``q``, ``d``, ``clk`` and ``<reset>``, and
parameter ``G_STAGES``. ``<reset>`` must clear ``q`` while it is asserted.

A field ``resetsignal`` in the domain is combined with the bus reset in that
reset's polarity and connected to the same port.
