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
    input, named after the signal instance, and is the domain clock. A signal
    is a domain clock only because a register names it. The signal must be one
    bit wide, not an array, and must not set ``cpuif_reset``, ``field_reset``,
    ``activelow``, ``activehigh``, ``sync`` or ``async``. Nothing else may
    reference it, for example as a ``resetsignal`` or a ``next``.

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
    ``sw`` is ``r`` and ``hw`` is ``w``. The field has no storage. A read
    returns the ``hwif_in`` input sampled on the domain clock, so the input must
    be synchronous to that clock.

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
    trigger crosses. On the domain clock edge of that access, every member
    loads its domain storage from its bus-side copy, and the trigger loads its
    own fields from the write data. A member that was not written keeps its
    value in the copy, so the load rewrites the old value. A read of a member
    returns the bus-side copy, which can differ from the domain output until the
    next trigger write.

Read group
    A read of the trigger crosses. On the domain clock edge of that access,
    every member's status inputs are captured into a snapshot in the domain, and
    the trigger's own value is captured into the read data. A read of a member
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
domain clock edge. The trigger read captures the whole register into the
snapshot on one edge, and each subword read of the member returns that subword
of the snapshot.

Arrays
------

A register array with ``cdc_clk``, and a ``cdc_clk`` register inside an arrayed
regfile, are accepted. The generator emits them in ``for`` loops as it does for
any array. Every element is a separate slot, so each element has its own
address, its own storage and its own handshake index. An access to one element
changes only that element's outputs.

Reset
-----

The reset behavior is the same for the four ``--default-reset`` styles ``rst``,
``rst_n``, ``arst`` and ``arst_n``.

* The bus-side flops of the handshake (state, request toggle, pending slot) use
  the block's reset style, as the other flops of the block do.
* The handshake resets from one net. That net is the bus reset, ORed with the
  field ``resetsignal`` of the domain if its fields name one. All fields of a
  domain must name the same ``resetsignal`` or none.
* The synchronizers use an asynchronous, active-high reset derived from that
  net. For ``rst`` and ``rst_n`` the net is registered once on ``clk``, because
  a synchronous reset can glitch between clock edges.
* The domain reset, ``cdc_<clk>_dst_rst``, is active high in every style. It
  asserts at the same time as the bus-side reset, with the domain clock stopped
  or running, and releases ``cdc_nstages`` domain clock edges later.
* The flops in the domain (storage, snapshots, read data, acknowledge toggle)
  reset asynchronously from the domain reset.
* The bus-side copies of write members reset as a field does: from the field's
  ``resetsignal`` if it has one, else from the default reset.

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

Rules
-----

Export stops with an error for each of these.

* ``cdc_clk`` on an ``external`` register, and any CDC register with
  ``--rt-external reg``.
* A register with both ``buffer_writes`` and ``buffer_reads``.
* A plain register, or a trigger, wider than ``accesswidth``.
* A wide member with an ``msb0`` field.
* A trigger that is not a register, is not in the same domain, does not set the
  buffering property, or is an array element.
* A field access other than the config and status combinations above, a status
  field in a write member, and a config field in a read member.
* ``onread``, ``onwrite``, ``intr``, ``singlepulse``, ``paritycheck``,
  ``hwset``, ``hwclr``, ``swacc`` and ``swmod`` on a field of a CDC register.
* Two different ``resetsignal`` values among the fields of one domain.
* A property outside a CDC register that references a field of one, such as
  ``x.f->next = cdc_reg.f``. Such a reference would let bus clock logic sample
  a domain flop with no synchronizer.
* A clock signal that breaks the rules under ``cdc_clk``, or that carries
  ``cdc_nstages`` or ``cdc_fast_mode_en`` without being a domain clock.
* A port that collides with a name generated for a domain, for example an
  existing port named ``<clk>_fast_mode_en`` or ``cdc_<clk>_*``.
