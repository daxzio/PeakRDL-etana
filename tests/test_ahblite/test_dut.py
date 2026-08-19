import sys
from pathlib import Path

# Add parent directory to path to access shared test modules
test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))
from cocotb import test  # noqa: E402

from tb_base import testbench  # noqa: E402
from cocotbext.ahb import AHBWrite


@test()
async def test_dut_simple(dut):
    tb = testbench(dut)
    await tb.clk.wait_clkn(200)

    await tb.intf.custom(
        [0x0010, 0x0004, 0x0018, 0x000C], [0x12, 0x34, 0x56, 0x78], mode=[1, 1, 1, 1]
    )
    #     await tb.intf.write(0x0004, 0x34)
    #     await tb.intf.write(0x0008, 0x56)
    #     await tb.intf.write(0x000c, 0x78)

    await tb.intf.read(0x0010, 0x12)
    await tb.intf.read(0x0004, 0x34)
    await tb.intf.read(0x0018, 0x56)
    await tb.intf.read(0x000C, 0x78)

    await tb.clk.end_test()
