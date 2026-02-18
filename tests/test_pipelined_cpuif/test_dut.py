"""Test pipelined CPU interface - concurrent transactions"""

import sys
from pathlib import Path

# Add parent directory to path to access shared test modules
test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))
from cocotb import test
from cocotb.triggers import RisingEdge
from tb_base import testbench


@test()
async def test_dut_pipelined_cpuif(dut):
    """Test CPU interface can handle pipelined/concurrent operations"""
    tb = testbench(dut)
    await tb.clk.wait_clkn(200)

    for i in range(64):
        await tb.intf.write(i * 4, i + 0x12340000)

    # Verify HW values (storage updates 1 cycle after pready)
    await RisingEdge(tb.clk.clk)
    await RisingEdge(tb.clk.clk)
    for i in range(64):
        expected = i + 0x12340000
        # hwif_out_x is now an unpacked array - access element directly
        actual = int(tb.hwif_out_x[i].value) & 0xFFFFFFFF
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
