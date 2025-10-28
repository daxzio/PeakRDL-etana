Open Bus Interface (OBI)
=========================

The Open Bus Interface (OBI) is an open-source bus protocol developed by the OpenHW Group.
It supports multiple outstanding transactions and provides separate request/response channels.

OBI Protocol Overview
---------------------

OBI uses a two-phase handshake protocol:

**Request Phase (A-Channel):**
  - ``req`` and ``gnt`` handshake for address/control transfer
  - Manager asserts ``req`` with address and control signals
  - Subordinate asserts ``gnt`` when ready to accept

**Response Phase (R-Channel):**
  - ``rvalid`` and ``rready`` handshake for data transfer
  - Subordinate asserts ``rvalid`` with response data
  - Manager asserts ``rready`` when ready to accept

OBI-Flat
--------

Implements the register block using an OBI CPU interface with **flattened signal interface**
(individual input/output ports).

* Command line: ``--cpuif obi-flat``
* Class: :class:`peakrdl_etana.cpuif.obi.OBI_Cpuif_flattened`

Signal Interface
~~~~~~~~~~~~~~~~

**Request Channel (A-Channel):**

* ``s_obi_req`` - Request valid (input)
* ``s_obi_gnt`` - Grant/ready (output)
* ``s_obi_addr`` - Address (input)
* ``s_obi_we`` - Write enable (input)
* ``s_obi_be`` - Byte enable (input)
* ``s_obi_wdata`` - Write data (input)
* ``s_obi_aid`` - Address ID (input)

**Response Channel (R-Channel):**

* ``s_obi_rvalid`` - Response valid (output)
* ``s_obi_rready`` - Response ready (input)
* ``s_obi_rdata`` - Read data (output)
* ``s_obi_err`` - Error response (output)
* ``s_obi_rid`` - Response ID (output)

Parameters
~~~~~~~~~~

The OBI interface includes an ``ID_WIDTH`` parameter to configure the transaction ID width:

.. code-block:: systemverilog

   module my_regblock #(
       parameter ID_WIDTH = 1  // Default ID width
   ) (
       // ... signals ...
   );

Features
--------

**Multiple Outstanding Transactions:**
  OBI supports pipelining of transactions through separate request and response channels.

**Transaction IDs:**
  The ``aid`` (address ID) and ``rid`` (response ID) signals allow tracking of multiple
  outstanding transactions.

**Byte Enables:**
  Per-byte write strobes through the ``be`` signal enable partial word writes.

Error Response Support
----------------------

The OBI interface supports error signaling via the ``err`` signal. When error response
options are enabled:

**--err-if-bad-addr**
    Asserts ``err`` when software accesses an unmapped address

**--err-if-bad-rw**
    Asserts ``err`` when:

    - Writing to a read-only register
    - Reading from a write-only register

Usage Example
-------------

.. code-block:: bash

   # Generate register block with OBI interface
   peakrdl etana my_registers.rdl --cpuif obi-flat -o output_dir/

   # Enable error responses
   peakrdl etana my_registers.rdl --cpuif obi-flat \
       --err-if-bad-addr --err-if-bad-rw -o output_dir/

Integration Notes
-----------------

* The interface is fully compatible with OpenHW Group's OBI specification
* Address signals are byte-addressed (each increment represents one byte)
* The default ``ID_WIDTH`` is 1 bit, but can be overridden during instantiation
* Response channel uses ready/valid handshaking for back-pressure support

.. note::
    PeakRDL-etana uses flattened signals exclusively. There are no SystemVerilog
    struct-based interface options.
