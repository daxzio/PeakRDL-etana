"""Readback through the retimed fanin path.

N_REGS=20 keeps --rt-read-fanin enabled. The default test_read_fanin map has
one register, and the exporter turns the option off for that size.
"""

import sys
from pathlib import Path

test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))
from random import randint  # noqa: E402
from cocotb import test  # noqa: E402
from tb_base import testbench  # noqa: E402


@test()
async def test_dut_read_fanin_rt(dut):
    tb = testbench(dut)
    await tb.clk.wait_clkn(200)

    N_REGS = 20
    REGWIDTH = 32
    STRIDE = REGWIDTH // 8

    data = [randint(0, 2**REGWIDTH - 1) for _ in range(N_REGS)]

    for i in range(N_REGS):
        await tb.intf.read(i * STRIDE, 0x1)

    for i in range(N_REGS):
        await tb.intf.write(i * STRIDE, data[i])

    for i in range(N_REGS):
        await tb.intf.read(i * STRIDE, data[i])

    await tb.clk.end_test()
