"""Test swacc/swmod - software access and modify strobes (simplified)"""

from cocotb import test
from tb_base import testbench


@test()
async def test_dut_swacc_swmod(dut):
    """Test basic swacc and swmod behavior"""
    tb = testbench(dut)
    await tb.clk.wait_clkn(200)

    # r2: swmod on rw field
    await tb.intf.read(0x1, 0x14)  # Initial value 20
    await tb.intf.write(0x1, 21)
    await tb.intf.read(0x1, 21)

    # r3: swmod with rclr (read-clear)
    await tb.intf.read(0x2, 0x1E)  # Initial 30
    await tb.intf.write(0x2, 0x2A)  # Write 42
    await tb.intf.read(0x2, 0x2A)
    await tb.intf.read(0x2, 0x00)  # rclr - cleared on read

    # r4: swacc and swmod
    await tb.intf.read(0x3, 0x12)
    await tb.intf.write(0x3, 0x34)
    await tb.intf.read(0x3, 0x34)

    await tb.clk.end_test()
