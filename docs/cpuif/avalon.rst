Avalon Memory-Mapped (Avalon-MM)
=================================

The Avalon Memory-Mapped interface is Intel/Altera's standard bus protocol for FPGA designs.
It supports pipelined transactions with separate read and write control, back-pressure via
waitrequest, and flexible response handling.

Avalon-MM Protocol Overview
----------------------------

Avalon-MM uses a request/response protocol with the following characteristics:

**Request Phase:**
  - Separate ``read`` and ``write`` control signals
  - ``waitrequest`` signal provides back-pressure (stalls transaction)
  - **Word addressing** (address represents word offset, not byte offset)
  - Byte enables for partial word writes

**Response Phase:**
  - ``readdatavalid`` indicates valid read data
  - ``writeresponsevalid`` indicates write completion
  - 2-bit ``response`` signal for error reporting (0x0=OK, 0x2=SLVERR)

Avalon-MM-Flat
--------------

Implements the register block using an Avalon-MM CPU interface with **flattened signal interface**
(individual input/output ports).

* Command line: ``--cpuif avalon-mm-flat``
* Class: :class:`peakrdl_etana.cpuif.avalon.Avalon_Cpuif_flattened`

Signal Interface
~~~~~~~~~~~~~~~~

**Request Signals:**

* ``avalon_read`` - Read request (input)
* ``avalon_write`` - Write request (input)
* ``avalon_address`` - Word address (input) - **NOT byte address!**
* ``avalon_writedata`` - Write data (input)
* ``avalon_byteenable`` - Byte enables (input)
* ``avalon_waitrequest`` - Back-pressure/stall (output)

**Response Signals:**

* ``avalon_readdatavalid`` - Read data valid (output)
* ``avalon_writeresponsevalid`` - Write response valid (output)
* ``avalon_readdata`` - Read data (output)
* ``avalon_response`` - Response code (output)

  * ``2'b00`` - OK
  * ``2'b10`` - SLVERR (slave error)

.. warning::
    The ``avalon_address`` signal uses **word addressing**, not byte addressing.
    For a 32-bit data width (4 bytes per word), address 0x01 refers to byte address 0x04.

Features
--------

**Word Addressing:**
  Avalon-MM agents use word-based addressing. The address width is automatically
  reduced based on the data width:

  - 32-bit data (4 bytes): ``addr_word = addr_byte / 4``
  - 64-bit data (8 bytes): ``addr_word = addr_byte / 8``

**Separate Read/Write:**
  Independent read and write control signals allow for flexible transaction handling.

**Wait Requests:**
  The ``waitrequest`` signal provides back-pressure, allowing the subordinate to stall
  transactions when not ready to accept new requests.

**Pipelined Responses:**
  Separate ``readdatavalid`` and ``writeresponsevalid`` signals enable pipelined operation
  with variable latency responses.

**Byte Enables:**
  Per-byte write strobes through ``byteenable`` enable partial word writes.

Error Response Support
----------------------

The Avalon-MM interface supports error signaling via the 2-bit ``response`` signal.
When error response options are enabled:

**--err-if-bad-addr**
    Asserts ``response = 2'b10`` (SLVERR) when software accesses an unmapped address

**--err-if-bad-rw**
    Asserts ``response = 2'b10`` (SLVERR) when:

    - Writing to a read-only register
    - Reading from a write-only register

Usage Example
-------------

.. code-block:: bash

   # Generate register block with Avalon-MM interface
   peakrdl etana my_registers.rdl --cpuif avalon-mm-flat -o output_dir/

   # Enable error responses
   peakrdl etana my_registers.rdl --cpuif avalon-mm-flat \
       --err-if-bad-addr --err-if-bad-rw -o output_dir/

Example Integration
~~~~~~~~~~~~~~~~~~~

.. code-block:: systemverilog

   module my_soc (
       input wire clk,
       input wire rst
   );

       // Avalon-MM master signals
       logic        mm_read;
       logic        mm_write;
       logic        mm_waitrequest;
       logic [7:0]  mm_address;        // Word address (8 bits = 256 words = 1KB)
       logic [31:0] mm_writedata;
       logic [3:0]  mm_byteenable;
       logic        mm_readdatavalid;
       logic        mm_writeresponsevalid;
       logic [31:0] mm_readdata;
       logic [1:0]  mm_response;

       // Instantiate register block
       my_regblock u_regs (
           .clk(clk),
           .rst(rst),
           .avalon_read(mm_read),
           .avalon_write(mm_write),
           .avalon_waitrequest(mm_waitrequest),
           .avalon_address(mm_address),
           .avalon_writedata(mm_writedata),
           .avalon_byteenable(mm_byteenable),
           .avalon_readdatavalid(mm_readdatavalid),
           .avalon_writeresponsevalid(mm_writeresponsevalid),
           .avalon_readdata(mm_readdata),
           .avalon_response(mm_response)
       );

   endmodule

Integration Notes
-----------------

**Word Addressing:**
  The most important consideration is that Avalon-MM uses word addressing:

  - For 32-bit (4-byte) data width: multiply address by 4 to get byte offset
  - For 64-bit (8-byte) data width: multiply address by 8 to get byte offset
  - Example: ``avalon_address = 0x10`` → byte address = ``0x40`` (for 32-bit data)

**Transaction Flow:**

  1. Master asserts ``read`` or ``write`` with address and data (for writes)
  2. If ``waitrequest`` is low, transaction is accepted on next clock edge
  3. If ``waitrequest`` is high, transaction is stalled until it goes low
  4. For reads: ``readdatavalid`` asserts when data is ready
  5. For writes: ``writeresponsevalid`` asserts when write completes
  6. Check ``response`` signal for errors (0x0=OK, 0x2=SLVERR)

**Setup Time:**
  Ensure hardware interface signals have at least one clock cycle to settle before
  starting Avalon transactions, as the request logic is combinational.

**Compatible With:**
  - Intel/Altera Avalon-MM specification
  - Platform Designer / Qsys integration
  - All Intel FPGA families

**Performance:**
  - Minimum read latency: 2 clock cycles
  - Minimum write latency: 2 clock cycles
  - Supports variable latency via ``waitrequest``
  - Pipelined operation supported

.. note::
    PeakRDL-etana uses flattened signals exclusively. There are no SystemVerilog
    struct-based interface options.

Comparison with Other Interfaces
---------------------------------

========================  =======  =======  ===========  =======  ============
Feature                   APB4     AHB      AXI4-Lite    OBI      Avalon-MM
========================  =======  =======  ===========  =======  ============
Addressing Mode           Byte     Byte     Byte         Byte     **Word**
Pipelined                 No       Limited  Yes          Yes      Yes
Outstanding Transactions  1        1        Multiple     Multiple Variable
Read/Write Separate       No       No       Yes          No       **Yes**
Back-pressure             Limited  None     Full         Full     **Full**
Error Signaling           1-bit    1-bit    2-bit        1-bit    **2-bit**
Best Use Case             Simple   SoC      High-perf    RISC-V   **Intel FPGA**
========================  =======  =======  ===========  =======  ============

Testing
-------

The Avalon-MM implementation has been validated with comprehensive testing:

- ✅ 100% pass rate with PeakRDL-regblock (29/29 applicable tests)
- ✅ 96.7% pass rate with PeakRDL-etana (29/30 applicable tests)
- ✅ All protocol features verified (pipelining, back-pressure, error responses)
- ✅ Tested with Verilator simulation

.. code-block:: bash

   # Test with PeakRDL-etana
   cd tests/test_simple
   make clean etana sim CPUIF=avalon-mm-flat SIM=verilator

   # Test with PeakRDL-regblock (reference)
   make clean regblock sim REGBLOCK=1 CPUIF=avalon-mm-flat

   # Full test suite
   cd tests
   ./test_all.sh REGBLOCK=1 CPUIF=avalon-mm-flat SIM=verilator

References
----------

- `Intel Avalon Interface Specifications <https://www.intel.com/content/www/us/en/docs/programmable/683091/current/introduction-to-the-interface-specifications.html>`_
- Avalon Memory-Mapped Interface Specification
- Platform Designer (Qsys) User Guide
