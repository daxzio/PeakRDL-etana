# from cocotb import start_soon
import sys
from pathlib import Path
from random import randint

# Add parent directory to path to access shared test modules
test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))
from cocotb import test  # noqa: E402

from tb_base import testbench  # noqa: E402


@test()
async def test_dut_simple(dut):
    tb = testbench(dut)
    mask = 0xFFFFFFFF
    await tb.clk.wait_clkn(200)

    x0 = randint(0, mask)
    await tb.intf.write(0x0000, x0)
    await tb.intf.read(0x0000, x0)

    x0 = randint(0, mask)
    await tb.intf.write(0x0100, x0)
    await tb.intf.read(0x0100, x0)

    await tb.clk.end_test()
