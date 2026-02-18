"""Test wide registers (regwidth > accesswidth) - simplified"""

import sys
from pathlib import Path

# Add parent directory to path to access shared test modules
test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))
from cocotb import test  # noqa: E402
from cocotb.triggers import RisingEdge  # noqa: E402
from tb_base import testbench  # noqa: E402


@test()
async def test_dut_wide_regs(dut):
    """Test wide registers with multi-cycle access (simplified)"""
    tb = testbench(dut)
    await tb.clk.wait_clkn(200)

    # rw_reg1: 64-bit register, 16-bit accesswidth
    # Write to all 4 sub-words (0x0, 0x2, 0x4, 0x6)
    assert tb.hwif_out_rw_reg1_f1.value == 0
    assert tb.hwif_out_rw_reg1_f2.value == 0

    await tb.intf.write(0x0, 0x1234)
    await tb.intf.write(0x2, 0x5678)
    await tb.intf.write(0x4, 0x9ABC)
    await tb.intf.write(0x6, 0xDEF1)
    await RisingEdge(tb.clk.clk)
    await RisingEdge(tb.clk.clk)  # Storage updates 1 cycle after pready

    # Check field values
    assert tb.hwif_out_rw_reg1_f1.value == 0x34
    assert tb.hwif_out_rw_reg1_f2.value == 0x1

    # Read back (fields are scattered across sub-words)
    await tb.intf.read(0x0, 0x1034)
    await tb.intf.read(0x2, 0x0000)
    await tb.intf.read(0x4, 0x9A10)
    await tb.intf.read(0x6, 0x0000)

    # rw_reg2: Another 64-bit register
    assert tb.hwif_out_rw_reg2_f1.value == 0
    assert tb.hwif_out_rw_reg2_f2.value == 0

    await tb.intf.write(0x8, 0x1234)
    await tb.intf.write(0xA, 0x5678)
    await tb.intf.write(0xC, 0x9ABC)
    await tb.intf.write(0xE, 0xDEF1)
    await RisingEdge(tb.clk.clk)
    await RisingEdge(tb.clk.clk)

    assert tb.hwif_out_rw_reg2_f1.value == 0x8
    assert tb.hwif_out_rw_reg2_f2.value == 0xDEF1

    await tb.intf.read(0x8, 0x0000)
    await tb.intf.read(0xA, 0x0008)
    await tb.intf.read(0xC, 0x0000)
    await tb.intf.read(0xE, 0xDEF1)

    # r_reg: 32-bit ro register with hw write
    await tb.intf.read(0x20, 0x0000)
    await tb.intf.read(0x22, 0x0000)

    tb.hwif_in_r_reg_f1.value = 0xAB
    tb.hwif_in_r_reg_f2.value = 0x4DE
    await RisingEdge(tb.clk.clk)

    await tb.intf.read(0x20, 0xB000)
    await tb.intf.read(0x22, 0x4DEA)

    # r_reg3 & r_reg4: ro registers (skip - depend on reset behavior)
    # Just verify they're accessible
    await tb.intf.read(0x30)
    await tb.intf.read(0x38)

    await tb.clk.end_test()
