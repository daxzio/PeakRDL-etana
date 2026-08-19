"""Mixed design: internal reg, standard external mem, and early external mem."""

import sys
from pathlib import Path
from random import randint

from cocotb import test, start_soon
from cocotb.triggers import RisingEdge, ReadOnly

test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))

from tb_base import testbench

FAST_MEM_BASE = 0x0200
SLOW_MEM_BASE = 0x0100


async def _no_wait_states_fast_mem_only(dut):
    while True:
        await RisingEdge(dut.clk)
        await ReadOnly()
        if dut.s_apb_psel.value == 1 and dut.s_apb_penable.value == 1:
            addr = int(dut.s_apb_paddr.value)
            if addr >= FAST_MEM_BASE and dut.s_apb_pwrite.value == 0:
                assert (
                    dut.s_apb_pready.value == 1
                ), "wait state on early external mem read"


@test()
async def test_dut_early_external_mixed(dut):
    tb = testbench(dut)
    start_soon(_no_wait_states_fast_mem_only(dut))

    await tb.clk.wait_clkn(200)

    await tb.intf.write(0x0000, 0xA5A5A5A5)
    await tb.intf.read(0x0000, 0xA5A5A5A5)

    slow_val = randint(0, 0xFFFFFFFF)
    await tb.intf.write(SLOW_MEM_BASE, slow_val)
    await tb.intf.read(SLOW_MEM_BASE, slow_val)

    fast_val = randint(0, 0xFFFFFFFF)
    await tb.intf.write(FAST_MEM_BASE, fast_val)
    await tb.intf.read(FAST_MEM_BASE, fast_val)

    for _ in range(8):
        addr = FAST_MEM_BASE + randint(0, 15) * 4
        val = randint(0, 0xFFFFFFFF)
        await tb.intf.write(addr, val)
        await tb.intf.read(addr, val)

    for _ in range(8):
        addr = SLOW_MEM_BASE + randint(0, 15) * 4
        val = randint(0, 0xFFFFFFFF)
        await tb.intf.write(addr, val)
        await tb.intf.read(addr, val)

    await tb.clk.end_test(200)
