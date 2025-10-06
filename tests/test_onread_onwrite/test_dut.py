"""
Test for onread and onwrite field behaviors.
Tests: rclr, rset, woset, woclr, wot, wzs, wzc, wzt, wclr, wset
"""

import sys
from pathlib import Path

# Add parent directory to path to access shared test modules
test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))
from cocotb import test  # noqa: E402
from tb_base import testbench  # noqa: E402


@test()
async def test_dut_onread_onwrite(dut):
    """Test onread and onwrite field side effects"""
    tb = testbench(dut)
    await tb.clk.wait_clkn(200)

    # r1: onread rclr (read-clear) and rset (read-set)
    await tb.intf.read(0x0, 0x0FF0)  # f1=0xF0, f2=0x0F
    await tb.intf.read(0x0, 0xFF00)  # After read: f1→0x00, f2→0xFF
    await tb.intf.write(0x0, 0x00FF)
    await tb.intf.read(0x0, 0x00FF)
    await tb.intf.read(0x0, 0xFF00)  # Side effects trigger again

    # r2: onwrite woset, woclr, wot (write-one-to-*)
    await tb.intf.read(0x4, 0x0F0)
    await tb.intf.write(0x4, 0x111)
    await tb.intf.read(0x4, 0x1E1)
    await tb.intf.write(0x4, 0x122)
    await tb.intf.read(0x4, 0x0C3)

    # r3: onwrite wzs, wzc, wzt (write-zero-to-*)
    await tb.intf.read(0x8, 0x0F0)
    await tb.intf.write(0x8, 0xEEE)
    await tb.intf.read(0x8, 0x1E1)
    await tb.intf.write(0x8, 0xEDD)
    await tb.intf.read(0x8, 0x0C3)

    # r4: onwrite wclr (write-clear) and wset (write-set)
    await tb.intf.read(0xC, 0x0FF0)
    await tb.intf.write(0xC, 0x1234)  # Any write clears f1, sets f2
    await tb.intf.read(0xC, 0xFF00)

    await tb.clk.end_test()
