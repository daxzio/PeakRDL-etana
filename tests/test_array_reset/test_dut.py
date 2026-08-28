"""Test per-element reset values in arrayed regfiles."""

import sys
from pathlib import Path

test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))
from cocotb import test
from tb_base import testbench


@test()
async def test_dut_array_reset(dut):
    tb = testbench(dut)
    await tb.clk.wait_clkn(200)

    await tb.intf.read(0x0000, 0x0)
    await tb.intf.read(0x0004, 0x0)
    await tb.intf.read(0x0008, 0xA)
    await tb.intf.read(0x000C, 0xB)

    await tb.clk.end_test()
