from random import randint
from cocotb import test

from interfaces.clkrst import ClkReset

from cocotbext.apb import ApbMaster
from cocotbext.apb import ApbBus


class testbench:
    def __init__(self, dut, reset_sense=1, period=10):

        self.regwidth = int(dut.G_REGWIDTH)
        self.mask = (2**self.regwidth) - 1
        self.incr = int(self.regwidth / 8)
        self.cr = ClkReset(dut, period, reset_sense=reset_sense, resetname="rst")
        self.dut = dut

        apb_prefix = "s_apb"
        self.bus = ApbBus.from_prefix(dut, apb_prefix)
        clk_name = "clk"
        self.intf = ApbMaster(self.bus, getattr(dut, clk_name))


@test()
async def test_dut_basic(dut):
    tb = testbench(dut, reset_sense=1)

    await tb.cr.wait_clkn(200)

    await tb.intf.read(0x0000, 0x0)
    await tb.intf.read(0x0004, 0x0)
    await tb.intf.read(0x0008, 0x0)
    x = []
    for i in range(3):
        x.append(randint(0, (2**32) - 1))
    await tb.intf.write(0x0000, x[0])
    await tb.intf.write(0x0004, x[1])
    await tb.intf.write(0x0008, x[2])
    await tb.intf.read(0x0000, x[0] & 0xFF)
    await tb.intf.read(0x0004, x[1] & 0xFF)
    await tb.intf.read(0x0008, x[2] & 0xFF)

    await tb.cr.end_test(200)
