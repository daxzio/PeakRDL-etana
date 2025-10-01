from random import randint

from cocotb import start_soon
from cocotb import test
from cocotb.triggers import RisingEdge

from tb_base import testbench


async def detect_parity_error(
    clk,
    parity_error,
):
    while True:
        await RisingEdge(clk)
        assert parity_error.value == 0


@test()
async def test_dut_parity(dut):
    tb = testbench(dut)
    parity_error = dut.parity_error

    await tb.clk.wait_clkn(200)
    start_soon(detect_parity_error(tb.clk.clk, parity_error))

    for i in range(50):
        j = randint(0, 8)
        await tb.intf.write(0x0000, randint(0, 0xFFFFFFFF))
        await tb.intf.write(0x1000 + j * 4, randint(0, 0xFFFFFFFF))

    await tb.intf.write(0x0000, 0x0)
    await tb.clk.wait_clkn(2)
    assert parity_error.value == 0

    await tb.intf.write(0x0000, 0x12345678)
    await tb.clk.wait_clkn(2)
    assert parity_error.value == 0

    await tb.intf.read(0x0000, 0x00345678)
    await tb.clk.wait_clkn(2)
    assert parity_error.value == 0

    await tb.clk.end_test()
