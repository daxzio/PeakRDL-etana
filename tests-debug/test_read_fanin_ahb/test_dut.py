import logging
import math
from random import randint
from cocotb import test

from interfaces.clkrst import ClkReset

from cocotbext.ahb import AHBBus
from cocotbext.ahb import AHBMaster
from cocotbext.daxzio.ahb_wrapper import AHBMonitorDX
from cocotbext.daxzio.ahb_wrapper import AHBLiteMasterDX


class testbench:
    def __init__(self, dut, reset_sense=0, period=10):

        self.regwidth = int(dut.REGWIDTH)
        self.n_regs = int(dut.N_REGS)
        self.mask = (2**self.regwidth) - 1
        self.incr = int(self.regwidth / 8)
        self.cr = ClkReset(dut, period, reset_sense=reset_sense, resetname="rst_n")
        self.dut = dut

        clk_name = "clk"
        ahb_prefix = "s_ahb"
        self.bus = AHBBus.from_prefix(dut, ahb_prefix)
        self.intf = AHBLiteMasterDX(
            self.bus, getattr(dut, clk_name), getattr(dut, "rst_n")
        )
        self.intf.log.setLevel(logging.DEBUG)
        self.mon = AHBMonitorDX(self.bus, getattr(dut, clk_name), getattr(dut, "rst_n"))
        self.mon.enable_write_logging()
        self.mon.enable_read_logging()


# @test()
# async def test_dut_basic(dut):
#     tb = testbench(dut)
#
#     await tb.cr.wait_clkn(200)
#
#     await tb.intf.read(0x0000, 0x1)
#
#     await tb.intf.write(0x0000, 0x12345678)
#     await tb.intf.read(0x0000, 0x12345678)
#
#     x = []
#     for i in range(tb.n_regs):
#         x.append(randint(0, tb.mask))
#
#     for i in range(tb.n_regs):
#         await tb.intf.write(0x0000 + (i * tb.incr), x[i])
#
#     for i in range(tb.n_regs):
#         z = randint(0, tb.n_regs - 1)
#         y = x[z] & tb.mask
#         await tb.intf.read(0x0000 + (z * tb.incr), y)
#     for i in range(tb.n_regs):
#         y = x[i] & tb.mask
#         await tb.intf.read(0x0000 + (i * tb.incr), y)


@test()
async def test_dut_ahb(dut):
    tb = testbench(dut)

    await tb.cr.wait_clkn(200)

    #     await tb.intf.read(0x0000, 0x1)

    #     await tb.intf.write(0x0000, 0x12345678)
    #     await tb.intf.read(0x0000, 0x12345678)
    #
    #     await tb.intf.write(0x0000+tb.incr, 0)
    #     await tb.intf.write(0x0000+tb.incr, 0x12345678, size=1)
    #     await tb.intf.read(0x0000+tb.incr, 0x00000078)
    #     await tb.intf.write(0x0000+tb.incr, 0)
    #     await tb.intf.write(0x0000+tb.incr+1, 0x12345678, size=1)
    #     await tb.intf.read(0x0000+tb.incr, 0x00007800)
    #     await tb.intf.read(0x0000+tb.incr+1, 0x78, size=1)
    #     await tb.intf.write(0x0000+tb.incr, 0)
    #     await tb.intf.write(0x0000+tb.incr+2, 0x12345678, size=1)
    #     await tb.intf.read(0x0000+tb.incr, 0x00780000)
    #     await tb.intf.read(0x0000+tb.incr+2, 0x78, size=1)
    #     await tb.intf.write(0x0000+tb.incr, 0)
    #     await tb.intf.write(0x0000+tb.incr+3, 0x12345678, size=1)
    #     await tb.intf.read(0x0000+tb.incr, 0x78000000)
    #     await tb.intf.read(0x0000+tb.incr+3, 0x78, size=1)
    #
    #
    #     x0 = randint(0, tb.mask)
    #     await tb.intf.write(0x0000+tb.incr, 0)
    #     await tb.intf.write(0x0000+tb.incr, x0, size=2)
    #     await tb.intf.read(0x0000+tb.incr, x0 & 0xffff)
    #
    #     x0 = randint(0, tb.mask)
    #     await tb.intf.write(0x0000+tb.incr, 0)
    #     await tb.intf.write(0x0000+tb.incr+2, x0, size=2)
    #     await tb.intf.read(0x0000+tb.incr, (x0 & 0xffff) << 16)
    #     await tb.intf.read(0x0000+tb.incr+2, x0 & 0xffff, size=2)
    instances = int(math.log2(tb.regwidth / 4))
    #     print(instances)
    for j in range(instances):
        power = 2**j
        #         # Use register mask for full-width accesses to avoid overflow
        #         if power*8 >= tb.regwidth:
        #             power_mask = tb.mask
        #         else:

        power_mask = (2 ** (power * 8)) - 1
        for i in range(int(tb.regwidth / (8 * power))):
            addr = 0x0000 + tb.incr
            x0 = randint(0, tb.mask)
            # For full-width access, don't apply any mask
            #             if power*8 >= tb.regwidth:
            #                 x0_byte = x0
            #                 expected = x0_byte
            #             else:
            x0_byte = x0 & power_mask
            expected = x0_byte << (i * (8 * power))
            await tb.intf.write(addr, 0)
            await tb.intf.write(addr + i * power, x0, size=power)
            await tb.intf.read(addr, expected)
            await tb.intf.read(addr + i * power, x0_byte, size=power)

    await tb.cr.end_test(200)
