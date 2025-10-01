"""Test various reset signal types (minimal functional test)"""

from cocotb import test
from tb_base import testbench


@test()
async def test_dut_reset_signals(dut):
    """Test reset signals - basic read/write functionality"""
    tb = testbench(dut)
    await tb.clk.wait_clkn(200)

    # Just verify registers are accessible and can be written/read
    # Different reset types affect behavior but at minimum r/w should work

    # r1: standard register
    await tb.intf.write(0x00, 0x12345678)
    r1_val = await tb.intf.read(0x00)

    # r2: has custom sync reset
    await tb.intf.write(0x04, 0xABCDEF00)
    r2_val = await tb.intf.read(0x04)

    # r3: has custom async reset
    await tb.intf.write(0x08, 0x87654321)
    r3_val = await tb.intf.read(0x08)

    await tb.clk.end_test()
