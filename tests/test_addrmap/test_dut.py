import sys
from pathlib import Path

# Add parent directory to path to access shared test modules
test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))
from cocotb import test  # noqa: E402


from tb_base import testbench  # noqa: E402
from random import randint


@test()
async def test_dut_simple(dut):
    tb = testbench(dut)
    await tb.clk.wait_clkn(200)

    await tb.intf.read(0x0000, 0x00)
    await tb.intf.read(0x0004, 0x00)
    await tb.intf.read(0x0008, 0x00)
    await tb.intf.read(0x0100, 0x00)
    await tb.intf.read(0x0200, 0x00)
    await tb.intf.write(0x0000, 0xFFFFFFFF)
    await tb.intf.write(0x0004, 0xFFFFFFFF)
    await tb.intf.write(0x0008, 0xFFFFFFFF)
    await tb.intf.write(0x0100, 0xFFFFFFFF)
    await tb.intf.write(0x1000, 0xFFFFFFFF)
    await tb.intf.write(0x1004, 0xFFFFFFFF)
    await tb.intf.read(0x0000, 0x0)
    await tb.intf.read(0x0004, 0xFF)
    await tb.intf.read(0x0008, 0xFF)
    await tb.intf.read(0x0100, 0xFFFFFFFF)
    await tb.intf.read(0x1000, 0xFFFFFFFF)
    await tb.intf.read(0x1004, 0xFFFFFFFF)

    x = []
    for i in range(64):
        x.append(randint(0, 0xFFFFFFFF))

    for i in range(64):
        await tb.intf.write(0x0100 + (4 * i), x[i])

    for i in range(64):
        await tb.intf.read(0x0100 + (4 * i), x[i])

    x = []
    for i in range(64):
        x.append(randint(0, 0xFFFFFFFFFFFFFFFF))

    for i in range(64):
        await tb.intf.write(0x1000 + (8 * i), x[i])

    for i in range(64):
        await tb.intf.read(0x1000 + (8 * i), x[i])

    x = []
    for i in range(32):
        x.append(randint(0, 0xFFFFFFFF))

    for i in range(32):
        await tb.intf.write(0x2000 + (4 * i), x[i])

    for i in range(32):
        await tb.intf.read(0x2000 + (4 * i), x[i])

    x = []
    for i in range(32):
        x.append(randint(0, 0xFFFFFFFFFFFFFFFF))

    for i in range(32):
        await tb.intf.write(0x3000 + (8 * i), x[i])

    for i in range(32):
        await tb.intf.read(0x3000 + (8 * i), x[i])

    await tb.clk.end_test()
