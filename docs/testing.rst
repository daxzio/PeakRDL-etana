.. _testing:

Testing
=======

PeakRDL-etana includes a comprehensive test suite built with `Cocotb <https://docs.cocotb.org/>`_,
validating register block functionality across multiple CPU interfaces and configurations.

Test Framework Overview
-----------------------

The test suite validates:

* Basic register operations (read, write, reset values)
* All SystemRDL field types and properties
* Hardware interface signal behavior
* CPU interface error responses (NEW in v0.23)
* External registers and memories
* Counter fields, interrupts, and side effects
* Multiple CPU interfaces and configurations

Test Modes
----------

Tests can run in three different modes:

Etana Mode (Default)
^^^^^^^^^^^^^^^^^^^^

Tests the PeakRDL-etana generated RTL using Icarus Verilog:

.. code-block:: bash

    cd tests/test_simple
    make clean etana sim COCOTB_REV=1.9.2

Regblock Reference Mode
^^^^^^^^^^^^^^^^^^^^^^^

Tests against PeakRDL-regblock reference implementation using Verilator:

.. code-block:: bash

    make clean regblock sim COCOTB_REV=1.9.2 REGBLOCK=1

This validates that etana produces functionally equivalent RTL to the upstream project.

VHDL Mode
^^^^^^^^^

Tests VHDL generation (select tests only):

.. code-block:: bash

    make clean regblock-vhdl sim COCOTB_REV=1.9.2 GHDL=1

Key Test Cases
--------------

test_simple
^^^^^^^^^^^

Basic register operations and field types.

**Validates:**

* Register read/write operations
* Reset value initialization
* Basic field properties (sw, hw access)

test_cpuif_err_rsp
^^^^^^^^^^^^^^^^^^

CPU interface error response validation (NEW).

**Validates:**

* Error responses for unmapped addresses (``--err-if-bad-addr``)
* Error responses for forbidden reads/writes (``--err-if-bad-rw``)
* Read-only register write protection
* Write-only register read protection
* External register/memory error handling

**Register Map:**

.. code-block::

    0x00: r_rw   - Read/Write register (internal)
    0x04: r_r    - Read-only register (internal)
    0x08: r_w    - Write-only register (internal)
    0x0C: er_rw  - External R/W register
    0x10: er_r   - External read-only register
    0x14: er_w   - External write-only register
    0x18: <unmapped> - Generates error response
    0x20: mem_rw - External R/W memory
    0x28: mem_r  - External read-only memory
    0x30: mem_w  - External write-only memory

**Supported CPU Interfaces:**

* APB4 (validates ``pslverr`` signal)
* AXI4-Lite (validates ``rresp``/``bresp`` signals)
* AHB (validates ``hresp`` signal)
* Passthrough (validates ``rd_err``/``wr_err`` signals)

**Usage:**

.. code-block:: bash

    cd tests/test_cpuif_err_rsp
    make clean etana sim COCOTB_REV=1.9.2 CPUIF=apb4-flat

test_external
^^^^^^^^^^^^^

External register and memory validation.

**Validates:**

* External register protocol (req, ack, data)
* Read and write operations to external components
* External memory block access
* Hardware interface signal timing

test_counter_basics
^^^^^^^^^^^^^^^^^^^

Counter field type validation.

**Validates:**

* Increment and decrement counters
* Overflow/underflow behavior
* Counter reset and enable

test_field_types
^^^^^^^^^^^^^^^^

Comprehensive field type coverage.

**Validates:**

* All standard SystemRDL field types
* Field properties (onread, onwrite, etc.)
* Field access combinations

Running Tests
-------------

Run All Tests
^^^^^^^^^^^^^

Execute the complete test suite:

.. code-block:: bash

    cd tests
    ./test_all.sh

This runs all tests with default settings (Icarus Verilog, Cocotb 1.9.2).

Run Specific Test
^^^^^^^^^^^^^^^^^

Navigate to a test directory and run:

.. code-block:: bash

    cd tests/test_cpuif_err_rsp
    make clean etana sim COCOTB_REV=1.9.2

CPU Interface Selection
^^^^^^^^^^^^^^^^^^^^^^^

Test with different CPU interfaces:

.. code-block:: bash

    # APB4 (default)
    make sim CPUIF=apb4-flat

    # AXI4-Lite
    make sim CPUIF=axi4-lite-flat

    # AHB
    make sim CPUIF=ahb-flat

    # Passthrough
    make sim CPUIF=passthrough

Generate Waveforms
^^^^^^^^^^^^^^^^^^

Enable waveform generation for debugging:

.. code-block:: bash

    # Icarus (generates .fst file)
    make sim WAVES=1

    # View waveforms
    gtkwave sim_build/*.fst

Test Infrastructure
-------------------

Base Testbench
^^^^^^^^^^^^^^

All tests use ``tb_base.py`` which provides:

* Auto-detection of CPU interface type
* Clock and reset management
* Unified interface abstraction
* Common utility functions

Bus Wrappers
^^^^^^^^^^^^

Located in ``tests/interfaces/``:

* ``apb_wrapper.py`` - APB4 bus functional model
* ``axi_wrapper.py`` - AXI4-Lite bus functional model
* ``ahb_wrapper.py`` - AHB bus functional model
* ``passthrough.py`` - Passthrough protocol driver

All wrappers support the ``error_expected`` parameter for error response validation.

External Emulators
^^^^^^^^^^^^^^^^^^

Located in ``tests/test_cpuif_err_rsp/external_emulators.py``:

* ``SimpleExtRegEmulator`` - Read/write external register
* ``SimpleExtRegReadOnly`` - Read-only external register
* ``SimpleExtRegWriteOnly`` - Write-only external register
* ``SimpleExtMemEmulator`` - Read/write external memory
* ``SimpleExtMemReadOnly`` - Read-only external memory
* ``SimpleExtMemWriteOnly`` - Write-only external memory

**Features:**

* Auto-detection of field naming (regblock vs etana)
* Bit-enable mask support
* Single-cycle response latency
* Compatible with all CPU interfaces

Writing Tests
-------------

Basic Test Pattern
^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from cocotb import test
    from tb_base import testbench

    @test()
    async def test_my_feature(dut):
        """Test description"""
        tb = testbench(dut)

        # Write to register
        await tb.intf.write(0x00, 0x1234)

        # Read back and verify
        await tb.intf.read(0x00, 0x1234)

        await tb.clk.end_test()

Error Response Testing
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    @test()
    async def test_errors(dut):
        """Test error responses"""
        tb = testbench(dut)

        # Expect error on unmapped address
        await tb.intf.read(0xFF, 0, error_expected=True)

        # Expect error on write to read-only register
        await tb.intf.write(0x04, 0x5678, error_expected=True)

        await tb.clk.end_test()

External Register Testing
^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from cocotb import test, start_soon
    from tb_base import testbench
    from external_emulators import SimpleExtRegEmulator

    @test()
    async def test_external(dut):
        """Test external register"""
        tb = testbench(dut)

        # Create and start emulator
        ext_reg = SimpleExtRegEmulator(dut, tb.clk.clk, "hwif_out_my_reg")
        start_soon(ext_reg.run())

        # Set value in emulator
        ext_reg.value = 0xABCD
        await tb.clk.wait_clkn(2)

        # Read from CPU interface
        await tb.intf.read(0x10, 0xABCD)

        await tb.clk.end_test()

Test Directory Structure
------------------------

Each test follows this structure:

.. code-block::

    tests/test_<name>/
    ├── Makefile              # Includes ../tests.mak
    ├── regblock.rdl          # Register definition (copied from upstream)
    ├── test_dut.py           # Cocotb test implementation
    └── external_emulators.py # (Optional) External component emulators

Continuous Integration
----------------------

GitHub Actions workflows validate all tests across:

* **Python versions:** 3.8, 3.9, 3.10, 3.11, 3.12, 3.13
* **Simulators:** Icarus Verilog, Verilator
* **Cocotb version:** 1.9.2
* **Test modes:** Etana, Regblock reference

Workflows run on:

* Every push to branches
* Every pull request
* Weekly schedule (Sunday 1:00 AM)

Test workflows skip on tag pushes to avoid redundant runs during releases.

Troubleshooting
---------------

Common Issues
^^^^^^^^^^^^^

**ModuleNotFoundError: No module named 'cocotb'**

Activate the virtual environment:

.. code-block:: bash

    source ../venv.2.0.0/bin/activate

**Signal Name Mismatch**

Regblock and etana have different field naming conventions:

* **Regblock:** Includes field suffix (e.g., ``hwif_out_reg_wr_data_f``)
* **Etana:** No field suffix (e.g., ``hwif_out_reg_wr_data``)

The external emulators auto-detect this difference.

**Cocotb 2.0.0 + AXI4-Lite Compatibility**

Use Cocotb 1.9.2 for AXI4-Lite testing:

.. code-block:: bash

    make sim COCOTB_REV=1.9.2

Further Documentation
---------------------

For detailed test suite documentation, see ``tests/TEST_SUITE_README.md`` in the repository.

For test migration guidelines, see ``cursor_help/COCOTB_MIGRATION_GUIDE.md``.
