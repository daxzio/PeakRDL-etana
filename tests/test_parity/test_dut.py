import sys
from pathlib import Path

# Add parent directory to path to access shared test modules
test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))
from random import randint  # noqa: E402

from cocotb import start_soon  # noqa: E402
from cocotb import test  # noqa: E402
from cocotb.triggers import RisingEdge  # noqa: E402

from tb_base import testbench  # noqa: E402


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
