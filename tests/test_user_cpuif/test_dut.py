"""Test user-defined CPU interface - framework test, basic validation only"""

import sys
from pathlib import Path

# Add parent directory to path to access shared test modules
test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))
from cocotb import test  # noqa: E402
from tb_base import testbench  # noqa: E402


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
