import sys
from pathlib import Path

# Add parent directory to path to access shared test modules
test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))
from cocotb import test  # noqa: E402


from tb_base import testbench  # noqa: E402
from random import randint


def get_index(val, i, width=32):
    mask = 2**width - 1
    return (int(val.value) >> i * width) & mask


async def check_range(tb, addr, depth=32, width=32, hwr=False):
    incr = int(width / 8)
    lmask = (2 ** (width - 32)) - 1
    umask = 2**width - 1
    x = []
    for i in range(depth):
        x.append(randint(lmask, umask))

    for i in range(depth):
        if hwr:
            if i % 2 == 0:
                y = get_index(
                    tb.hwif_out_page_config32_hwnr_tout_max_upper, int(i / 2), 16
                )
                z = get_index(
                    tb.hwif_out_page_config32_hwnr_tout_max_lower, int(i / 2), 16
                )
            else:
                y = get_index(
                    tb.hwif_out_page_config32_hwnr_tout_min_upper, int(i / 2), 16
                )
                z = get_index(
                    tb.hwif_out_page_config32_hwnr_tout_min_lower, int(i / 2), 16
                )
            k = (z << 16) | y
            assert 0 == k
        await tb.intf.write(addr + (incr * i), x[i])
        await tb.clk.wait_clkn(2)
        if hwr:
            if i % 2 == 0:
                y = get_index(
                    tb.hwif_out_page_config32_hwnr_tout_max_upper, int(i / 2), 16
                )
                z = get_index(
                    tb.hwif_out_page_config32_hwnr_tout_max_lower, int(i / 2), 16
                )
            else:
                y = get_index(
                    tb.hwif_out_page_config32_hwnr_tout_min_upper, int(i / 2), 16
                )
                z = get_index(
                    tb.hwif_out_page_config32_hwnr_tout_min_lower, int(i / 2), 16
                )
            k = (z << 16) | y
            assert x[i] == k

    for i in range(depth):
        await tb.intf.read(addr + (incr * i), x[i])


@test()
async def test_dut_simple(dut):
    tb = testbench(dut)
    await tb.clk.wait_clkn(200)

    await tb.intf.read(0x0000, 0x00)
    await tb.intf.read(0x0004, 0x00)
    await tb.intf.read(0x0008, 0x00)
    await tb.intf.read(0x1000, 0x00)
    await tb.intf.read(0x2000, 0x00)
    await tb.intf.write(0x0000, 0xFFFFFFFF)
    await tb.intf.write(0x0004, 0xFFFFFFFF)
    await tb.intf.write(0x0008, 0xFFFFFFFF)
    await tb.intf.write(0x1000, 0xFFFFFFFF)
    await tb.intf.write(0x2000, 0xFFFFFFFF)
    await tb.intf.write(0x2004, 0xFFFFFFFF)
    await tb.intf.read(0x0000, 0x0)
    await tb.intf.read(0x0004, 0xFF)
    await tb.intf.read(0x0008, 0xFF)
    await tb.intf.read(0x1000, 0xFFFFFFFF)
    await tb.intf.read(0x2000, 0xFFFFFFFF)
    await tb.intf.read(0x2004, 0xFFFFFFFF)

    await check_range(tb, 0x1000, 16, 32)
    await check_range(tb, 0x2000, 16, 64)
    await check_range(tb, 0x3000, 8, 32)
    await check_range(tb, 0x4000, 8, 64)
    await check_range(tb, 0x5000, 16, 32, hwr=True)
    await check_range(tb, 0x6000, 16, 64)
    await check_range(tb, 0x7000, 8, 32)
    await check_range(tb, 0x8000, 8, 64)

    await tb.clk.end_test()
