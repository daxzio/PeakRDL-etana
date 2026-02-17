import sys
from pathlib import Path

# Add parent directory to path to access shared test modules
test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))
from cocotb import test  # noqa: E402

from tb_base import testbench  # noqa: E402


@test()
async def test_dut_hw_access(dut):
    tb = testbench(dut)
    await tb.clk.wait_clkn(200)

    # check initial conditions
    await tb.intf.read(0x4, 0x11)
    await tb.intf.read(0x8, 0x22)
    await tb.intf.read(0xC, 0x33)

    # ---------------------------------
    # set hwenable = F0
    await tb.intf.write(0x0, 0x00F0)
    await tb.clk.wait_clkn(2)  # Storage updates 1 cycle after pready

    # test hwenable + we
    tb.hwif_in_r1_f.value = 0xAB
    tb.hwif_in_r1_f_we.value = 1
    await tb.clk.wait_clkn(1)
    tb.hwif_in_r1_f_we.value = 0
    await tb.intf.read(0x4, 0xA1)

    # test hwenable + hwclr
    tb.hwif_in_r1_f_hwclr.value = 1
    await tb.clk.wait_clkn(1)
    tb.hwif_in_r1_f_hwclr.value = 0
    await tb.intf.read(0x4, 0x01)

    # test hwenable + hwset
    tb.hwif_in_r1_f_hwset.value = 1
    await tb.clk.wait_clkn(1)
    tb.hwif_in_r1_f_hwset.value = 0
    await tb.intf.read(0x4, 0xF1)

    # ---------------------------------
    # set hwmask = F0
    await tb.intf.write(0x0, 0xF000)
    await tb.clk.wait_clkn(2)

    # test hwmask + we
    tb.hwif_in_r2_f.value = 0xAB
    tb.hwif_in_r2_f_we.value = 1
    await tb.clk.wait_clkn(1)
    tb.hwif_in_r2_f_we.value = 0
    await tb.intf.read(0x8, 0x2B)

    # test hwmask + hwclr
    tb.hwif_in_r2_f_hwclr.value = 1
    await tb.clk.wait_clkn(1)
    tb.hwif_in_r2_f_hwclr.value = 0
    await tb.intf.read(0x8, 0x20)

    # test hwmask + hwset
    tb.hwif_in_r2_f_hwset.value = 1
    await tb.clk.wait_clkn(1)
    tb.hwif_in_r2_f_hwset.value = 0
    await tb.intf.read(0x8, 0x2F)

    # ---------------------------------
    # test hwenable + hwclr via reference
    # toggle hwenable = F0, hwclr=1
    await tb.intf.write(0x0, 0x100F0)
    await tb.intf.write(0x0, 0x00000)
    await tb.clk.wait_clkn(2)
    await tb.intf.read(0xC, 0x03)

    # test hwenable + hwset via reference
    # toggle hwenable = 0F, hwset=1
    await tb.intf.write(0x0, 0x2000F)
    await tb.intf.write(0x0, 0x00000)
    await tb.clk.wait_clkn(2)
    await tb.intf.read(0xC, 0x0F)

    # test hwenable + we via reference
    tb.hwif_in_r3_f.value = 0xAA
    # toggle hwenable = 0F, we=1
    await tb.intf.write(0x0, 0x4000F)
    await tb.intf.write(0x0, 0x00000)
    await tb.intf.read(0xC, 0x0A)

    # ---------------------------------
    # test wel via reference
    tb.hwif_in_r4_f.value = 0xBB
    # toggle wel
    await tb.intf.write(0x0, 0x100000)
    await tb.intf.write(0x0, 0x000000)
    await tb.intf.read(0x10, 0xBB)

    tb.hwif_in_r4_f.value = 0xCC
    # toggle wel
    await tb.intf.write(0x0, 0x100000)
    await tb.intf.write(0x0, 0x000000)
    await tb.intf.read(0x10, 0xCC)

    # ---------------------------------
    # test we and next via reference
    tb.hwif_in_r5_f_next_value.value = 0x54
    await tb.intf.read(0x14, 0x55)
    tb.hwif_in_r5_f_next_value.value = 0x56
    tb.hwif_in_r5_f_we.value = 1
    await tb.clk.wait_clkn(1)
    tb.hwif_in_r5_f_next_value.value = 0
    tb.hwif_in_r5_f_we.value = 0
    await tb.intf.read(0x14, 0x56)

    await tb.clk.end_test()
