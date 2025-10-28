Introduction
============

PeakRDL-etana is a specialized fork of PeakRDL-regblock that implements a **flattened signal architecture**.
This free and open-source control & status register (CSR) compiler translates your SystemRDL register
description into synthesizable SystemVerilog RTL with individual signal ports instead of SystemVerilog structs.

**Key Differences from Original PeakRDL-regblock:**

* **Flattened signal interface** - Individual ports (``hwif_in_reg_field``) instead of struct members (``hwif_in.reg.field``)
* **Enhanced compatibility** - Works with all synthesis tools and design flows
* **Direct connectivity** - No struct unpacking required
* **Improved debugging** - Individual signals easier to trace in waveforms

**Features:**

* Generates fully synthesizable SystemVerilog RTL (IEEE 1800-2012)
* Options for many popular CPU interface protocols (AMBA APB, AHB, AXI4-Lite, and more)
* **CPU interface error responses** - Configurable error signaling for unmapped addresses and forbidden R/W
* **External component support** - Validated integration with external registers and memories
* Configurable pipelining options for designs with fast clock rates
* Broad support for SystemRDL 2.0 features
* Fully synthesizable SystemVerilog. Tested on Xilinx/AMD's Vivado & Intel Quartus
* Enhanced safety checks: width validation, assertion guards, optimized field logic
* **Comprehensive test suite** - Cocotb-based validation across multiple CPU interfaces

.. warning::

    This is a specialized fork with flattened signal architecture. For the original
    struct-based implementation, see `PeakRDL-regblock <https://github.com/SystemRDL/PeakRDL-regblock>`_.

Upstream Sync Status
--------------------

This fork is based on **PeakRDL-regblock v0.22.0** (December 2024) and includes all applicable
fixes from **v1.1.0**. See ``UPSTREAM_SYNC_STATUS.md`` in the repository root for detailed information.

Installing
----------

Clone and install from the repository:

.. code-block:: bash

    git clone https://github.com/daxzio/PeakRDL-etana.git
    cd PeakRDL-etana
    pip install -e .

Example
-------
Use PeakRDL-etana via the PeakRDL command line tool:

.. code-block:: bash

    # Install the command line tool
    python3 -m pip install peakrdl

    # Export with flattened signals!
    peakrdl etana atxmega_spi.rdl -o regblock/ --cpuif axi4-lite

    # Flatten nested address map components
    peakrdl etana my_design.rdl -o output/ --flatten-nested-blocks

    # Enable CPU interface error responses
    peakrdl etana my_design.rdl -o output/ --cpuif apb4-flat --err-if-bad-addr --err-if-bad-rw

Links
-----

- `Source repository <https://github.com/daxzio/PeakRDL-etana>`_
- `Original PeakRDL-regblock <https://github.com/SystemRDL/PeakRDL-regblock>`_
- `Issue tracker <https://github.com/daxzio/PeakRDL-etana/issues>`_
- `SystemRDL Specification <http://accellera.org/downloads/standards/systemrdl>`_


.. toctree::
    :hidden:

    self
    architecture
    hwif
    template_generation
    hwif_report
    configuring
    testing
    limitations
    licensing
    api

.. toctree::
    :hidden:
    :caption: CPU Interfaces

    cpuif/introduction
    cpuif/apb
    cpuif/ahb
    cpuif/axi4lite
    cpuif/avalon
    cpuif/passthrough
    cpuif/internal_protocol
    cpuif/customizing

.. toctree::
    :hidden:
    :caption: SystemRDL Properties

    props/field
    props/reg
    props/addrmap
    props/signal
    props/rhs_props

.. toctree::
    :hidden:
    :caption: Other SystemRDL Features

    rdl_features/external

.. toctree::
    :hidden:
    :caption: Extended Properties

    udps/intro
    udps/read_buffering
    udps/write_buffering
    udps/extended_swacc
