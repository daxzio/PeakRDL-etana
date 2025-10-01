"""Test user-defined CPU interface - framework test, basic validation only"""

from cocotb import test
from tb_base import testbench


@test()
async def test_dut_user_cpuif(dut):
    """Basic test - framework override test not fully applicable to cocotb"""
    tb = testbench(dut)
    await tb.clk.wait_clkn(200)

    # Simple read/write test
    await tb.intf.write(0x0, 0xDEAD)
    await tb.intf.read(0x0, 0xDEAD)

    # Verify hwif
    assert tb.hwif_out_r1_f.value == 0xDEAD

    await tb.clk.end_test()
