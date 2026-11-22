.. _cdc:

CDC registers
=============

A register with the ``cdc_clk`` property stores its fields in a clock domain
other than the CPU interface clock. Etana generates the storage flops in that
domain and carries each bus access across with a toggle handshake. The
handshake, the synchronizers and the storage are part of the generated module.
Export writes no other module.

Compile the etana UDPs first. They define ``cdc_clk``, ``cdc_nstages`` and
``cdc_fast_mode_en``.

Properties
----------

cdc_clk
    Property on ``reg``. A reference to a ``signal``. Registers that name the
    same signal form one domain with one handshake. The signal becomes a module
    input, named after the signal instance, and is the domain clock. The signal
    may be declared outside the exported addrmap. A signal is a domain clock
    only because a register names it. The signal must be one bit wide,
    not an array, and must not set ``cpuif_reset``, ``field_reset``,
    ``activelow``, ``activehigh``, ``sync`` or ``async``. Nothing else may
    reference it, for example as a ``resetsignal`` or a ``next``.

    The export ignores a ``cdc_clk`` register inside an external ``addrmap`` or
    ``regfile``. The export of that block generates the register and its
    handshake. A signal that only such registers name is an ordinary signal in
    this export and becomes the input ``hwif_in_<signal>``.

cdc_nstages
    Property on the clock ``signal``. Integer, default 2, minimum 2. The number
    of flops in each synchronizer of the domain.

cdc_fast_mode_en
    Property on the clock ``signal``. Boolean, default false. When true, the
    module gets the input ``<clk>_fast_mode_en`` (see `Fast mode`_). Export
    prints a warning that states the timing bound.

``cdc_nstages`` and ``cdc_fast_mode_en`` are errors on a signal that no
register names in ``cdc_clk``.

Handshake
---------

Each domain has one handshake that carries one register access at a time. The
bus side issues a request, which toggles a request flop. The request crosses
to the domain clock through a synchronizer. The domain performs the access on
one domain clock edge and toggles an acknowledge flop. The acknowledge crosses
back to the bus clock through a second synchronizer. The CPU interface stalls
from the request until the acknowledge.

A write to a plain register is posted: the handshake takes the write data and
the CPU interface completes the write in one bus cycle. A second access that
arrives while the handshake is busy waits in a one-entry pending slot, so
accesses reach the domain in order. A read, and a write to a group trigger,
complete when the acknowledge returns.

With ``cdc_nstages`` equal to N, T_dst the domain clock period and T_bus the bus
clock period, a read takes at least N + 2 and at most
N + 2 + ceil((N + 2) * T_dst / T_bus) bus cycles, counted from request to
acknowledge, both inclusive. A write to a group trigger takes the same time.

If a domain clock stops, an access to a register in that domain stalls the bus
with no timeout.

Fast mode
---------

Fast mode is a run-time input of a domain with ``cdc_fast_mode_en``. The input
``<clk>_fast_mode_en`` follows the clock input in the port list. For the clock
``sync_clk`` it is ``sync_clk_fast_mode_en``. The bus clock samples it.

With the input at 0, the handshake waits for the acknowledge toggle, as
described above. With the input at 1, the handshake completes an access without
waiting for the acknowledge, so a read or a trigger write takes 2 bus cycles.
The input exists so that one generated module serves two targets: a fast domain
clock with the input at 1, and a slower domain clock, for example in emulation,
with the input at 0.

With the input at 1, the domain clock must satisfy::

    (NSTAGES + 1) * T_dst + d <= T_csr

where ``T_dst`` is the domain clock period, ``d`` is the path delay from the
domain flops to the bus clock flops, and ``T_csr`` is the bus clock period.
The generated module does not check the bound. Change the input only while the
bus is idle.

A domain without ``cdc_fast_mode_en`` has no fast-mode input and no fast-mode
logic.

Register classes
----------------

The scanner assigns each register with ``cdc_clk`` to one class.

+---------------+-------------------------------------------------+------------------+-----------------------+
| Class         | Declared by                                     | Write            | Read                  |
+===============+=================================================+==================+=======================+
| plain         | ``cdc_clk`` only                                | crosses, posted  | crosses               |
+---------------+-------------------------------------------------+------------------+-----------------------+
| write trigger | ``buffer_writes``; ``wbuffer_trigger`` is the   | crosses, not     | crosses               |
|               | register itself (the default)                   | posted           |                       |
+---------------+-------------------------------------------------+------------------+-----------------------+
| write member  | ``buffer_writes``; ``wbuffer_trigger`` is       | bus-side copy,   | bus-side copy         |
|               | another register                                | no crossing      |                       |
+---------------+-------------------------------------------------+------------------+-----------------------+
| read trigger  | ``buffer_reads``; ``rbuffer_trigger`` is the    | crosses, posted, | crosses               |
|               | register itself (the default)                   | if writable      |                       |
+---------------+-------------------------------------------------+------------------+-----------------------+
| read member   | ``buffer_reads``; ``rbuffer_trigger`` is        | none             | snapshot, no crossing |
|               | another register                                |                  |                       |
+---------------+-------------------------------------------------+------------------+-----------------------+

A register that crosses has one slot in its domain, and the handshake carries
one slot at a time. Members have no slot. A write to a read-only register, and
a read of a write-only register, complete without a hang and change nothing.

Fields
------

A CDC register has two kinds of field.

Config field
    ``sw`` is ``rw`` or ``w``, and ``hw`` is ``r`` or ``na``. The field is
    stored in the domain, and an ``hw = r`` field drives its output port from
    the domain flops. A write merges per bit:
    ``storage <= (storage & ~biten) | (data & biten)``. A field with a reset
    value resets to it. A field without one has no reset.

Status field
    ``sw`` is ``r`` and ``hw`` is ``w``. The ``hwif_in`` input is sampled on
    the domain clock, so it must be synchronous to that clock. In a plain
    register or a trigger the field has no flops of its own: a read samples the
    input into the read-data register of the domain. All registers of a domain
    share that register, and it holds the value only until the next read in
    the domain. In a read member the field has one snapshot flop per bit (see
    `Atomic groups`_).

Any other combination of ``sw`` and ``hw`` is an error.

Atomic groups
-------------

A group makes several registers change, or be read, on one domain clock edge.
Groups reuse ``buffer_writes`` with ``wbuffer_trigger``, and ``buffer_reads``
with ``rbuffer_trigger``. The trigger and all members must be registers in the
same domain. The trigger must itself set the buffering property. A trigger
cannot be an array element or sit inside an arrayed regfile. An arrayed member
joins its group with every element. A group may consist of the trigger alone: a
write to it is not posted.

Write group
    A write to a member updates the member's bus-side copy, with a per-bit
    merge, and completes in one bus cycle. It changes no output. A write to the
    trigger crosses and carries only the trigger's own write data and byte
    enables. On the domain clock edge of that access, every member loads its
    domain storage from its bus-side copy whatever the byte enables are, and
    the trigger loads its own fields from the write data with a per-bit merge.
    A member that was not written keeps its value in the copy, so the load
    rewrites the old value. The trigger has no bus-side copy. A read of a member
    returns the bus-side copy, which can differ from the domain output until
    the next trigger write. A read of the trigger crosses and returns the
    domain value of its fields with ``sw`` read access. Bits outside fields
    with ``sw`` read access read 0.

Read group
    A read of the trigger crosses. On the domain clock edge of that access,
    every member's status inputs are captured into a snapshot in the domain, and
    the trigger's own value is captured into the read data. The trigger has no
    snapshot, and its read returns only its own value. A write to a trigger
    with a config field crosses and is posted, merges per bit like a plain
    register, and loads no snapshot. A read of a member
    returns the snapshot and does not cross. A snapshot is loaded only by a read
    of its own trigger. It resets to 0, so a member reads 0 until the first
    trigger read.

In default mode, a write group loads while the bus is stalled, from the request
until the acknowledge. The bus-side copies cannot change in that time, so the
domain clock samples them while they are stable. A read group changes its
snapshots only during a trigger read, which also stalls the bus, so the
snapshots are stable whenever the bus reads them. Neither needs a synchronizer.

In fast mode the acknowledge does not wait for the domain. The two arguments
then rest on the timing bound under `Fast mode`_: the domain edge that loads or
captures must come within one bus cycle of the request.

A write member bit costs two flops, the bus-side copy and the domain storage. A
read member bit costs one flop, the snapshot.

Wide members
------------

A write member or a read member may have ``regwidth`` greater than
``accesswidth``. A plain register or a trigger may not.

Each subword write to a wide write member updates that subword of the bus-side
copy, with a per-bit merge. A subword that is not written keeps its value. A
config field may span subwords. The trigger write loads the whole register on one
domain clock edge. The trigger read captures the whole member into its
snapshot on one edge, and each subword read of the member returns that subword
of the snapshot.

Arrays
------

A register array with ``cdc_clk``, and a ``cdc_clk`` register inside an arrayed
regfile, are accepted. The generator emits them in ``for`` loops as it does for
any array. Every element is a separate slot, so each element has its own
address, its own storage and its own handshake index. An access to one element
changes only that element's outputs.

Example
-------

An example design with two domains, a write group, a read group, arrayed
members, wide members and fast mode is in
:download:`tests/test_cdc_example/regblock.rdl <../../tests/test_cdc_example/regblock.rdl>`.
The cocotb test in ``tests/test_cdc_example/test_dut.py`` simulates it.

Reset
-----

The reset behavior is the same for the four ``--default-reset`` styles ``rst``,
``rst_n``, ``arst`` and ``arst_n``.

* The bus-side flops of the handshake (state, request toggle, pending slot) use
  the block's reset style, as the other flops of the block do.
* The bus reset is the only reset of a domain. A field of a CDC register must
  not set ``resetsignal``.
* The synchronizers use an asynchronous, active-high reset derived from the bus
  reset. For ``rst`` and ``rst_n`` it is registered once on ``clk``, because a
  synchronous reset can glitch between clock edges.
* The domain reset, ``cdc_<clk>_dst_rst``, is active high in every style. It
  asserts with the domain clock stopped or running: at the same time as the
  bus-side reset in ``arst`` and ``arst_n``, and one ``clk`` cycle later in
  ``rst`` and ``rst_n``. Its release needs ``cdc_nstages`` domain clock edges
  after the bus-side reset releases.
* The flops in the domain (storage, snapshots, read data, acknowledge toggle)
  reset asynchronously from the domain reset.
* The bus-side copies of write members reset from the bus reset, in the
  block's reset style. A bus reset therefore resets the copy and the domain
  storage of a member to the field's reset value.

With ``cdc_fast_mode_en`` and the input at 1, wait for the domain reset to
release before the first access.

Synchronizer cell
-----------------

By default each synchronizer is a vector of flops in the generated module.
Each domain has three synchronizers: reset, request and acknowledge. The option
``--sync-cell NAME`` replaces each of them with an instance of the module
``NAME``, which the project supplies. The generated module then has no inline
synchronizer flops.

The module has this interface:

.. code-block:: systemverilog

    module NAME #(parameter int NSTAGES = 2) (
        output logic q,    // synchronized; 0 while rst is asserted
        input  wire  d,
        input  wire  clk,  // receiving clock
        input  wire  rst   // active high, asynchronous
    );

``rst`` is active high and asynchronous in every ``--default-reset`` style, so
one cell serves all four. The generated module sets ``NSTAGES`` from
``cdc_nstages`` of the domain. Add the cell to the file list of the simulator
or synthesis tool together with the generated module.

Crossings
---------

Each domain, with ``<clk>`` the clock signal name, has three synchronizers.
Each carries one bit. With inline synchronizers the flops of each are a vector
named ``<name>_ff``, and its last bit drives the output net. With
``--sync-cell`` each is an instance named ``<name>`` that drives the output net.

``cdc_<clk>_u_rst_sync``
    Output net ``cdc_<clk>_rst_sync_q``. Clocked by ``<clk>``, ``d`` is
    ``1'b1``, reset asynchronously by ``cdc_<clk>_arst`` from the bus side. Its
    output releases ``cdc_<clk>_dst_rst``.

``cdc_<clk>_u_req_sync``
    Output net ``cdc_<clk>_req_sync``. Carries the request toggle
    ``cdc_<clk>_req_tgl`` from ``clk`` to ``<clk>``.

``cdc_<clk>_u_ack_sync``
    Output net ``cdc_<clk>_ack_sync``. Carries the acknowledge toggle
    ``cdc_<clk>_ack_tgl`` from ``<clk>`` to ``clk``.

The signals below cross without a synchronizer. The handshake holds each one
stable while the receiving clock samples it; in fast mode this rests on the
timing bound under `Fast mode`_. Use the names to write max-delay or
false-path constraints, or CDC lint waivers.

From ``clk`` to ``<clk>``:

* ``cdc_<clk>_idx``, ``cdc_<clk>_is_wr``, ``cdc_<clk>_wr_data`` and
  ``cdc_<clk>_wr_biten``: the request index, the write flag, the write data and
  the bit enables. They are flops on the bus side.
* ``cdc_shadow_<reg path>``: the bus-side copy of a write member. The domain
  storage ``cdc_dst_<field path>_value`` of each of its fields loads from it on a
  trigger write. The trigger has no bus-side copy.

From ``<clk>`` to ``clk``:

* ``cdc_<clk>_rdata``: the read data, a flop in the domain. The readback logic
  reads it through ``cdc_<clk>_rd_data``.
* ``cdc_snap_<reg path>``: the snapshot of a read member, a flop in the domain.
  The readback logic reads it on a member read.

``<field path>`` and ``<reg path>`` are the hierarchical names below the top
addrmap, joined with ``_``, for example ``cdc_shadow_thr_lo`` and
``cdc_dst_thr_lo_v_value``.

Rules
-----

Export stops with an error for each of these.

* ``cdc_clk`` on an ``external`` register, and any CDC register with
  ``--rt-external reg``.
* A register with both ``buffer_writes`` and ``buffer_reads``.
* A plain register, or a trigger, wider than ``accesswidth``.
* An ``msb0`` field in a CDC register.
* A trigger that is not a register, is not in the same domain, does not set the
  buffering property, is itself a member of another group, or is an array
  element.
* A field access other than the config and status combinations above, a status
  field in a write member, and a config field in a read member.
* ``onread``, ``onwrite``, ``intr``, ``singlepulse``, ``paritycheck``,
  ``hwset``, ``hwclr``, ``swacc``, ``swmod``, ``rd_swacc``, ``wr_swacc``,
  ``counter``, ``we``, ``wel``, ``swwe``, ``swwel``, ``anded``, ``ored``,
  ``xored``, ``hwenable``, ``hwmask``, ``sticky``, ``stickybit``, ``rclr``,
  ``rset`` and ``next`` on a field of a CDC register.
* A ``reset`` of a CDC field that is a reference instead of a constant.
* A ``resetsignal`` on a field of a CDC register.
* A property outside a CDC register that references a field of one, such as
  ``x.f->next = cdc_reg.f``. Such a reference would let bus clock logic sample
  a domain flop with no synchronizer.
* A clock signal that breaks the rules under ``cdc_clk``, or that carries
  ``cdc_nstages`` or ``cdc_fast_mode_en`` without being a domain clock.
* A clock signal declared inside an arrayed regfile or addrmap.
* Two clock signals with the same instance name, for example one signal
  declared in each of two instances of a regfile. Both would become the same
  port.
* A clock signal named like an existing port: ``clk``, the bus reset port, or a
  CPU interface port.
* A port that collides with a name generated for a domain, for example an
  existing port named ``<clk>_fast_mode_en`` or ``cdc_<clk>_*``.
