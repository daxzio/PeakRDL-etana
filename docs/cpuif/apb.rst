AMBA APB
========

Both APB3 and APB4 standards are supported.

.. warning::
    Some IP vendors will incorrectly implement the address signalling
    assuming word-addresses. (that each increment of ``PADDR`` is the next word)

    For this exporter, values on the interface's ``PADDR`` input are interpreted
    as byte-addresses. (an APB interface with 32-bit wide data increments
    ``PADDR`` in steps of 4 for every word). Even though APB protocol does not
    allow for unaligned transfers, this is in accordance to the official AMBA
    specification.

    Be sure to double-check the interpretation of your interconnect IP. A simple
    bit-shift operation can be used to correct this if necessary.


APB3
----

Implements the register block using an
`AMBA 3 APB <https://developer.arm.com/documentation/ihi0024/b/Introduction/About-the-AMBA-3-APB>`_
CPU interface with **flattened signal interface** (individual input/output ports).

* Command line: ``--cpuif apb3-flat``
* Class: :class:`peakrdl_etana.cpuif.apb3.APB3_Cpuif_flattened`

.. note::
    PeakRDL-etana uses flattened signals exclusively. There are no SystemVerilog
    struct-based interface options.


APB4
----

Implements the register block using an
`AMBA 4 APB <https://developer.arm.com/documentation/ihi0024/d/?lang=en>`_
CPU interface with **flattened signal interface** (individual input/output ports).

* Command line: ``--cpuif apb4-flat``
* Class: :class:`peakrdl_etana.cpuif.apb4.APB4_Cpuif_flattened`

.. note::
    PeakRDL-etana uses flattened signals exclusively. There are no SystemVerilog
    struct-based interface options.

Error Response Support
----------------------

APB4 supports error signaling via the ``PSLVERR`` signal. When error response
options are enabled:

**--err-if-bad-addr**
    Asserts ``PSLVERR`` when software accesses an unmapped address

**--err-if-bad-rw**
    Asserts ``PSLVERR`` when:

    * Software attempts to read a write-only register
    * Software attempts to write a read-only register

**Example:**

.. code-block:: bash

    peakrdl etana design.rdl --cpuif apb4-flat --err-if-bad-addr --err-if-bad-rw -o output/

**Note:** APB3 does not include the ``PSLVERR`` signal and therefore does not support
error response generation.
