from random import randint
from cocotb import start_soon
from cocotb import test

from cocotbext.apb import ApbBus
from cocotbext.apb import ApbMaster
from cocotbext.apb import ApbMonitor


from interfaces.clkreset import Clk
from interfaces.clkreset import Reset
from interfaces.detect_clk import detect_clk


class testbench:
    def __init__(self, dut, reset_sense=0):
        try:
            self.clk_freq = int(dut.G_CLK_FREQ.value)
        except AttributeError:
            self.clk_freq = 100000000
        self.datawidth = int(dut.G_DATAWIDTH.value)
        self.addrwidth = int(dut.G_ADDRWIDTH.value)

        period = 1000000000 / self.clk_freq
        self.clk = Clk(dut, period, clkname="clk")
        self.reset = Reset(dut, self.clk, reset_sense=reset_sense, resetname="resetn")

        apb_bus = ApbBus.from_prefix(dut, "s_apb")
        #         self.ram = ApbRam(apb_bus, self.clk.clk, size=2**10)
        self.intf = ApbMaster(apb_bus, getattr(dut, "clk"))
        self.mon = ApbMonitor(apb_bus, self.clk.clk)

        start_soon(detect_clk(self.clk.clk, "input_clk", self.clk_freq / 1000000))


@test()
async def test_apn_external(dut):
    tb = testbench(dut)

    await tb.clk.wait_clkn(200)

    x0 = randint(0, 0xFFFFFFFF)
    x1 = randint(0, 0xFFFFFFFF)
    await tb.intf.write(0x00000010, x0)
    await tb.intf.read(0x00000010, x0)
    await tb.intf.read(0x00000000, 0x12345678)

    await tb.intf.read(0x00001000)
    await tb.intf.read(0x00001004)
    await tb.intf.read(0x00001008)
    await tb.intf.read(0x0000100C)

    await tb.intf.read(0x00000000, 0x12345678)

    x0 = randint(0, 0xFFFFFFFF)
    x1 = randint(0, 0xFFFFFFFF)
    await tb.intf.write(0x00002000, x0)
    await tb.intf.write(0x00002004, x1)
    await tb.intf.read(0x00002000, x0)
    await tb.intf.read(0x00002004, x1)

    x0 = randint(0, 0xFFFFFFFF)
    x1 = randint(0, 0xFFFFFFFF)
    x2 = randint(0, 0xFFFFFFFF)
    x3 = randint(0, 0xFFFFFFFF)
    await tb.intf.write(0x00004000, x0)
    await tb.intf.write(0x00004004, x1)
    await tb.intf.write(0x00004008, x2)
    await tb.intf.write(0x0000400C, x3)
    await tb.intf.read(0x00004000, x0)
    await tb.intf.read(0x00004004, x1)
    await tb.intf.read(0x00004008, x2)
    await tb.intf.read(0x0000400C, x3)

    await tb.clk.wait_clkn(200)

    await tb.clk.end_test()
