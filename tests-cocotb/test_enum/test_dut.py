"""Test enum field encoding"""

from cocotb import test
from tb_base import testbench


@test()
async def test_dut_enum(dut):
    """Test enum values in field encoding"""
    tb = testbench(dut)
    await tb.clk.wait_clkn(200)

    # Enum values from RDL: val_1=3, val_2=4
    VAL_1 = 3
    VAL_2 = 4

    # Check initial value (should be val_2)
    await tb.intf.read(0x0, VAL_2)

    # Write val_1
    await tb.intf.write(0x0, VAL_1)

    # Read back val_1
    await tb.intf.read(0x0, VAL_1)

    await tb.clk.end_test()
