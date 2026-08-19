AMBA AHB5 (hazard3 fabric)
============================

Implements the register block using an AMBA AHB5 CPU interface with the
**shared-bus slave port convention** used by hazard3 (``ahbl_splitter``,
``ahb_sync_sram``, ``ahbl_to_apb``). This variant is intended for dropping
an etana regblock directly onto the hazard3 AHB-Lite fabric alongside SRAM
and APB peripherals.

The AHB5 CPU interface provides **flattened signal interface** (individual
input/output ports):

* Command line: ``--cpuif ahb5-flat``
* Class: :class:`peakrdl_etana.cpuif.ahb5.AHB5_Cpuif_flattened`

.. note::
    PeakRDL-etana uses flattened signals exclusively. There are no SystemVerilog
    struct-based interface options.

.. warning::
    Like other CPU interfaces in this exporter, the AHB5 ``HADDR`` input is
    interpreted as a byte-address. Address values should be byte-aligned according
    to the data width being used (e.g., for 32-bit transfers, addresses increment
    in steps of 4).

Supported Signals
-----------------

The AHB5 interface includes the following signals (prefix ``s_ahb_``):

Request signals (inputs):
    * ``s_ahb_hsel`` - Slave select (tie high when no per-slave decoder)
    * ``s_ahb_htrans[1:0]`` - Transfer type (NONSEQ, SEQ, IDLE, BUSY)
    * ``s_ahb_hwrite`` - Write enable (1 = write, 0 = read)
    * ``s_ahb_hsize[2:0]`` - Transfer size
    * ``s_ahb_hburst[2:0]`` - Burst type (accepted, unused for CSR)
    * ``s_ahb_hprot[3:0]`` - Protection (accepted, unused for CSR)
    * ``s_ahb_hmastlock`` - Locked transfer (accepted, unused for CSR)
    * ``s_ahb_hnonsec`` - Non-secure transfer (accepted, unused for CSR)
    * ``s_ahb_hexcl`` - Exclusive access request
    * ``s_ahb_hmaster[3:0]`` - Master identifier for exclusive monitor
    * ``s_ahb_haddr`` - Byte address
    * ``s_ahb_hwdata`` - Write data bus
    * ``s_ahb_hready`` - **HREADYIN** (global bus ready input)

Response signals (outputs):
    * ``s_ahb_hready_resp`` - **HREADYOUT** (slave ready output)
    * ``s_ahb_hrdata`` - Read data bus
    * ``s_ahb_hresp`` - Transfer response (0 = OKAY, 1 = ERROR)
    * ``s_ahb_hexokay`` - Exclusive-okay response (AHB5)

Split HREADY Model
------------------

Unlike ``ahb-flat`` (single ``HREADY`` output), this variant uses the
shared-fabric convention:

* ``s_ahb_hready`` (**input**) = HREADYIN from the bus arbiter/splitter
* ``s_ahb_hready_resp`` (**output**) = HREADYOUT from this slave

The slave qualifies new address phases with ``HSEL && HTRANS[1] && HREADYIN``.
When the slave cannot complete a transfer, it drives ``HREADYOUT`` low.

Exclusive Access (HEXCL / HEXOKAY)
----------------------------------

The interface implements a local exclusive monitor:

* An exclusive read (``HEXCL=1``) establishes a reservation for ``{HADDR, HMASTER}``
* A matching exclusive write completes with ``HEXOKAY=1`` and performs the write
* A non-matching exclusive write completes with ``HEXOKAY=0`` and suppresses the write
* Any intervening normal write to the reserved address invalidates the monitor

Error Response Support
----------------------

The AHB5 interface supports error signaling via ``HRESP``:

**--err-if-bad-addr**
    Asserts ``HRESP`` (ERROR = 1) when software accesses an unmapped address

**--err-if-bad-rw**
    Asserts ``HRESP`` (ERROR = 1) when software attempts invalid read/write

**Example:**

.. code-block:: bash

    peakrdl etana design.rdl --cpuif ahb5-flat --err-if-bad-addr --err-if-bad-rw -o output/

hazard3 Integration Example
---------------------------

Mapping an etana regblock onto the hazard3 ``ahbls_*`` slave port convention
(see ``ahb_sync_sram.v`` and ``example_soc.v``):

.. code-block:: systemverilog

    ahb5_regblock #(
        // ...
    ) my_regs (
        .clk               (clk),
        .rst               (~rst_n),

        // hazard3 fabric slave port (ahbls_* naming)
        .s_ahb_hready_resp (regs_hready_resp),
        .s_ahb_hready      (regs_hready),       // HREADYIN from splitter
        .s_ahb_hresp       (regs_hresp),
        .s_ahb_haddr       (regs_haddr),
        .s_ahb_hwrite      (regs_hwrite),
        .s_ahb_htrans      (regs_htrans),
        .s_ahb_hsize       (regs_hsize),
        .s_ahb_hburst      (regs_hburst),
        .s_ahb_hprot       (regs_hprot),
        .s_ahb_hmastlock   (regs_hmastlock),
        .s_ahb_hwdata      (regs_hwdata),
        .s_ahb_hrdata      (regs_hrdata),

        // No per-slave decoder in ahbl_splitter fabric
        .s_ahb_hsel        (1'b1),

        // AHB5 signals not forwarded by hazard3 splitter to SRAM slaves;
        // tie off when connecting through ahbl_splitter
        .s_ahb_hexcl       (1'b0),
        .s_ahb_hexokay     (),
        .s_ahb_hnonsec     (1'b1),
        .s_ahb_hmaster     (4'b0),

        // hwif signals ...
    );

Connect ``regs_hready_resp`` / ``regs_hready`` to a new port on ``ahbl_splitter``
alongside the existing SRAM and APB bridge ports.

Testing
-------

The ``test_ahb5`` test validates the AHB5 interface including split-HREADY,
read/write to internal and external registers, multi-cycle external latency,
and exclusive access (``HEXCL``/``HEXOKAY``).

References
----------

* `AMBA 5 AHB Protocol Specification <https://developer.arm.com/documentation/ihi0033/latest/>`_
* hazard3 ``ahb_sync_sram.v`` and ``example_soc.v``
