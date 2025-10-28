CPUIF Passthrough
=================

This CPUIF mode bypasses the protocol converter stage and directly exposes the
internal CPUIF handshake signals to the user.

* Command line: ``--cpuif passthrough``
* Class: :class:`peakrdl_etana.cpuif.passthrough.PassthroughCpuif`

For more details on the protocol itself, see: :ref:`cpuif_protocol`.

Error Response Support
----------------------

The Passthrough interface supports error response generation via ``rd_err`` and ``wr_err`` signals:

* When ``--err-if-bad-addr`` is enabled, accessing unmapped addresses asserts the error signal
* When ``--err-if-bad-rw`` is enabled, forbidden reads/writes assert the error signal

**Validated with external components** - The ``test_cpuif_err_rsp`` test validates Passthrough
error responses with both internal registers and external registers/memories.
