from random import randint
from cocotb import test

from interfaces.clkrst import ClkReset
from interfaces.apb_driver import ApbDriver


class testbench:
    def __init__(self, dut, reset_sense=1, period=10):

        self.regwidth = int(dut.REGWIDTH)
        self.n_regs = int(dut.N_REGS)
        self.mask = (2**self.regwidth) - 1
        self.incr = int(self.regwidth / 8)
        self.cr = ClkReset(dut, period, reset_sense=reset_sense, resetname="rst")
        self.dut = dut

        self.intf = ApbDriver(dut)


@test()
async def test_dut_basic(dut):
    tb = testbench(dut, reset_sense=1)

    await tb.cr.wait_clkn(200)

    await tb.intf.read(0x0000, 0x1)
    x = []
    for i in range(tb.n_regs):
        x.append(randint(0, (2**64) - 1))

    for i in range(tb.n_regs):
        await tb.intf.write(0x0000 + (i * tb.incr), x[i])

    for i in range(tb.n_regs):
        z = randint(0, tb.n_regs - 1)
        y = x[z] & tb.mask
        await tb.intf.read(0x0000 + (z * tb.incr), y)
    for i in range(tb.n_regs):
        y = x[i] & tb.mask
        await tb.intf.read(0x0000 + (i * tb.incr), y)

    await tb.cr.end_test(200)
