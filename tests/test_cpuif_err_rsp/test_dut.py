"""Test CPU interface error responses

This test verifies error response behavior for:
- Unmapped address access (if err_if_bad_addr is enabled)
- Forbidden read/write operations (if err_if_bad_rw is enabled)

Tests both regular registers and external registers/memories.

Note: This test uses APB4 interface with both error modes enabled.
To test other configurations, regenerate RTL with different parameters.
"""

from cocotb import test, start_soon
from tb_base import testbench
from external_emulators import (
    SimpleExtRegEmulator,
    SimpleExtRegReadOnly,
    SimpleExtRegWriteOnly,
    SimpleExtMemEmulator,
    SimpleExtMemReadOnly,
    SimpleExtMemWriteOnly,
)


@test()
async def test_dut_cpuif_err_rsp(dut):
    """Test CPU interface error responses for unmapped addresses and forbidden R/W"""
    tb = testbench(dut)

    # Start external register/memory emulators
    er_rw = SimpleExtRegEmulator(dut, tb.clk.clk, "hwif_out_er_rw")
    er_r = SimpleExtRegReadOnly(dut, tb.clk.clk, "hwif_out_er_r")
    er_w = SimpleExtRegWriteOnly(dut, tb.clk.clk, "hwif_out_er_w")
    mem_rw = SimpleExtMemEmulator(dut, tb.clk.clk, "hwif_out_mem_rw", num_entries=2)
    mem_r = SimpleExtMemReadOnly(dut, tb.clk.clk, "hwif_out_mem_r", num_entries=2)
    mem_w = SimpleExtMemWriteOnly(dut, tb.clk.clk, "hwif_out_mem_w", num_entries=2)

    start_soon(er_rw.run())
    start_soon(er_r.run())
    start_soon(er_w.run())
    start_soon(mem_rw.run())
    start_soon(mem_r.run())
    start_soon(mem_w.run())

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
    # r_r - sw=r; hw=na; // Wire/Bus - constant value
    # --------------------------------------------------------------------------
    addr = 0x4

    # Read constant value
    await tb.intf.read(addr, 80)

    # Try to write (should error)
    await tb.intf.write(addr, 81, error_expected=True)

    # Verify value unchanged
    await tb.intf.read(addr, 80)

    # --------------------------------------------------------------------------
    # r_w - sw=w; hw=r; // Storage element
    # --------------------------------------------------------------------------
    addr = 0x8

    # Try to read (should error, returns 0)
    await tb.intf.read(addr, 0, error_expected=True)

    # Verify hardware sees initial value
    assert int(tb.hwif_out_r_w_f.value) == 100, "Initial HW value mismatch"

    # Write new value
    await tb.intf.write(addr, 101)

    # Try to read again (still errors)
    await tb.intf.read(addr, 0, error_expected=True)

    # Verify hardware sees new value
    assert int(tb.hwif_out_r_w_f.value) == 101, "Updated HW value mismatch"

    # --------------------------------------------------------------------------
    # External registers
    # er_rw - sw=rw; hw=na; // Storage element
    # --------------------------------------------------------------------------
    addr = 0xC

    # Set initial value in emulator
    er_rw.value = 0x8C
    await tb.clk.wait_clkn(2)

    # Read value
    await tb.intf.read(addr, 0x8C)

    # Write and read back
    await tb.intf.write(addr, 0x8D)
    await tb.intf.read(addr, 0x8D)

    # --------------------------------------------------------------------------
    # er_r - sw=r; hw=na; // Wire/Bus - constant value
    # --------------------------------------------------------------------------
    addr = 0x10

    # Set value in read-only emulator
    er_r.value = 0xB4
    await tb.clk.wait_clkn(2)

    # Read value
    await tb.intf.read(addr, 0xB4)

    # Try to write (should error)
    await tb.intf.write(addr, 0xB5, error_expected=True)

    # Verify value unchanged
    await tb.intf.read(addr, 0xB4)

    # --------------------------------------------------------------------------
    # er_w - sw=w; hw=r; // Storage element
    # --------------------------------------------------------------------------
    addr = 0x14

    # Set initial value in write-only emulator
    er_w.value = 0xC8
    await tb.clk.wait_clkn(2)

    # Try to read (should error)
    await tb.intf.read(addr, 0, error_expected=True)

    # Verify internal value unchanged
    assert er_w.value == 0xC8, "Write-only register internal value changed unexpectedly"

    # Write new value
    await tb.intf.write(addr, 0xC9)
    await tb.clk.wait_clkn(2)

    # Try to read again (still errors)
    await tb.intf.read(addr, 0, error_expected=True)

    # Verify internal value updated
    assert er_w.value == 0xC9, "Write-only register internal value not updated"

    # --------------------------------------------------------------------------
    # Reading/writing from/to non-existing register
    # --------------------------------------------------------------------------
    addr = 0x18
    await tb.intf.read(addr, 0, error_expected=True)
    await tb.intf.write(addr, 0x8C, error_expected=True)

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
    # mem_r - sw=r;
    # --------------------------------------------------------------------------
    addr = 0x28

    # Set value in read-only memory
    mem_r.mem[0] = 0xB4
    await tb.clk.wait_clkn(2)

    # Read value
    await tb.intf.read(addr, 0xB4)

    # Try to write (should error)
    await tb.intf.write(addr, 0xB5, error_expected=True)

    # Verify value unchanged
    await tb.intf.read(addr, 0xB4)

    # --------------------------------------------------------------------------
    # mem_w - sw=w;
    # --------------------------------------------------------------------------
    addr = 0x30

    # Set initial value in write-only memory
    mem_w.mem[0] = 0xC8
    await tb.clk.wait_clkn(2)

    # Try to read (should error)
    await tb.intf.read(addr, 0, error_expected=True)

    # Verify internal value unchanged
    assert mem_w.mem[0] == 0xC8, "Write-only memory internal value changed unexpectedly"

    # Write new value
    await tb.intf.write(addr, 0xC9)
    await tb.clk.wait_clkn(2)

    # Try to read again (still errors)
    await tb.intf.read(addr, 0, error_expected=True)

    # Verify internal value updated
    assert mem_w.mem[0] == 0xC9, "Write-only memory internal value not updated"

    await tb.clk.end_test()
