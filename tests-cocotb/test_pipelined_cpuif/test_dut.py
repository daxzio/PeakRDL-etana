"""Test pipelined CPU interface - concurrent transactions"""

from cocotb import test, start_soon
from cocotb.triggers import RisingEdge
from tb_base import testbench


@test()
async def test_dut_pipelined_cpuif(dut):
    """Test CPU interface can handle pipelined/concurrent operations"""
    tb = testbench(dut)
    await tb.clk.wait_clkn(200)

    # Write all 64 registers in parallel burst
    async def write_all():
        for i in range(64):
            await tb.intf.write(i * 4, i + 0x12340000)

    await write_all()

    # Verify HW values
    await RisingEdge(tb.clk.clk)
    for i in range(64):
        expected = i + 0x12340000
        actual = (int(tb.hwif_out_x_x.value) >> i * 32) & 0xFFFFFFFF
        assert (
            actual == expected
        ), f"hwif_out.x[{i}] = 0x{actual:08x}, expected 0x{expected:08x}"

    # Read all registers in parallel burst
    for i in range(64):
        await tb.intf.read(i * 4, i + 0x12340000)

    # Mix read/writes on first 8 registers
    for i in range(8):
        await tb.intf.write(i * 4, i + 0x56780000)
        await tb.intf.read(i * 4, i + 0x56780000)

    await tb.clk.end_test()
