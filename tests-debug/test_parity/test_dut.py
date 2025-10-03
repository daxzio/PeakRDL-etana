from random import randint
from cocotb import test

from interfaces.clkrst import ClkReset
from cocotbext.apb import ApbMaster
from cocotbext.apb import ApbBus


def parity(x, width=32):
    parity = 1
    for i in range(width):
        bit = (x >> i) & 0x1
        parity = parity ^ bit
        print(i, parity, bit, f"0x{x:x}", bit)
    y = x | (parity << width)
    return y


class testbench:
    def __init__(self, dut, reset_sense=1, period=10):

        self.cr = ClkReset(dut, period, reset_sense=reset_sense, resetname="rst_n")
        self.dut = dut

        apb_prefix = "s_apb"
        self.bus = ApbBus.from_prefix(dut, apb_prefix)
        clk_name = "clk"
        self.intf = ApbMaster(self.bus, getattr(dut, clk_name))


@test()
async def test_dut_basic(dut):
    tb = testbench(dut, reset_sense=0)
    #     tb.hwif_in_main_sync_mult.value = 30

    await tb.cr.wait_clkn(200)

    await tb.intf.read(0x0000, 0)

    x = []
    for i in range(9):
        x.append(randint(0, 0xFFFFFFFF))
    await tb.intf.write(0x0000, x[0])
    for i in range(8):
        await tb.intf.write(0x1000 + (i * 4), x[i + 1])
    y = x[0] & 0x1FFFFFF
    await tb.intf.read(0x0000, y)
    for i in range(32):
        z = randint(0, 7)
        y = x[z + 1] & 0x1FFFFFF
        await tb.intf.read(0x1000 + (z * 4), y)

    x = randint(0, 0xFFFFFFFF)
    y = x & 0x1FFFFFF
    await tb.intf.write(0x0000, x)
    await tb.intf.read(0x0000, y)

    for i in range(8):
        x = randint(0, 0xFFFFFFFF)
        y = x & 0x1FFFFFF
        await tb.intf.write(0x1000 + (i * 4), x)
        await tb.intf.read(0x1000 + (i * 4), y)

    await tb.intf.write(0x0000, 0)
    await tb.cr.end_test(10)
    assert 0 == dut.i_top.parity_error.value
    dut.i_top.field_storage_r1_f1_value.value = 1
    await tb.cr.end_test(2)
    assert 1 == dut.i_top.parity_error.value
    await tb.intf.write(0x0000, 1)
    await tb.cr.end_test(2)
    assert 0 == dut.i_top.parity_error.value

    await tb.intf.write(0x1004, 0)
    await tb.cr.end_test(10)
    assert 0 == dut.i_top.parity_error.value
    dut.i_top.field_storage_r2_f1_value[1].value = 1
    await tb.cr.end_test(2)
    assert 1 == dut.i_top.parity_error.value
    await tb.intf.write(0x1004, 1)
    await tb.cr.end_test(2)
    assert 0 == dut.i_top.parity_error.value

    await tb.cr.end_test(200)
