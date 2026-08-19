"""Test early_external_read on external mem with a registered block RAM slave."""

import sys
from pathlib import Path
from random import randint

from cocotb import test, start_soon
from cocotb.triggers import RisingEdge, ReadOnly

test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))

from tb_base import testbench


async def _no_wait_states_apb(dut):
    while True:
        await RisingEdge(dut.clk)
        await ReadOnly()
        if dut.s_apb_psel.value == 1 and dut.s_apb_penable.value == 1:
            assert dut.s_apb_pready.value == 1, "wait state on external access"


@test()
async def test_dut_early_external_read(dut):
    tb = testbench(dut)
    #     tb.intf.enable_backpressure(rready=True)

    if hasattr(dut, "s_apb_penable"):
        start_soon(_no_wait_states_apb(dut))

    await tb.clk.wait_clkn(200)

    # Basic read/write
    x0 = randint(0, 0xFFFFFFFF)
    x1 = randint(0, 0xFFFFFFFF)
    await tb.intf.write(0x0010, x0)
    await tb.intf.write(0x0014, x1)
    await tb.intf.read(0x0010, x0)
    await tb.intf.read(0x0014, x1)

    # Back-to-back reads
    for _ in range(8):
        addr = 0x0020 + (randint(0, 15) * 4)
        val = randint(0, 0xFFFFFFFF)
        await tb.intf.write(addr, val)
        await tb.intf.read(addr, val)

    # Back-to-back writes
    for _ in range(8):
        addr = 0x0040 + (randint(0, 15) * 4)
        val = randint(0, 0xFFFFFFFF)
        await tb.intf.write(addr, val)

    # Mixed read/write
    for _ in range(16):
        if randint(0, 1):
            addr = randint(0, 15) * 4
            val = randint(0, 0xFFFFFFFF)
            await tb.intf.write(addr, val)
        else:
            addr = randint(0, 15) * 4
            val = randint(0, 0xFFFFFFFF)
            await tb.intf.write(addr, val)
            await tb.intf.read(addr, val)

    await tb.clk.end_test(200)
