.. _cdc:

CDC registers
=============

Registers in a different clock domain from the CPU interface use the ``cdc_clk``
property. Etana places storage in that domain and writes the toggle handshake
into the generated module. There is no separate handshake cell to compile.

Compile the Etana UDPs first: ``hdl-src/etana_udps.rdl`` (or your package copy),
including ``cdc_clk``, ``cdc_fast_mode_en``, and ``cdc_nstages``.

Properties
----------

cdc_clk
    ``reg`` reference to a ``signal``. All registers that reference the same
    signal share one handshake and one destination reset synchroniser. The signal
    becomes a clock input on the exported module. The clock ``signal`` must be
    declared in the same addrmap as the registers (not inside an arrayed regfile).

cdc_fast_mode_en
    Optional boolean on the CDC clock ``signal``. When true, the module has an
    input ``<clock>_fast_mode_en``. While that input is high, a posted write can
    complete without waiting for the return toggle. The destination clock must be
    fast enough that ``(cdc_nstages + 1) * T_dst`` plus logic delay fits inside
    one bus cycle. The input can change at runtime.

cdc_nstages
    Optional integer on the CDC clock ``signal`` (default 2, minimum 2). Number of
    synchroniser stages in each toggle crossing inside the handshake cell.

Atomic groups
-------------

Write and read atomicity reuse ``buffer_writes`` / ``wbuffer_trigger`` and
``buffer_reads`` / ``rbuffer_trigger``. On CDC registers, triggers must be CDC
registers in the **same** domain; group members must not be ``external``.

Write groups keep a bus-domain **shadow** per member (including each array
element). A write to the trigger performs a non-posted load of the concatenated
member image into the destination domain.

Read groups keep bus-domain **snapshot** registers per member. A read of the
trigger starts a CDC read; captured values appear in the snapshots and in
subsequent reads of member addresses. Snapshots reset to zero; reads before the
first successful trigger read return zero for members.

Register arrays
---------------

CDC registers may be arrays, including registers inside arrayed regfiles.
Catalog **slots** are flattened (one handshake index per array element for plain
registers). Buffered **triggers** must be scalar registers (not array instances,
not inside an arrayed regfile). Group members may be arrays; shadows, snapshots,
and slot indices use unpacked dimensions in the generated RTL.

Supported field usage
---------------------

CDC fields are restricted to simple software/hardware access:

* **Config (crossing):** ``sw`` = rw or w, ``hw`` = r or na — storage in the
  destination domain, accessed through the handshake.
* **Status:** ``sw`` = r, ``hw`` = w — sampled from ``hwif`` inputs; reads cross
  through the handshake when the register is a plain CDC register or a trigger.
* **Group members** must match the group kind (config members in write groups,
  status members in read groups).

A plain CDC register or a group trigger must have ``regwidth`` equal to
``accesswidth``. A group member may be wider: each subword updates its shadow
or is read from its snapshot, and the trigger access still moves the whole
member on one destination edge. Values such as counters,
interrupts, ``swacc`` / ``swmod``, ``onread`` / ``onwrite``, and similar field
properties are not allowed on CDC fields. Elaboration runs
``CdcDesignValidator``; negative cases are covered by ``tests/test_cdc_validate.py``.

Other rules
-----------

* CDC registers cannot be ``external`` or combined with ``--rt-external reg``.
* A clock ``signal`` cannot use CPU or field reset properties; only
  ``cdc_nstages`` and ``cdc_fast_mode_en`` are allowed on that signal.
* ``cdc_fast_mode_en`` applies only to a signal referenced by ``cdc_clk``.
* Field ``resetsignal`` in the domain may be OR-combined with the bus reset for
  the destination reset synchroniser input when it is in scope.

Stopped clocks
--------------

If a destination clock stops, bus accesses to its registers stall with no timeout.

Handshake and ``--sync-cell``
-----------------------------

The handshake state machine is part of the generated module. Bus-side flops use
the same ``always_ff`` event and active-high reset condition as the rest of the
regblock. Destination flops use the domain clock and an active-high ``dst_rst``
that stays asserted until the bus reset has crossed ``cdc_nstages`` destination
clocks.

By default each synchronizer is a shift register in that same module. Pass
``--sync-cell NAME`` to instantiate ``NAME`` instead, once per crossing. The
module must have ports ``q``, ``d``, ``clk``, and ``rst`` (``rst`` clears ``q``
while it is high) and a parameter ``NSTAGES``.

Tests
-----

Cocotb integration tests live under ``tests/test_cdc*`` (handshake, reset styles,
groups, arrays, fast mode). Rule and scanner checks: ``pytest tests/test_cdc_validate.py``.
