import sys
from pathlib import Path

# Add parent directory to path to access shared test modules
test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))
from cocotb import test  # noqa: E402

from tb_base import testbench  # noqa: E402


def revbits(x, n=32):
    rev = 0
    for i in range(n):
        rev <<= 1
        rev += x & 1
        x >>= 1
    return rev


@test()
async def test_dut_write_buffer(dut):
    tb = testbench(dut)
    await tb.clk.wait_clkn(200)

    # reg1
    await tb.intf.read(0x0, 0x0)
    await tb.intf.read(0x2, 0x0)
    await tb.intf.read(0x4, 0x0)
    await tb.intf.read(0x6, 0x0)
    assert tb.hwif_out_reg1_f1.value == 0
    await tb.intf.write(0x0, 0x1234)
    await tb.intf.write(0x2, 0x5678)
    await tb.intf.write(0x4, 0x9ABC)
    await tb.intf.write(0x6, 0xDEF1)
    await tb.clk.wait_clkn(5)
    assert tb.hwif_out_reg1_f1.value == 0xDEF19ABC56781234
    await tb.intf.read(0x0, 0x1234)
    await tb.intf.read(0x2, 0x5678)
    await tb.intf.read(0x4, 0x9ABC)
    await tb.intf.read(0x6, 0xDEF1)

    # reg1_msb0
    await tb.intf.read(0x8, 0x0)
    await tb.intf.read(0xA, 0x0)
    await tb.intf.read(0xC, 0x0)
    await tb.intf.read(0xE, 0x0)
    assert tb.hwif_out_reg1_msb0_f1.value == 0
    await tb.intf.write(0x8, 0x1234)
    await tb.intf.write(0xA, 0x5678)
    await tb.intf.write(0xC, 0x9ABC)
    await tb.intf.write(0xE, 0xDEF1)
    await tb.clk.wait_clkn(2)
    await tb.clk.wait_clkn(20)
    # For MSB0 fields, we need to manually reverse the bits
    assert tb.hwif_out_reg1_msb0_f1.value == 0x2C481E6A3D598F7B
    assert tb.hwif_out_reg1_msb0_f1.value == revbits(0xDEF19ABC56781234, 64)
    await tb.intf.read(0x8, 0x1234)
    await tb.intf.read(0xA, 0x5678)
    await tb.intf.read(0xC, 0x9ABC)
    await tb.intf.read(0xE, 0xDEF1)

    # reg2
    await tb.intf.read(0x10, 0x0)
    await tb.intf.read(0x12, 0x0)
    assert tb.hwif_out_reg2_f1.value == 0
    assert tb.hwif_out_reg2_f2.value == 0
    await tb.intf.write(0x10, 0x34AA)
    await tb.intf.write(0x12, 0xAA12)
    await tb.clk.wait_clkn(2)
    assert tb.hwif_out_reg2_f1.value == 0x234
    assert tb.hwif_out_reg2_f2.value == 0x1
    await tb.intf.read(0x10, 0x3400)
    await tb.intf.read(0x12, 0x0012)

    # reg2_msb0
    await tb.intf.read(0x14, 0x0)
    await tb.intf.read(0x16, 0x0)
    assert tb.hwif_out_reg2_msb0_f1.value == 0
    assert tb.hwif_out_reg2_msb0_f2.value == 0
    await tb.intf.write(0x14, 0x34AA)
    #     await tb.intf.write(0x16, 0x0)
    await tb.intf.write(0x16, 0xAA12)
    await tb.clk.wait_clkn(2)

    #     assert tb.hwif_out_reg2_msb0.value == revbits(0x1234) = 0x2c48
    assert tb.hwif_out_reg2_msb0_f1.value == 0x2C4
    assert tb.hwif_out_reg2_msb0_f2.value == 0x8
    await tb.intf.read(0x14, 0x3400)
    await tb.intf.read(0x16, 0x0012)

    # --------------------------------------------------------------------------
    # Alternate Triggers
    # --------------------------------------------------------------------------

    # g1_r1, g1_r2
    await tb.intf.read(0x18, 0x0)
    await tb.intf.read(0x1A, 0x0)
    assert tb.hwif_out_g1_r1_f1.value == 0
    assert tb.hwif_out_g1_r2_f1.value == 0
    await tb.intf.write(0x1A, 0x1234)
    await tb.intf.write(0x18, 0xABCD)
    await tb.clk.wait_clkn(1)
    assert tb.hwif_out_g1_r1_f1.value == 0xABCD
    assert tb.hwif_out_g1_r2_f1.value == 0x1234
    await tb.intf.read(0x18, 0xABCD)
    await tb.intf.read(0x1A, 0x1234)

    # g2_r1, g2_r2
    await tb.intf.read(0x1C, 0x0)
    await tb.intf.read(0x1E, 0x0)
    assert tb.hwif_out_g2_r1_f1.value == 0
    assert tb.hwif_out_g2_r2_f1.value == 0
    await tb.intf.write(0x1C, 0x5678)
    await tb.intf.write(0x1E, 0x9876)
    await tb.clk.wait_clkn(1)
    assert tb.hwif_out_g2_r1_f1.value == 0
    assert tb.hwif_out_g2_r2_f1.value == 0
    tb.hwif_in_trigger_sig.value = 1
    tb.hwif_in_trigger_sig_n.value = 0
    await tb.clk.wait_clkn(1)
    tb.hwif_in_trigger_sig.value = 0
    tb.hwif_in_trigger_sig_n.value = 1
    await tb.clk.wait_clkn(1)
    assert tb.hwif_out_g2_r1_f1.value == 0x5678
    assert tb.hwif_out_g2_r2_f1.value == 0x9876
    await tb.intf.read(0x1C, 0x5678)
    await tb.intf.read(0x1E, 0x9876)
    # g3_r1
    await tb.intf.read(0x20, 0x0)
    assert tb.hwif_out_g3_r1_f1.value == 0
    await tb.intf.write(0x20, 0xFEDC)
    await tb.clk.wait_clkn(2)
    assert tb.hwif_out_g3_r1_f1.value == 0
    await tb.intf.read(0x20, 0x0)
    await tb.intf.write(0x22, 0x0)
    await tb.clk.wait_clkn(2)
    assert tb.hwif_out_g3_r1_f1.value == 0
    await tb.intf.read(0x20, 0x0)
    await tb.intf.write(0x22, 0x1)
    await tb.clk.wait_clkn(2)
    assert tb.hwif_out_g3_r1_f1.value == 0xFEDC
    await tb.intf.read(0x20, 0xFEDC)

    # g4_r1
    await tb.intf.read(0x24, 0x0)
    assert tb.hwif_out_g4_r1_f1.value == 0
    await tb.intf.write(0x24, 0xCAFE)
    await tb.clk.wait_clkn(2)
    assert tb.hwif_out_g4_r1_f1.value == 0
    await tb.intf.read(0x24, 0x0)
    await tb.intf.write(0x26, 0x1)
    await tb.clk.wait_clkn(2)
    assert tb.hwif_out_g4_r1_f1.value == 0
    await tb.intf.read(0x24, 0x0)
    await tb.intf.write(0x26, 0xE)
    await tb.clk.wait_clkn(2)
    assert tb.hwif_out_g4_r1_f1.value == 0
    await tb.intf.read(0x24, 0x0)
    await tb.intf.write(0x26, 0xF)
    await tb.clk.wait_clkn(2)
    assert tb.hwif_out_g4_r1_f1.value == 0xCAFE
    await tb.intf.read(0x24, 0xCAFE)

    # --------------------------------------------------------------------------
    # swmod behavior
    # --------------------------------------------------------------------------

    # g5_r1, g5_modcount
    await tb.intf.read(0x28, 0x0)
    await tb.intf.read(0x2A, 0x0)
    await tb.intf.write(0x28, 0x1234)
    await tb.intf.write(0x28, 0x5678)
    await tb.intf.read(0x28, 0x0)
    await tb.intf.read(0x2A, 0x0)
    tb.hwif_in_trigger_sig.value = 1
    await tb.clk.wait_clkn(1)
    tb.hwif_in_trigger_sig.value = 0
    await tb.intf.read(0x28, 0x5678)
    await tb.intf.read(0x2A, 0x1)

    # g6_r1, g6_modcount
    await tb.intf.read(0x2E, 0x0)
    await tb.intf.read(0x2C, 0x0)
    await tb.intf.read(0x2E, 0x1)
    await tb.intf.write(0x2C, 0x5678)
    await tb.intf.write(0x2C, 0x1234)
    await tb.intf.read(0x2E, 0x1)
    await tb.intf.read(0x2C, 0x0)
    await tb.intf.read(0x2E, 0x2)
    tb.hwif_in_trigger_sig.value = 1
    await tb.clk.wait_clkn(1)
    tb.hwif_in_trigger_sig.value = 0
    await tb.intf.read(0x2E, 0x3)
    await tb.intf.read(0x2C, 0x1234)
    await tb.intf.read(0x2E, 0x4)

    # --------------------------------------------------------------------------
    # strobes
    # --------------------------------------------------------------------------
    # reg1
    # reset field to known state
    await tb.intf.write(0x0, 0x0000)
    await tb.intf.write(0x2, 0x0000)
    await tb.intf.write(0x4, 0x0000)
    await tb.intf.write(0x6, 0x0000)
    await tb.clk.wait_clkn(1)
    await tb.intf.read(0x0, 0x0)
    await tb.intf.read(0x2, 0x0)
    await tb.intf.read(0x4, 0x0)
    await tb.intf.read(0x6, 0x0)
    assert tb.hwif_out_reg1_f1.value == 0

    await tb.intf.write(0x0, 0xABCD, 0xF000)
    await tb.intf.write(0x2, 0x1234, 0x0F00)
    await tb.intf.write(0x4, 0x5678, 0x00F0)
    await tb.intf.write(0x6, 0xEF12, 0x000F)
    await tb.clk.wait_clkn(1)
    await tb.intf.read(0x0, 0xA000)
    await tb.intf.read(0x2, 0x0200)
    await tb.intf.read(0x4, 0x0070)
    await tb.intf.read(0x6, 0x0002)
    assert tb.hwif_out_reg1_f1.value == 0x0002_0070_0200_A000

    # Check that strobes are cumulative
    await tb.intf.write(0x0, 0x0030, 0x00F0)
    await tb.intf.write(0x2, 0x0070, 0x00F0)
    await tb.intf.write(0x4, 0x000D, 0x000F)
    await tb.intf.write(0x4, 0xA000, 0xF000)
    await tb.intf.write(0x2, 0x0008, 0x000F)
    await tb.intf.write(0x0, 0x0200, 0x0F00)
    await tb.intf.write(0x6, 0xA000, 0xF000)
    await tb.intf.write(0x6, 0x0F00, 0x0F00)
    await tb.clk.wait_clkn(1)
    await tb.intf.read(0x0, 0xA230)
    await tb.intf.read(0x2, 0x0278)
    await tb.intf.read(0x4, 0xA07D)
    await tb.intf.read(0x6, 0xAF02)
    assert tb.hwif_out_reg1_f1.value == 0xAF02_A07D_0278_A230

    # reg1_msb0
    # reset field to known state
    await tb.intf.write(0x8, 0x0000)
    await tb.intf.write(0xA, 0x0000)
    await tb.intf.write(0xC, 0x0000)
    await tb.intf.write(0xE, 0x0000)
    await tb.clk.wait_clkn(1)
    await tb.intf.read(0x8, 0x0)
    await tb.intf.read(0xA, 0x0)
    await tb.intf.read(0xC, 0x0)
    await tb.intf.read(0xE, 0x0)
    assert tb.hwif_out_reg1_msb0_f1.value == 0

    await tb.intf.write(0x8, 0xABCD, 0xF000)
    await tb.intf.write(0xA, 0x1234, 0x0F00)
    await tb.intf.write(0xC, 0x5678, 0x00F0)
    await tb.intf.write(0xE, 0xEF12, 0x000F)
    await tb.clk.wait_clkn(1)
    await tb.intf.read(0x8, 0xA000)
    await tb.intf.read(0xA, 0x0200)
    await tb.intf.read(0xC, 0x0070)
    await tb.intf.read(0xE, 0x0002)
    assert tb.hwif_out_reg1_msb0_f1.value == revbits(0x0002_0070_0200_A000, 64)
    assert tb.hwif_out_reg1_msb0_f1.value == 0x0005_0040_0E00_4000

    # Check that strobes are cumulative
    await tb.intf.write(0x8, 0x0030, 0x00F0)
    await tb.intf.write(0xA, 0x0070, 0x00F0)
    await tb.intf.write(0xC, 0x000D, 0x000F)
    await tb.intf.write(0xC, 0xA000, 0xF000)
    await tb.intf.write(0xA, 0x0008, 0x000F)
    await tb.intf.write(0x8, 0x0200, 0x0F00)
    await tb.intf.write(0xE, 0xA000, 0xF000)
    await tb.intf.write(0xE, 0x0F00, 0x0F00)
    await tb.clk.wait_clkn(1)
    await tb.intf.read(0x8, 0xA230)
    await tb.intf.read(0xA, 0x0278)
    await tb.intf.read(0xC, 0xA07D)
    await tb.intf.read(0xE, 0xAF02)
    assert tb.hwif_out_reg1_msb0_f1.value == revbits(0xAF02_A07D_0278_A230, 64)
    assert tb.hwif_out_reg1_msb0_f1.value == 0x0C45_1E40_BE05_40F5

    await tb.clk.end_test()
