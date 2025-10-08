"""Test fixed-point number format fields

Tests various Q notation formats:
- Q8.8: 8 integer bits, 8 fractional bits (16 bits, unsigned)
- Q32.-12: 32 integer bits, -12 fractional bits = bits [31:12] (20 bits, unsigned)
- SQ-8.32: -8 integer bits, 32 fractional bits (24 bits, signed)
- SQ-6.7: -6 integer bits, 7 fractional bits (1 bit, signed)
"""

import sys
from pathlib import Path

# Add parent directory to path to access shared test modules
test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))
from cocotb import test  # noqa: E402
from cocotb.triggers import RisingEdge  # noqa: E402
from tb_base import testbench  # noqa: E402


@test()
async def test_dut_fixedpoint(dut):
    """Test fixed-point field widths, ranges, and signedness"""
    tb = testbench(dut)
    await tb.clk.wait_clkn(200)

    # Set all fields to all 1s
    # Note: regblock preserves case, etana uses lowercase - check both
    q32_sig = getattr(tb, "hwif_in_r1_f_Q32_n12", None)
    if q32_sig is None:
        q32_sig = getattr(tb, "hwif_in_r1_f_q32_n12")
    q32_sig.value = (1 << 20) - 1  # 20-bit field, all 1s
    tb.hwif_in_r2_f_signed.value = (1 << 16) - 1  # 16-bit field, all 1s
    tb.hwif_in_r2_f_no_sign.value = (1 << 16) - 1  # 16-bit field, all 1s
    await tb.intf.write(0x0, 0xFFFF_FFFF_FFFF_FFFF)
    await tb.intf.write(0x8, 0xFFFF_FFFF_FFFF_FFFF)
    await RisingEdge(tb.clk.clk)

    # --------------------------------------------------------------------------
    # Q8.8 (sw=rw, hw=r)
    # 8 integer bits, 8 fractional bits = 16 bits total, unsigned
    q8_8_sig = getattr(tb, "hwif_out_r1_f_Q8_8", None)
    if q8_8_sig is None:
        q8_8_sig = getattr(tb, "hwif_out_r1_f_q8_8")
    f_Q8_8 = int(q8_8_sig.value)

    # Verify bit range [7:-8] means bits [15:0] in Python
    assert (
        f_Q8_8 & 0xFFFF
    ) == 0xFFFF, f"Q8.8 bit range: got 0x{f_Q8_8:04x}, expected 0xFFFF"

    # Verify bit width is 16
    assert (
        f_Q8_8.bit_length() <= 16
    ), f"Q8.8 width: {f_Q8_8.bit_length()} bits, expected ≤16"

    # Verify unsigned (value > 0)
    assert f_Q8_8 > 0, "Q8.8 should be unsigned (> 0)"

    # --------------------------------------------------------------------------
    # Q32.-12 (sw=r, hw=w)
    # 32 integer bits, -12 fractional bits = bits [31:12] = 20 bits, unsigned
    f_Q32_n12 = int(q32_sig.value)

    # Verify bit range [31:12] - we wrote all 1s, so should be 0xFFFFF (20 bits)
    assert (
        f_Q32_n12 & 0xFFFFF
    ) == 0xFFFFF, f"Q32.-12 bit range: got 0x{f_Q32_n12:05x}, expected 0xFFFFF"

    # Verify bit width is 20
    assert (
        f_Q32_n12.bit_length() <= 20
    ), f"Q32.-12 width: {f_Q32_n12.bit_length()} bits, expected ≤20"

    # Verify unsigned (value > 0)
    assert f_Q32_n12 > 0, "Q32.-12 should be unsigned (> 0)"

    # --------------------------------------------------------------------------
    # SQ-8.32 (sw=rw, hw=r)
    # -8 integer bits, 32 fractional bits = 24 bits total, SIGNED
    sqn8_32_sig = getattr(tb, "hwif_out_r1_f_SQn8_32", None)
    if sqn8_32_sig is None:
        sqn8_32_sig = getattr(tb, "hwif_out_r1_f_sqn8_32")
    f_SQn8_32_raw = int(sqn8_32_sig.value)

    # Verify bit range [-9:-32] means bits [23:0] in Python
    assert (
        f_SQn8_32_raw & 0xFFFFFF
    ) == 0xFFFFFF, f"SQ-8.32 bit range: got 0x{f_SQn8_32_raw:06x}, expected 0xFFFFFF"

    # Verify bit width is 24
    assert (
        f_SQn8_32_raw.bit_length() <= 24
    ), f"SQ-8.32 width: {f_SQn8_32_raw.bit_length()} bits, expected ≤24"

    # Verify signed (all 1s in signed number = -1, which is < 0)
    # Convert to signed: if MSB is set, it's negative
    if f_SQn8_32_raw & (1 << 23):  # MSB set
        f_SQn8_32_signed = f_SQn8_32_raw - (1 << 24)
    else:
        f_SQn8_32_signed = f_SQn8_32_raw
    assert (
        f_SQn8_32_signed < 0
    ), f"SQ-8.32 should be signed (< 0), got {f_SQn8_32_signed}"

    # --------------------------------------------------------------------------
    # SQ-6.7 (sw=rw, hw=r)
    # -6 integer bits, 7 fractional bits = 1 bit total, SIGNED
    sqn6_7_sig = getattr(tb, "hwif_out_r1_f_SQn6_7", None)
    if sqn6_7_sig is None:
        sqn6_7_sig = getattr(tb, "hwif_out_r1_f_sqn6_7")
    f_SQn6_7_raw = int(sqn6_7_sig.value)

    # Verify bit range [-7:-7] means bit [0] in Python
    assert (
        f_SQn6_7_raw & 0x1
    ) == 0x1, f"SQ-6.7 bit range: got 0x{f_SQn6_7_raw:01x}, expected 0x1"

    # Verify bit width is 1
    assert (
        f_SQn6_7_raw.bit_length() <= 1
    ), f"SQ-6.7 width: {f_SQn6_7_raw.bit_length()} bits, expected ≤1"

    # Verify signed (1-bit signed with value 1 = -1 < 0)
    if f_SQn6_7_raw & 1:  # MSB set (only bit)
        f_SQn6_7_signed = f_SQn6_7_raw - 2  # 2^1 = 2
    else:
        f_SQn6_7_signed = f_SQn6_7_raw
    assert f_SQn6_7_signed < 0, f"SQ-6.7 should be signed (< 0), got {f_SQn6_7_signed}"

    # --------------------------------------------------------------------------
    # 16-bit signed integer (sw=r, hw=w)
    f_signed_raw = int(tb.hwif_in_r2_f_signed.value)

    # Verify bit range [15:0]
    assert (
        f_signed_raw & 0xFFFF
    ) == 0xFFFF, f"f_signed bit range: got 0x{f_signed_raw:04x}, expected 0xFFFF"

    # Verify bit width is 16
    assert (
        f_signed_raw.bit_length() <= 16
    ), f"f_signed width: {f_signed_raw.bit_length()} bits, expected ≤16"

    # Verify signed (all 1s in 16-bit signed = -1 < 0)
    if f_signed_raw & (1 << 15):  # MSB set
        f_signed_signed = f_signed_raw - (1 << 16)
    else:
        f_signed_signed = f_signed_raw
    assert (
        f_signed_signed < 0
    ), f"f_signed should be signed (< 0), got {f_signed_signed}"

    # --------------------------------------------------------------------------
    # 16-bit unsigned integer (sw=rw, hw=r)
    f_unsigned = int(tb.hwif_out_r2_f_unsigned.value)

    # Verify bit range [15:0]
    assert (
        f_unsigned & 0xFFFF
    ) == 0xFFFF, f"f_unsigned bit range: got 0x{f_unsigned:04x}, expected 0xFFFF"

    # Verify bit width is 16
    assert (
        f_unsigned.bit_length() <= 16
    ), f"f_unsigned width: {f_unsigned.bit_length()} bits, expected ≤16"

    # Verify unsigned (value > 0)
    assert f_unsigned > 0, "f_unsigned should be unsigned (> 0)"

    # --------------------------------------------------------------------------
    # 16-bit field (no sign specified, defaults to unsigned)
    f_no_sign = int(tb.hwif_in_r2_f_no_sign.value)

    # Verify bit range [15:0]
    assert (
        f_no_sign & 0xFFFF
    ) == 0xFFFF, f"f_no_sign bit range: got 0x{f_no_sign:04x}, expected 0xFFFF"

    # Verify bit width is 16
    assert (
        f_no_sign.bit_length() <= 16
    ), f"f_no_sign width: {f_no_sign.bit_length()} bits, expected ≤16"

    # Verify unsigned (logic is unsigned in SV)
    assert f_no_sign > 0, "f_no_sign should be unsigned (> 0)"

    # --------------------------------------------------------------------------
    # Verify readback via CPU interface
    # r1: f_Q8_8[16] + f_Q32_n12[20] + f_sqn8_32[24] + f_sqn6_7[1] = 61 bits
    # After writing all 1s, readable parts should reflect the field sizes
    await tb.intf.read(0x0, 0x1FFF_FFFF_FFFF_FFFF)

    # r2: f_signed[16] (sw=r) + f_unsigned[16] (sw=rw) + f_no_sign[16] (sw=r) = 48 bits
    # f_signed is hw=w (write-only), so only f_unsigned is readable
    await tb.intf.read(0x8, 0x0000_FFFF_FFFF_FFFF)

    await tb.clk.end_test()
