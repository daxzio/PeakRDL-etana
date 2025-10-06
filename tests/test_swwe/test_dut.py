"""Test software write enable (swwe) and level (swwel)"""

import sys
from pathlib import Path

# Add parent directory to path to access shared test modules
test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))
from cocotb import test  # noqa: E402
from tb_base import testbench  # noqa: E402


@test()
async def test_dut_swwe(dut):
    """Test swwe and swwel properties"""
    tb = testbench(dut)
    await tb.clk.wait_clkn(200)

    # r1: swwe = true (inferred signal, active high)
    await tb.intf.read(0x1, 0x11)
    tb.hwif_in_r1_f_swwe.value = 0  # Disable writes
    await tb.intf.write(0x1, 0x12)
    await tb.intf.read(0x1, 0x11)  # No change
    tb.hwif_in_r1_f_swwe.value = 1  # Enable writes
    await tb.intf.write(0x1, 0x13)
    await tb.intf.read(0x1, 0x13)  # Updated

    # r2: swwel = true (inferred signal, active low)
    await tb.intf.read(0x2, 0x22)
    tb.hwif_in_r2_f_swwel.value = 1  # Disable writes
    await tb.intf.write(0x2, 0x23)
    await tb.intf.read(0x2, 0x22)  # No change
    tb.hwif_in_r2_f_swwel.value = 0  # Enable writes
    await tb.intf.write(0x2, 0x24)
    await tb.intf.read(0x2, 0x24)  # Updated

    # r3: swwe via lock register (lock.r3_swwe)
    await tb.intf.read(0x3, 0x33)
    await tb.intf.write(0x0, 0x0)  # lock.r3_swwe = 0
    await tb.intf.write(0x3, 0x32)
    await tb.intf.read(0x3, 0x33)  # No change
    await tb.intf.write(0x0, 0x1)  # lock.r3_swwe = 1
    await tb.intf.write(0x3, 0x34)
    await tb.intf.read(0x3, 0x34)  # Updated

    # r4: swwel via lock register (lock.r4_swwel, active low)
    await tb.intf.read(0x4, 0x44)
    await tb.intf.write(0x0, 0x2)  # lock.r4_swwel = 1
    await tb.intf.write(0x4, 0x40)
    await tb.intf.read(0x4, 0x44)  # No change
    await tb.intf.write(0x0, 0x0)  # lock.r4_swwel = 0
    await tb.intf.write(0x4, 0x45)
    await tb.intf.read(0x4, 0x45)  # Updated

    # r5: swwe via reference chain (r5->swwe = r3->swwe = lock.r3_swwe)
    await tb.intf.read(0x5, 0x55)
    await tb.intf.write(0x0, 0x0)  # lock.r3_swwe = 0
    await tb.intf.write(0x5, 0x52)
    await tb.intf.read(0x5, 0x55)  # No change
    await tb.intf.write(0x0, 0x1)  # lock.r3_swwe = 1
    await tb.intf.write(0x5, 0x54)
    await tb.intf.read(0x5, 0x54)  # Updated

    # r6: swwe via cross-reference (r6->swwe = r4->swwel, inverted polarity)
    await tb.intf.read(0x6, 0x66)
    await tb.intf.write(0x0, 0x0)  # lock.r4_swwel = 0 -> r6 can write
    await tb.intf.write(0x6, 0x60)
    await tb.intf.read(0x6, 0x66)  # No change (swwe inverted from swwel)
    await tb.intf.write(0x0, 0x2)  # lock.r4_swwel = 1 -> r6 cannot write
    await tb.intf.write(0x6, 0x65)
    await tb.intf.read(0x6, 0x65)  # Updated

    await tb.clk.end_test()
