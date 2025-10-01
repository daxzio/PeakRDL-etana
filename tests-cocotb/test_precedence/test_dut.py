"""Test precedence property - sw vs hw write priority"""

from cocotb import test
from tb_base import testbench


@test()
async def test_dut_precedence(dut):
    """Test sw vs hw write precedence"""
    tb = testbench(dut)
    await tb.clk.wait_clkn(200)

    # Setup: Hardware continuously writes 0 to both fields
    tb.hwif_in_r1_f_sw.value = 0
    tb.hwif_in_r1_f_sw_we.value = 1
    tb.hwif_in_r1_f_hw.value = 0
    tb.hwif_in_r1_f_hw_we.value = 1
    await tb.clk.wait_clkn(2)

    # Verify both fields are 0, event counters are 0
    await tb.intf.read(0x0, 0b00)
    await tb.intf.read(0x4, 0x00)

    # Software writes 0b11 (3) three times while HW still writing 0
    await tb.intf.write(0x0, 0b11)
    await tb.intf.write(0x0, 0b11)
    await tb.intf.write(0x0, 0b11)

    # Both fields read as 0 (HW writes win)
    await tb.intf.read(0x0, 0x00)

    # Event counters show f_sw_count=3 (sw precedence field counted)
    await tb.intf.read(0x4, 0x03)

    await tb.clk.end_test()
