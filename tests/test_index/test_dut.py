import sys
from random import randint, shuffle
from pathlib import Path

# Add test root and local directory to path to access shared modules
module_dir = Path(__file__).parent
test_dir = module_dir.parent
sys.path.insert(0, str(test_dir))
sys.path.insert(0, str(module_dir))
from cocotb import test, start_soon  # noqa: E402

from tb_base import testbench  # noqa: E402
from external_reg_emulator import (  # noqa: E402
    ExternalRegArrayEmulator,
    ExternalMemEmulator,
)


@test()
async def test_dut_simple(dut):
    tb = testbench(dut)
    await tb.clk.wait_clkn(200)

    # Start emulator for the external register bank
    ext_regs = ExternalRegArrayEmulator(dut, tb.clk.clk)
    start_soon(ext_regs.run())
    ext_mem = ExternalMemEmulator(dut, tb.clk.clk)
    start_soon(ext_mem.run())

    def build_block_accesses(start_addr: int, count: int, mask: int):
        block = []
        for idx in range(count):
            addr = start_addr + (idx * 4)
            value = randint(0, 0xFFFFFFFF)
            block.append((addr, mask, value))
        return block

    accesses = []

    # regblock.a[31] occupies addresses 0x00-0x78
    accesses += build_block_accesses(0x0000, 31, 0x00FF00FF)

    # regblock.b[26] occupies addresses 0x7C-0xE0
    accesses += build_block_accesses(0x007C, 26, 0x00FF00FF)

    # regblock.c is a single 32-bit register at 0xF0
    accesses += build_block_accesses(0x00F0, 1, 0xFFFFFFFF)

    # regblock.d[8] occupies addresses 0xF8-0x114
    accesses += build_block_accesses(0x00F8, 8, 0x00FF00FF)

    # external reg e[8] occupies addresses 0x20C-0x22C
    accesses += build_block_accesses(0x020C, 8, 0x00FF00FF)

    # external mem mm[13] occupies addresses 0x300-0x330
    accesses += build_block_accesses(0x0300, 13, 0xFFFFFFFF)

    write_order = accesses[:]
    read_order = accesses[:]
    shuffle(write_order)
    shuffle(read_order)

    for addr, _mask, value in write_order:
        await tb.intf.write(addr, value)

    for addr, mask, value in read_order:
        await tb.intf.read(addr, value & mask)

    await tb.clk.end_test()
