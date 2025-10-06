"""Test enum field encoding"""

import sys
from pathlib import Path

# Add parent directory to path to access shared test modules
test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))
from cocotb import test  # noqa: E402
from tb_base import testbench  # noqa: E402


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
