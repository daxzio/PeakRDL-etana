"""Test various reset signal types"""

from cocotb import test
from cocotb.triggers import RisingEdge, Timer
from tb_base import testbench


@test()
async def test_dut_reset_signals(dut):
    """Test different reset signal types and their behaviors"""
    tb = testbench(dut)

    # Initialize all reset signals to active state
    dut.root_cpuif_reset.value = 1
    tb.hwif_in_r2_my_reset.value = 1
    tb.hwif_in_r3_my_areset.value = 1
    tb.hwif_in_r4_my_reset_n.value = 0
    tb.hwif_in_r5_my_areset_n.value = 0
    tb.hwif_in_f2_reset.value = 1
    dut.r5f2_resetvalue.value = 0xABCD

    # Wait 2 cycles, then deassert all resets
    await tb.clk.wait_clkn(2)
    dut.rst.value = 0
    dut.root_cpuif_reset.value = 0
    tb.hwif_in_r2_my_reset.value = 0
    tb.hwif_in_r3_my_areset.value = 0
    tb.hwif_in_r4_my_reset_n.value = 1
    tb.hwif_in_r5_my_areset_n.value = 1
    tb.hwif_in_f2_reset.value = 0
    await tb.clk.wait_clkn(1)

    # Verify initial reset values
    await tb.intf.read(0x00, 0x5678_1234)
    await tb.intf.read(0x04, 0x5678_1234)
    await tb.intf.read(0x08, 0x5678_1234)
    await tb.intf.read(0x0C, 0x5678_1234)
    await tb.intf.read(0x10, 0xABCD_1234)

    # Write zeros to all registers
    for i in range(5):
        await tb.intf.write(i * 4, 0)

    # Verify all zeros
    await tb.intf.read(0x00, 0x0000_0000)
    await tb.intf.read(0x04, 0x0000_0000)
    await tb.intf.read(0x08, 0x0000_0000)
    await tb.intf.read(0x0C, 0x0000_0000)
    await tb.intf.read(0x10, 0x0000_0000)

    # Test standard rst (resets r1.f1 only, f2 is not affected)
    dut.rst.value = 1
    await RisingEdge(tb.clk.clk)
    dut.rst.value = 0
    await RisingEdge(tb.clk.clk)

    await tb.intf.read(0x00, 0x0000_1234)
    await tb.intf.read(0x04, 0x0000_0000)
    await tb.intf.read(0x08, 0x0000_0000)
    await tb.intf.read(0x0C, 0x0000_0000)
    await tb.intf.read(0x10, 0x0000_0000)

    # Write zeros again
    for i in range(5):
        await tb.intf.write(i * 4, 0)

    # Test r2 custom sync reset (my_reset)
    tb.hwif_in_r2_my_reset.value = 1
    await RisingEdge(tb.clk.clk)
    tb.hwif_in_r2_my_reset.value = 0
    await RisingEdge(tb.clk.clk)

    await tb.intf.read(0x00, 0x0000_0000)
    await tb.intf.read(0x04, 0x0000_1234)
    await tb.intf.read(0x08, 0x0000_0000)
    await tb.intf.read(0x0C, 0x0000_0000)
    await tb.intf.read(0x10, 0x0000_0000)

    # Write zeros again
    for i in range(5):
        await tb.intf.write(i * 4, 0)

    # Test r3 async reset (my_areset) - async so use Timer
    await tb.clk.wait_clkn(1)
    try:
        await Timer(2, unit="ns")
    except TypeError:
        await Timer(2, units="ns")
    tb.hwif_in_r3_my_areset.value = 1
    try:
        await Timer(1, unit="ns")
    except TypeError:
        await Timer(1, units="ns")
    tb.hwif_in_r3_my_areset.value = 0
    await tb.clk.wait_clkn(1)

    await tb.intf.read(0x00, 0x0000_0000)
    await tb.intf.read(0x04, 0x0000_0000)
    await tb.intf.read(0x08, 0x0000_1234)
    await tb.intf.read(0x0C, 0x0000_0000)
    await tb.intf.read(0x10, 0x0000_0000)

    # Write zeros again
    for i in range(5):
        await tb.intf.write(i * 4, 0)

    # Test r4 active-low sync reset (my_reset_n)
    tb.hwif_in_r4_my_reset_n.value = 0
    await RisingEdge(tb.clk.clk)
    tb.hwif_in_r4_my_reset_n.value = 1
    await RisingEdge(tb.clk.clk)

    await tb.intf.read(0x00, 0x0000_0000)
    await tb.intf.read(0x04, 0x0000_0000)
    await tb.intf.read(0x08, 0x0000_0000)
    await tb.intf.read(0x0C, 0x0000_1234)
    await tb.intf.read(0x10, 0x0000_0000)

    # Write zeros again
    for i in range(5):
        await tb.intf.write(i * 4, 0)

    # Test r5 active-low async reset (my_areset_n)
    await tb.clk.wait_clkn(1)
    try:
        await Timer(2, unit="ns")
    except TypeError:
        await Timer(2, units="ns")
    tb.hwif_in_r5_my_areset_n.value = 0
    try:
        await Timer(1, unit="ns")
    except TypeError:
        await Timer(1, units="ns")
    tb.hwif_in_r5_my_areset_n.value = 1
    await tb.clk.wait_clkn(1)

    await tb.intf.read(0x00, 0x0000_0000)
    await tb.intf.read(0x04, 0x0000_0000)
    await tb.intf.read(0x08, 0x0000_0000)
    await tb.intf.read(0x0C, 0x0000_0000)
    await tb.intf.read(0x10, 0x0000_1234)

    # Write zeros again
    for i in range(5):
        await tb.intf.write(i * 4, 0)

    # Test field-specific reset (f2_reset) with new reset value
    await RisingEdge(tb.clk.clk)
    tb.hwif_in_f2_reset.value = 1
    dut.r5f2_resetvalue.value = 0x3210
    await RisingEdge(tb.clk.clk)
    tb.hwif_in_f2_reset.value = 0

    await tb.intf.read(0x00, 0x5678_0000)
    await tb.intf.read(0x04, 0x5678_0000)
    await tb.intf.read(0x08, 0x5678_0000)
    await tb.intf.read(0x0C, 0x5678_0000)
    await tb.intf.read(0x10, 0x3210_0000)

    await tb.clk.end_test()
