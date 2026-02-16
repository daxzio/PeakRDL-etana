"""Test CPU interface error responses

This test verifies error response behavior for:
- Unmapped address access (if err_if_bad_addr is enabled)
- Forbidden read/write operations (if err_if_bad_rw is enabled)

Tests both regular registers and external memories/regfiles.
Includes test for overlapped registers with different read/write permissions.

Note: This test uses APB4 interface with both error modes enabled.
To test other configurations, regenerate RTL with different parameters.
"""

from cocotb import test, start_soon
from tb_base import testbench
from external_emulators import (
    SimpleExtMemEmulator,
    SimpleExtMemReadOnly,
    SimpleExtMemWriteOnly,
)


@test()
async def test_dut_cpuif_err_rsp(dut):
    """Test CPU interface error responses for unmapped addresses and forbidden R/W"""
    tb = testbench(dut)

    # Start external memory/regfile emulators
    mem_rw = SimpleExtMemEmulator(dut, tb.clk.clk, "hwif_out_mem_rw", num_entries=2)
    mem_ro = SimpleExtMemReadOnly(dut, tb.clk.clk, "hwif_out_mem_ro", num_entries=2)
    mem_wo = SimpleExtMemWriteOnly(dut, tb.clk.clk, "hwif_out_mem_wo", num_entries=2)
    external_rf = SimpleExtMemEmulator(
        dut, tb.clk.clk, "hwif_out_external_rf", num_entries=16
    )

    start_soon(mem_rw.run())
    start_soon(mem_ro.run())
    start_soon(mem_wo.run())
    start_soon(external_rf.run())

    await tb.clk.wait_clkn(200)

    # --------------------------------------------------------------------------
    # r_rw - sw=rw; hw=na; // Storage element
    # --------------------------------------------------------------------------
    addr = 0x0

    # Read initial value
    await tb.intf.read(addr, 40)

    # Write and read back
    await tb.intf.write(addr, 61)
    await tb.intf.read(addr, 61)

    # --------------------------------------------------------------------------
    # r_ro - sw=r; hw=na; // Wire/Bus - constant value
    # --------------------------------------------------------------------------
    addr = 0x4

    # Read constant value
    await tb.intf.read(addr, 80)

    # Try to write (should error if err_if_bad_rw enabled)
    await tb.intf.write(addr, 81, error_expected=True)

    # Verify value unchanged
    await tb.intf.read(addr, 80)

    # --------------------------------------------------------------------------
    # r_wo - sw=w; hw=r; // Storage element
    # --------------------------------------------------------------------------
    addr = 0x8

    # Try to read (should error if err_if_bad_rw enabled, returns 0)
    await tb.intf.read(addr, 0, error_expected=True)

    # Verify hardware sees initial value
    assert int(tb.hwif_out_r_wo_f.value) == 100, "Initial HW value mismatch"

    # Write new value
    await tb.intf.write(addr, 101)

    # Try to read again (still errors)
    await tb.intf.read(addr, 0, error_expected=True)

    # Verify hardware sees new value
    assert int(tb.hwif_out_r_wo_f.value) == 101, "Updated HW value mismatch"

    # --------------------------------------------------------------------------
    # Reading/writing from/to non-existing register
    # --------------------------------------------------------------------------
    addr = 0x18
    await tb.intf.read(addr, 0, error_expected=True)
    await tb.intf.write(addr, 0x8C, error_expected=True)

    # --------------------------------------------------------------------------
    # Reading/writing from/to combined read AND write only register (overlapped)
    # --------------------------------------------------------------------------
    addr = 0x1C

    # Read from readonly register (should succeed)
    await tb.intf.read(addr, 200)

    # Write to writeonly register (should succeed)
    await tb.intf.write(addr, 0x8C)

    # Read again (should still return readonly value)
    await tb.intf.read(addr, 200)

    # --------------------------------------------------------------------------
    # External memories
    # mem_rw - sw=rw;
    # --------------------------------------------------------------------------
    addr = 0x20

    # Set initial value
    mem_rw.mem[0] = 0x8C
    await tb.clk.wait_clkn(2)

    # Read value
    await tb.intf.read(addr, 0x8C)

    # Write and read back
    await tb.intf.write(addr, 0x8D)
    await tb.intf.read(addr, 0x8D)

    # --------------------------------------------------------------------------
    # mem_ro - sw=r;
    # --------------------------------------------------------------------------
    addr = 0x28

    # Set value in read-only memory
    mem_ro.mem[0] = 0xB4
    await tb.clk.wait_clkn(2)

    # Read value
    await tb.intf.read(addr, 0xB4)

    # Try to write (should error if err_if_bad_rw enabled)
    await tb.intf.write(addr, 0xB5, error_expected=True)

    # Verify value unchanged
    await tb.intf.read(addr, 0xB4)

    # --------------------------------------------------------------------------
    # mem_wo - sw=w;
    # --------------------------------------------------------------------------
    addr = 0x30

    # Set initial value in write-only memory
    mem_wo.mem[0] = 0xC8
    await tb.clk.wait_clkn(2)

    # Try to read (should error if err_if_bad_rw enabled)
    await tb.intf.read(addr, 0, error_expected=True)

    # Verify internal value unchanged
    assert (
        mem_wo.mem[0] == 0xC8
    ), "Write-only memory internal value changed unexpectedly"

    # Write new value
    await tb.intf.write(addr, 0xC9)
    await tb.clk.wait_clkn(2)

    # Try to read again (still errors)
    await tb.intf.read(addr, 0, error_expected=True)

    # Verify internal value updated
    assert mem_wo.mem[0] == 0xC9, "Write-only memory internal value not updated"

    # --------------------------------------------------------------------------
    # External regfile
    # external_rf - Contains registers at various addresses
    # --------------------------------------------------------------------------
    addr = 0x40

    # Read initial value (should be 0 from placeholder registers)
    await tb.intf.read(addr, 0x0)

    # Write and read back
    await tb.intf.write(addr, 0xD0)
    await tb.intf.read(addr, 0xD0)

    await tb.clk.end_test()
