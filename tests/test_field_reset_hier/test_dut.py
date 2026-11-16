"""field_reset inherited from an addrmap, regfile, or above the top.

Each register is loaded with a sentinel, then one reset is pulsed. The readback
has to show that only the fields whose nearest field_reset (or explicit
resetsignal) is that signal return to their reset value.
"""

import inspect
import sys
from pathlib import Path

test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))
from cocotb import test  # noqa: E402
from cocotb.triggers import Timer  # noqa: E402
from tb_base import testbench  # noqa: E402

# cocotb 1.x names the argument "units"; 2.x names it "unit".
_TIMER_KW = "unit" if "unit" in inspect.signature(Timer).parameters else "units"

# Byte addresses of every software-visible word.
WORDS = (
    0x00,  # map_reg, both fields follow map_rst
    0x04,  # split_reg.lo = root_rst, split_reg.hi = map_rst
    0x08,  # plain_reg, explicit resetsignal, not a field_reset
    0x0C,  # no reset value; inherited map_rst must not load it
    0x20,
    0x24,
    0x28,
    0x2C,  # map_arr[4], all follow map_rst
    0x30,  # regfile with no field_reset of its own
    0x40,  # blk.rf_reg follows blk.rf_rst
    0x44,  # local_reg.lo = reg_rst, local_reg.hi = map_rst
    0x48,  # nested regfile with no signal inherits blk.rf_rst
    0x4C,  # active-low async
    0x50,  # wide register, low subword
    0x54,  # wide register, high subword
    0x60,  # active-high async
)

# Value present after every field reset has been applied.
RESET = {
    0x00: 0xA002A001,
    0x04: 0xB002B001,
    0x08: 0xC002C001,
    0x20: 0x000000D1,
    0x24: 0x000000D1,
    0x28: 0x000000D1,
    0x2C: 0x000000D1,
    0x30: 0x00001901,
    0x40: 0xE002E001,
    0x44: 0xF002F001,
    0x48: 0x00001111,
    0x4C: 0x00002222,
    0x50: 0x55556666,
    0x54: 0x33334444,
    0x60: 0x0000A5A5,
}

SENTINEL = 0x5A5A5A5A
NORESET = 0x0C
NORESET_VALUE = 0xA5A5A5A5
WIDE_HI = 0x54
WIDE_HI_SENTINEL = 0xA5A5A5A5

# Bits that actually read back. Narrow fields drop the rest of the word.
WIDTH = {
    0x00: 32,
    0x04: 32,
    0x08: 32,
    0x0C: 32,
    0x20: 8,
    0x24: 8,
    0x28: 8,
    0x2C: 8,
    0x30: 16,
    0x40: 32,
    0x44: 32,
    0x48: 16,
    0x4C: 16,
    0x50: 32,
    0x54: 32,
    0x60: 16,
}


def visible(addr, value):
    width = WIDTH[addr]
    if width >= 32:
        return value & 0xFFFFFFFF
    return value & ((1 << width) - 1)


def sentinel_image():
    image = {}
    for addr in WORDS:
        if addr == NORESET:
            raw = NORESET_VALUE
        elif addr == WIDE_HI:
            raw = WIDE_HI_SENTINEL
        else:
            raw = SENTINEL
        image[addr] = visible(addr, raw)
    return image


def paint(image, addr, hi=None, lo=None, word=None):
    """Replace one 32-bit word, or one 16-bit half of it."""
    if word is not None:
        image[addr] = word
        return
    current = image[addr]
    if lo is None:
        lo = current & 0xFFFF
    if hi is None:
        hi = (current >> 16) & 0xFFFF
    image[addr] = ((hi & 0xFFFF) << 16) | (lo & 0xFFFF)


async def delay_ns(duration):
    await Timer(duration, **{_TIMER_KW: "ns"})


@test()
async def test_dut_field_reset_hier(dut):
    tb = testbench(dut, reset_sense=None)
    expected = {}

    rst = dut.rst
    root_rst = dut.root_rst
    map_rst = tb.hwif_in_map_rst
    plain_rst = tb.hwif_in_plain_rst
    rf_rst = tb.hwif_in_blk_rf_rst
    reg_rst = tb.hwif_in_blk_local_reg_reg_rst
    async_rst_n = tb.hwif_in_blk_async_rf_async_rst_n
    a_rst = tb.hwif_in_a_blk_a_rst

    async def check(label):
        for addr in WORDS:
            if addr not in expected:
                continue
            try:
                await tb.intf.read(addr, expected[addr])
            except Exception as exc:
                raise AssertionError(
                    f"{label}: [0x{addr:02X}] expected 0x{expected[addr]:08X} ({exc})"
                ) from exc

    async def load_sentinels():
        expected.clear()
        expected.update(sentinel_image())
        for addr, value in expected.items():
            await tb.intf.write(addr, value)
        await tb.clk.wait_clkn(1)

    async def clocked_pulse(sig, active, inactive):
        sig.value = active
        await tb.clk.wait_clkn(1)
        sig.value = inactive
        await tb.clk.wait_clkn(1)

    async def midcycle_pulse(sig, active, inactive):
        # Leave the signal inactive at the surrounding clock edges. A
        # synchronous reset must ignore this. An asynchronous one must not.
        await tb.clk.wait_clkn(1)
        await delay_ns(2)
        sig.value = active
        await delay_ns(1)
        sig.value = inactive
        await tb.clk.wait_clkn(1)

    # Bring up every reset, including the bus reset, then release them.
    rst.value = 1
    root_rst.value = 1
    map_rst.value = 1
    plain_rst.value = 1
    rf_rst.value = 1
    reg_rst.value = 1
    a_rst.value = 1
    async_rst_n.value = 0
    await tb.clk.wait_clkn(2)
    rst.value = 0
    root_rst.value = 0
    map_rst.value = 0
    plain_rst.value = 0
    rf_rst.value = 0
    reg_rst.value = 0
    a_rst.value = 0
    async_rst_n.value = 1
    await tb.clk.wait_clkn(1)

    expected.update(RESET)
    await check("all field resets applied at start")

    await load_sentinels()
    await check("sentinels written")

    # Synchronous resets must not fire on a pulse that misses the clock edge.
    for sig in (map_rst, root_rst, plain_rst, rf_rst, reg_rst, rst):
        await midcycle_pulse(sig, 1, 0)
    await check("sync resets ignore a pulse between clocks")

    await clocked_pulse(rst, 1, 0)
    await check("module rst does not reset these fields")

    await clocked_pulse(map_rst, 1, 0)
    paint(expected, 0x00, word=0xA002A001)
    paint(expected, 0x04, hi=0xB002)
    for addr in (0x20, 0x24, 0x28, 0x2C):
        paint(expected, addr, word=0x000000D1)
    paint(expected, 0x30, word=0x00001901)
    paint(expected, 0x44, hi=0xF002)
    await check("map_rst resets addrmap-inherited fields only")

    await load_sentinels()
    await clocked_pulse(root_rst, 1, 0)
    paint(expected, 0x04, lo=0xB001)
    await check("root_rst is the above-top signal named by split_reg.lo")

    await load_sentinels()
    await clocked_pulse(plain_rst, 1, 0)
    paint(expected, 0x08, word=0xC002C001)
    await check("explicit resetsignal beats the inherited field_reset")

    await load_sentinels()
    await clocked_pulse(rf_rst, 1, 0)
    paint(expected, 0x40, word=0xE002E001)
    paint(expected, 0x48, word=0x00001111)
    paint(expected, 0x50, word=0x55556666)
    paint(expected, 0x54, word=0x33334444)
    await check("rf_rst shadows map_rst for the regfile and its child")

    await load_sentinels()
    await clocked_pulse(reg_rst, 1, 0)
    paint(expected, 0x44, lo=0xF001)
    await check("register field_reset shadows the regfile signal")

    await load_sentinels()
    await midcycle_pulse(a_rst, 1, 0)
    paint(expected, 0x60, word=0x0000A5A5)
    await check("active-high async field_reset")

    await load_sentinels()
    await midcycle_pulse(async_rst_n, 0, 1)
    paint(expected, 0x4C, word=0x00002222)
    await check("active-low async field_reset")

    # noreset_reg was written once and must still hold that value.
    assert expected[NORESET] == NORESET_VALUE
    await check("field with no reset value kept its write")

    await tb.clk.end_test()
