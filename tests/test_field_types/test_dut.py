from cocotb import test

from interfaces.clkrst import ClkReset
from interfaces.apb_driver import ApbDriver


class testbench:
    def __init__(self, dut, reset_sense=1, period=10):

        self.cr = ClkReset(dut, period, reset_sense=reset_sense, resetname="rst")
        self.dut = dut

        self.intf = ApbDriver(dut)


@test()
async def test_dut_basic(dut):
    tb = testbench(dut, reset_sense=1)

    await tb.cr.wait_clkn(200)

    await tb.intf.read(0x0000, 10)
    #     await tb.intf.read(0x0000, 0xFF00)
    #     await tb.intf.write(0x0000, 0x00FF)
    #     await tb.intf.read(0x0000, 0x00FF)
    #     await tb.intf.read(0x0000, 0xFF00)
    #
    #     await tb.intf.read(0x0004, 0x0F0)
    #     await tb.intf.write(0x0004, 0x111)
    #     await tb.intf.read(0x0004, 0x1E1)
    #     await tb.intf.write(0x0004, 0x122)
    #     await tb.intf.read(0x0004, 0x0C3)
    #
    #     await tb.intf.read(0x0008, 0x0F0)
    #     await tb.intf.write(0x0008, 0xEEE)
    #     await tb.intf.read(0x0008, 0x1E1)
    #     await tb.intf.write(0x0008, 0xEDD)
    #     await tb.intf.read(0x0008, 0x0C3)
    #
    #     await tb.intf.read(0x000C, 0x0FF0)
    #     await tb.intf.write(0x000C, 0x1234)
    #     await tb.intf.read(0x000C, 0xFF00)

    await tb.cr.end_test(200)
