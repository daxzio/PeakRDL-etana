# from cocotb import start_soon
import sys
from pathlib import Path

# Add parent directory to path to access shared test modules
test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))
from cocotb import test  # noqa: E402

from tb_base import testbench  # noqa: E402


@test()
async def test_dut_simple(dut):
    tb = testbench(dut)
    await tb.clk.wait_clkn(200)

    await tb.intf.read(0x0000, 0x0)
    await tb.intf.read(0x0004, 0x0)
    await tb.intf.write(0x0000, 0x12345678)
    await tb.intf.write(0x0004, 0x9ABCDEF0)
    await tb.intf.read(0x0000, 0x12345678)
    await tb.intf.read(0x0004, 0x9ABCDEF0)

    await tb.clk.end_test()
