"""Test bitwise reduction operations - anded, ored, xored"""

import sys
from pathlib import Path

# Add parent directory to path to access shared test modules
test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))
from cocotb import test  # noqa: E402
from cocotb.triggers import RisingEdge  # noqa: E402
from tb_base import testbench  # noqa: E402


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
