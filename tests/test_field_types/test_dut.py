"""
Test for various field type combinations from SystemRDL Table 12.

This test validates all valid combinations of sw/hw access modes:
- sw=rw/r/w with hw=rw/r/w/na
- Storage elements vs Wire/Bus types
- Write enable (we) and Write enable level (wel) signals
"""

from cocotb import test
from tb_base import testbench


@test()
async def test_dut_field_types(dut):
    """Test all field type combinations defined in SystemRDL Table 12"""
    tb = testbench(dut)

    # Set wel high before reset (as in original test)
    tb.hwif_in_r3_f_wel.value = 1

    await tb.clk.wait_clkn(200)  # Wait for reset

    # =========================================================================
    # r1 - sw=rw; hw=rw; we; // Storage element
    # Both software and hardware can read/write with write enable
    # =========================================================================
    await tb.intf.read(0x0, 10)
    assert tb.hwif_out_r1_f.value == 10

    await tb.intf.write(0x0, 11)
    await tb.intf.read(0x0, 11)
    assert tb.hwif_out_r1_f.value == 11

    # Try HW write without we (should not update)
    tb.hwif_in_r1_f.value = 9
    await tb.intf.read(0x0, 11)
    assert tb.hwif_out_r1_f.value == 11

    # HW write with we (should update)
    tb.hwif_in_r1_f.value = 12
    tb.hwif_in_r1_f_we.value = 1
    await tb.clk.wait_clkn(1)
    tb.hwif_in_r1_f.value = 0
    tb.hwif_in_r1_f_we.value = 0
    await tb.intf.read(0x0, 12)
    assert tb.hwif_out_r1_f.value == 12

    # =========================================================================
    # r2 - sw=rw; hw=r; // Storage element
    # Software can read/write, hardware can only read
    # =========================================================================
    await tb.intf.read(0x1, 20)
    assert tb.hwif_out_r2_f.value == 20

    await tb.intf.write(0x1, 21)
    await tb.intf.read(0x1, 21)
    assert tb.hwif_out_r2_f.value == 21

    # =========================================================================
    # r3 - sw=rw; hw=w; wel; // Storage element
    # Software can read/write, hardware can write with level-sensitive enable
    # =========================================================================
    await tb.intf.read(0x2, 30)

    await tb.intf.write(0x2, 31)
    await tb.intf.read(0x2, 31)

    # Try HW write with wel high (should not update)
    tb.hwif_in_r3_f.value = 29
    await tb.intf.read(0x2, 31)

    # HW write with wel low (should update)
    tb.hwif_in_r3_f.value = 32
    tb.hwif_in_r3_f_wel.value = 0
    await tb.clk.wait_clkn(1)
    tb.hwif_in_r3_f.value = 0
    tb.hwif_in_r3_f_wel.value = 1
    await tb.intf.read(0x2, 32)

    # =========================================================================
    # r4 - sw=rw; hw=na; // Storage element
    # Only software access
    # =========================================================================
    await tb.intf.read(0x3, 40)
    await tb.intf.write(0x3, 41)
    await tb.intf.read(0x3, 41)

    # =========================================================================
    # r5 - sw=r; hw=rw; we; // Storage element
    # Software read-only, hardware can read/write with enable
    # =========================================================================
    await tb.intf.read(0x4, 50)
    assert tb.hwif_out_r5_f.value == 50

    # SW write should not change value
    await tb.intf.write(0x4, 51)
    await tb.intf.read(0x4, 50)
    assert tb.hwif_out_r5_f.value == 50

    # HW write without we (should not update)
    tb.hwif_in_r5_f.value = 9
    await tb.intf.read(0x4, 50)
    assert tb.hwif_out_r5_f.value == 50

    # HW write with we (should update)
    tb.hwif_in_r5_f.value = 52
    tb.hwif_in_r5_f_we.value = 1
    await tb.clk.wait_clkn(1)
    tb.hwif_in_r5_f.value = 0
    tb.hwif_in_r5_f_we.value = 0
    await tb.intf.read(0x4, 52)
    assert tb.hwif_out_r5_f.value == 52

    # =========================================================================
    # r6 - sw=r; hw=r; // Wire/Bus - constant value
    # Both software and hardware read-only
    # =========================================================================
    await tb.intf.read(0x5, 60)
    assert tb.hwif_out_r6_f.value == 60

    await tb.intf.write(0x5, 61)
    await tb.intf.read(0x5, 60)
    assert tb.hwif_out_r6_f.value == 60

    # =========================================================================
    # r7 - sw=r; hw=w; // Wire/Bus - hardware assigns value
    # Software read-only, hardware writes the value directly
    # =========================================================================
    await tb.intf.read(0x6, 0)

    tb.hwif_in_r7_f.value = 70
    await tb.intf.read(0x6, 70)

    await tb.intf.write(0x6, 71)
    await tb.intf.read(0x6, 70)

    # =========================================================================
    # r8 - sw=r; hw=na; // Wire/Bus - constant value
    # Software read-only constant
    # =========================================================================
    await tb.intf.read(0x7, 80)
    await tb.intf.write(0x7, 81)
    await tb.intf.read(0x7, 80)

    # =========================================================================
    # r9 - sw=w; hw=rw; we; // Storage element
    # Software write-only, hardware can read/write
    # =========================================================================
    await tb.intf.read(0x8, 0)  # SW reads as 0
    assert tb.hwif_out_r9_f.value == 90  # But HW sees actual value

    await tb.intf.write(0x8, 91)
    await tb.intf.read(0x8, 0)  # SW still reads as 0
    assert tb.hwif_out_r9_f.value == 91

    # HW write without we (should not update)
    tb.hwif_in_r9_f.value = 89
    await tb.intf.read(0x8, 0)
    assert tb.hwif_out_r9_f.value == 91

    # HW write with we (should update)
    tb.hwif_in_r9_f.value = 92
    tb.hwif_in_r9_f_we.value = 1
    await tb.clk.wait_clkn(1)
    tb.hwif_in_r9_f.value = 0
    tb.hwif_in_r9_f_we.value = 0
    await tb.intf.read(0x8, 0)
    assert tb.hwif_out_r9_f.value == 92

    # =========================================================================
    # r10 - sw=w; hw=r; // Storage element
    # Software write-only, hardware read-only
    # =========================================================================
    await tb.intf.read(0x9, 0)  # SW reads as 0
    assert tb.hwif_out_r10_f.value == 100  # But HW sees actual value

    await tb.intf.write(0x9, 101)
    await tb.intf.read(0x9, 0)  # SW still reads as 0
    assert tb.hwif_out_r10_f.value == 101

    await tb.clk.end_test()
