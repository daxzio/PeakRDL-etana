# from cocotb import start_soon
import sys
from pathlib import Path

# Add parent directory to path to access shared test modules
test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))
from cocotb import test  # noqa: E402

# from cocotbext.apb import ApbBus
# from cocotbext.apb import ApbMonitor
# from cocotbext.apb import ApbMaster
#
# from interfaces.clkreset import Clk
# from interfaces.clkreset import Reset

from tb_base import testbench  # noqa: E402

# class testbench:
#     def __init__(self, dut, reset_sense=1):
#
#         period = 10
#         self.clk = Clk(dut, period, clkname="clk")
#         self.reset = Reset(dut, self.clk, reset_sense=reset_sense, resetname="rst")
#
#         apb_bus = ApbBus.from_prefix(dut, "s_apb")
#         self.intf = ApbMaster(apb_bus, getattr(dut, "clk"))


@test()
async def test_dut_simple(dut):
    tb = testbench(dut)
    await tb.clk.wait_clkn(200)

    await tb.intf.read(0x0000, 0x11)

    await tb.clk.end_test()
