# from cocotb import start_soon
from cocotb import test

# from cocotbext.apb import ApbBus
# from cocotbext.apb import ApbMonitor
# from cocotbext.apb import ApbMaster
#
# from interfaces.clkreset import Clk
# from interfaces.clkreset import Reset

from tb_base import testbench

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
