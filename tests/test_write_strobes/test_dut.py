"""Test write strobes - selective byte writes using pstrb"""

from cocotb import test
from tb_base import testbench


@test()
async def test_dut_write_strobes(dut):
    """Test write strobe functionality"""
    tb = testbench(dut)
    await tb.clk.wait_clkn(200)

    await tb.intf.read(0x0, 0x0F0)

    await tb.intf.write(0x0, 0x555, strb=0x333)  # strb=0x3 -> bytes 0-1
    await tb.intf.read(0x0, 0x1E1)

    await tb.intf.write(0x0, 0x5AA, strb=0x333)
    await tb.intf.read(0x0, 0x0C3)

    # r2: Test write-zero-to-* with strobes
    await tb.intf.read(0x4, 0x0F0)
    await tb.intf.write(0x4, 0xAAA, strb=0x333)  # Only bytes 0-1
    await tb.intf.read(0x4, 0x1E1)
    await tb.intf.write(0x4, 0xA55, strb=0x333)
    await tb.intf.read(0x4, 0x0C3)

    # r3: Test write-to-clear/set with strobes
    await tb.intf.read(0x8, 0x0FF0)
    await tb.intf.write(0x8, 0x1234, strb=0xFF00)  # All bytes
    await tb.intf.read(0x8, 0xFF00)

    # r4: Test partial strobes
    await tb.intf.read(0xC, 0x00)
    await tb.intf.write(0xC, 0xFF, strb=0xF0)  # Upper bytes only
    await tb.intf.read(0xC, 0xF0)
    await tb.intf.write(0xC, 0x00, strb=0x3C)  # Middle bytes
    await tb.intf.read(0xC, 0xC0)

    await tb.clk.end_test()
