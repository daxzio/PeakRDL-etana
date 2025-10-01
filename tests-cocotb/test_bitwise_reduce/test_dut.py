"""Test bitwise reduction operations - anded, ored, xored"""

from cocotb import test
from cocotb.triggers import RisingEdge
from tb_base import testbench


@test()
async def test_dut_bitwise_reduce(dut):
    """Test bitwise reduction properties"""
    tb = testbench(dut)
    await tb.clk.wait_clkn(200)

    # Test 0x00: all zeros
    await tb.intf.write(0x0, 0x00)
    await RisingEdge(tb.clk.clk)
    assert tb.hwif_out_r1_f_anded.value == 0
    assert tb.hwif_out_r1_f_ored.value == 0
    assert tb.hwif_out_r1_f_xored.value == 0

    # Test 0x01: one bit set
    await tb.intf.write(0x0, 0x01)
    await RisingEdge(tb.clk.clk)
    assert tb.hwif_out_r1_f_anded.value == 0
    assert tb.hwif_out_r1_f_ored.value == 1
    assert tb.hwif_out_r1_f_xored.value == 1

    # Test 0x02: different bit set
    await tb.intf.write(0x0, 0x02)
    await RisingEdge(tb.clk.clk)
    assert tb.hwif_out_r1_f_anded.value == 0
    assert tb.hwif_out_r1_f_ored.value == 1
    assert tb.hwif_out_r1_f_xored.value == 1

    # Test 0x03: two bits set (even parity)
    await tb.intf.write(0x0, 0x03)
    await RisingEdge(tb.clk.clk)
    assert tb.hwif_out_r1_f_anded.value == 0
    assert tb.hwif_out_r1_f_ored.value == 1
    assert tb.hwif_out_r1_f_xored.value == 0  # XOR parity

    # Test 0xFE: almost all bits (7 bits, odd parity)
    await tb.intf.write(0x0, 0xFE)
    await RisingEdge(tb.clk.clk)
    assert tb.hwif_out_r1_f_anded.value == 0
    assert tb.hwif_out_r1_f_ored.value == 1
    assert tb.hwif_out_r1_f_xored.value == 1

    # Test 0xFF: all bits set (8 bits, even parity)
    await tb.intf.write(0x0, 0xFF)
    await RisingEdge(tb.clk.clk)
    assert tb.hwif_out_r1_f_anded.value == 1  # All bits 1
    assert tb.hwif_out_r1_f_ored.value == 1
    assert tb.hwif_out_r1_f_xored.value == 0  # Even parity

    await tb.clk.end_test()
