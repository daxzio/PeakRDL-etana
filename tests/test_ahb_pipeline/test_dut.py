import sys
from random import randint
from pathlib import Path

# Add parent directory to path to access shared test modules
test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))
from cocotb import test, start_soon  # noqa: E402

from external_reg_emulator_simple import (  # noqa: E402
    ExtRegArrayEmulator,
    ExternalMemEmulator,
)

from tb_base import testbench  # noqa: E402


class testbench_ahb(testbench):
    def __init__(
        self,
        dut,
        reset_sense=1,
        reset_length=2,
        r2_ack_delay=(1, 5),
        r3_ack_delay=(1, 5),
    ):
        super().__init__(dut, reset_sense, reset_length)
        from cocotbext.ahb import AHBMonitor

        # External emulators with randomised ack delay (1-5 cycles) to stress pipeline
        self.ext_r2_emulator = ExtRegArrayEmulator(
            dut, self.clk.clk, prefix="r2", ack_delay=r2_ack_delay
        )
        self.ext_r3_emulator = ExternalMemEmulator(
            dut, self.clk.clk, prefix="r3", ack_delay_cycles=r3_ack_delay
        )
        start_soon(self.ext_r2_emulator.run())
        start_soon(self.ext_r3_emulator.run())


@test()
async def test_dut_simple(dut):
    tb = testbench_ahb(dut)
    mask = tb.intf.mask
    incr = tb.intf.incr
    await tb.clk.wait_clkn(200)

    #     await tb.intf.custom(
    #        [0x0010, 0x0004, 0x0018, 0x000c],
    #        [0x12, 0x34, 0x56, 0x78],
    #        mode=[1, 1, 1, 1]
    #    )
    #
    #     await tb.intf.read(0x0010, 0x12)
    #     await tb.intf.read(0x0004, 0x34)
    #     await tb.intf.read(0x0018, 0x56)
    #     await tb.intf.read(0x000c, 0x78)
    #
    x0 = randint(0, mask)
    x1 = randint(0, mask)
    x2 = randint(0, mask)
    x3 = randint(0, mask)
    await tb.intf.write(0x001C, x0)
    await tb.intf.write(0x0008, x1)
    await tb.intf.write(0x0014, x2)
    await tb.intf.write(0x0020, x3)

    await tb.intf.custom(
        [0x0008, 0x001C, 0x0020, 0x0014], [x0, x1, x2, x3], mode=[0, 0, 0, 0]
    )
    await tb.intf.read(0x001C, x0)
    await tb.intf.read(0x0008, x1)
    await tb.intf.read(0x0014, x2)
    await tb.intf.read(0x0020, x3)

    x0 = randint(0, mask)
    x1 = randint(0, mask << 32)
    x2 = randint(0, mask << 96)
    x3 = randint(0, mask)
    await tb.intf.write(0x0010, x0, length=incr)
    await tb.intf.write(0x0020, x1, length=incr * 2)
    await tb.intf.write(0x0030, x2, length=incr * 4)

    await tb.intf.read(0x0010, x0)
    await tb.intf.read(0x0020 + (0 * incr), (x1 & mask))
    await tb.intf.read(0x0020 + (1 * incr), ((x1 >> 32) & mask))
    await tb.intf.read(0x0020, x1, length=incr * 2)
    await tb.intf.read(0x0030 + (0 * incr), (x2 & mask))
    await tb.intf.read(0x0030 + (1 * incr), ((x2 >> 32) & mask))
    await tb.intf.read(0x0030 + (2 * incr), ((x2 >> 64) & mask))
    await tb.intf.read(0x0030 + (3 * incr), ((x2 >> 96) & mask))
    await tb.intf.read(0x0030, x2, length=incr * 4)

    # External array (r2) accesses
    await tb.intf.read(0x84)
    await tb.intf.write(0x84, 0x12345678)
    await tb.intf.read(0x80)
    await tb.intf.read(0x84, 0x12345678)

    # External memory window (r3) accesses
    await tb.intf.read(0x110)
    await tb.intf.write(0x110, 0xFEEDFACE)
    await tb.intf.write(0x114, 0xC001D00D)
    await tb.intf.read(0x110, 0xFEEDFACE)
    await tb.intf.read(0x114, 0xC001D00D)

    x2 = randint(0, mask << 96)
    await tb.intf.write(0x120, x2, length=incr * 4)
    await tb.intf.read(0x110, 0xFEEDFACE)
    await tb.intf.read(0x114, 0xC001D00D)
    await tb.intf.read(0x120, x2, length=incr * 4)

    await tb.clk.end_test()
