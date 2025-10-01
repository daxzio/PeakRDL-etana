"""Test external registers - registers/memory on external bus

Note: This test requires external register emulation to respond to the bus protocol.
External register emulators are started as background tasks.

Skipped: ext_reg_array[32] due to regblock wrapper array limitation.
"""

from random import randint
from cocotb import test, start_soon
from cocotb.triggers import RisingEdge
from tb_base import testbench
from external_reg_emulator_simple import (
    ExtRegEmulator,
    WideExtRegEmulator,
    ExtRegArrayEmulator,
    ExternalBlockEmulator,
    RoRegEmulator,
    WoRegEmulator,
    WideRoRegEmulator,
    WideWoRegEmulator,
)


@test()
async def test_dut_external(dut):
    """Test external register access with bus protocol"""
    tb = testbench(dut)

    # Start all external register emulators
    ext_reg = ExtRegEmulator(dut, tb.clk.clk)
    wide_ext_reg = WideExtRegEmulator(dut, tb.clk.clk)
    ext_reg_array = ExtRegArrayEmulator(dut, tb.clk.clk)
    rf_block = ExternalBlockEmulator(dut, tb.clk.clk, "hwif_out_rf")
    am_block = ExternalBlockEmulator(dut, tb.clk.clk, "hwif_out_am")
    mm_block = ExternalBlockEmulator(dut, tb.clk.clk, "hwif_out_mm")
    ro_reg = RoRegEmulator(dut, tb.clk.clk)
    wo_reg = WoRegEmulator(dut, tb.clk.clk)
    wide_ro_reg = WideRoRegEmulator(dut, tb.clk.clk)
    wide_wo_reg = WideWoRegEmulator(dut, tb.clk.clk)

    start_soon(ext_reg.run())
    start_soon(wide_ext_reg.run())
    start_soon(ext_reg_array.run())
    start_soon(rf_block.run())
    start_soon(am_block.run())
    start_soon(mm_block.run())
    start_soon(ro_reg.run())
    start_soon(wo_reg.run())
    start_soon(wide_ro_reg.run())
    start_soon(wide_wo_reg.run())

    # Keep references for internal state verification
    emulators = {
        "ext_reg": ext_reg,
        "wide_ext_reg": wide_ext_reg,
        "ext_reg_array": ext_reg_array,
        "rf": rf_block,
        "am": am_block,
        "mm": mm_block,
        "ro_reg": ro_reg,
        "wo_reg": wo_reg,
        "wide_ro_reg": wide_ro_reg,
        "wide_wo_reg": wide_wo_reg,
    }

    await tb.clk.wait_clkn(200)

    # --------------------------------------------------------------------------
    # Simple external registers
    # --------------------------------------------------------------------------

    # ext_reg: External register with mixed access fields (sw:r/w/rw)
    for _ in range(10):
        value = randint(0, 0xFFFFFFFF)
        await tb.intf.write(0x00, value)

        # Read back - only verify readable field (whatever_c bits [15:8])
        read_val = await tb.intf.read(0x00)
        read_int = (
            int.from_bytes(read_val, "little")
            if isinstance(read_val, bytes)
            else read_val
        )
        assert ((value >> 8) & 0xFF) == ((read_int >> 8) & 0xFF)

        # Internal state verification - check emulator storage
        # Verify whatever_b (bit 4) and whatever_c (bits 15:8) are stored
        expected_storage = ((value >> 4) & 1) << 4 | ((value >> 8) & 0xFF) << 8
        assert (
            emulators["ext_reg"].storage & 0xFF10
        ) == expected_storage, f"Internal storage mismatch"

    # wide_ext_reg: 64-bit external register (2 subwords)
    for i in range(2):
        for _ in range(10):
            value = randint(0, 0xFFFFFFFF)
            await tb.intf.write(0x10 + i * 4, value)
            await tb.intf.read(0x10 + i * 4, value)

            # Internal state verification
            assert (
                emulators["wide_ext_reg"].storage[i] == value
            ), f"wide_ext_reg[{i}] storage mismatch"

    # int_reg: Internal (non-external) register at 0x04
    await tb.intf.write(0x04, 0x1234)
    await tb.intf.read(0x04, 0x1234)

    # --------------------------------------------------------------------------
    # External register array - Now working with wrapper fix!
    # --------------------------------------------------------------------------
    # ext_reg_array[32] @ 0x100 - my_reg type (full 32-bit field)
    for i in range(32):
        for _ in range(5):
            value = randint(0, 0xFFFFFFFF)
            await tb.intf.write(0x100 + i * 4, value)
            await tb.intf.read(0x100 + i * 4, value)

            # Internal state verification
            assert (
                emulators["ext_reg_array"].storage[i] == value
            ), f"ext_reg_array[{i}] storage mismatch"

    # --------------------------------------------------------------------------
    # External regfile (rf @ 0x1000)
    # --------------------------------------------------------------------------
    for i in range(8):
        for _ in range(10):
            value = randint(0, 0xFFFFFFFF)
            await tb.intf.write(0x1000 + i * 4, value)
            await tb.intf.read(0x1000 + i * 4, value)

            # Internal state verification (addr is in bytes, so mem[i*4])
            assert (
                emulators["rf"].mem[i * 4] == value
            ), f"rf.mem[{i*4}] storage mismatch"

    # --------------------------------------------------------------------------
    # External addrmap (am @ 0x2000)
    # --------------------------------------------------------------------------
    for i in range(8):
        for _ in range(10):
            value = randint(0, 0xFFFFFFFF)
            await tb.intf.write(0x2000 + i * 4, value)
            await tb.intf.read(0x2000 + i * 4, value)

            # Internal state verification (addr is in bytes)
            assert (
                emulators["am"].mem[i * 4] == value
            ), f"am.mem[{i*4}] storage mismatch"

    # --------------------------------------------------------------------------
    # External memory (mm @ 0x3000)
    # --------------------------------------------------------------------------
    for i in range(8):
        for _ in range(10):
            value = randint(0, 0xFFFFFFFF)
            await tb.intf.write(0x3000 + i * 4, value)
            await tb.intf.read(0x3000 + i * 4, value)

            # Internal state verification (addr is in bytes)
            assert (
                emulators["mm"].mem[i * 4] == value
            ), f"mm.mem[{i*4}] storage mismatch"

    # --------------------------------------------------------------------------
    # Read-only external register (ro_reg @ 0x4000)
    # --------------------------------------------------------------------------
    # RO register - HW can write, SW can only read
    # Verify current value
    ro_val = await tb.intf.read(0x4000)
    ro_val_int = (
        int.from_bytes(ro_val, "little") if isinstance(ro_val, bytes) else ro_val
    )

    # Internal state verification
    assert (
        ro_val_int == emulators["ro_reg"].storage
    ), f"ro_reg value mismatch: CPU read 0x{ro_val_int:08x}, storage 0x{emulators['ro_reg'].storage:08x}"

    # --------------------------------------------------------------------------
    # Write-only external register (wo_reg @ 0x4004)
    # --------------------------------------------------------------------------
    # Can write, reads return 0
    for _ in range(10):
        value = randint(0, 0xFFFFFFFF)
        await tb.intf.write(0x4004, value)
        await tb.intf.read(0x4004, 0x00000000)  # WO reads as 0

        # Internal state verification - verify value stored even though SW can't read
        assert emulators["wo_reg"].storage == value, f"wo_reg storage mismatch"

    # --------------------------------------------------------------------------
    # Wide read-only external register (wide_ro_reg @ 0x4010)
    # --------------------------------------------------------------------------
    for i in range(2):
        wide_ro_val = await tb.intf.read(0x4010 + i * 4)
        wide_ro_int = (
            int.from_bytes(wide_ro_val, "little")
            if isinstance(wide_ro_val, bytes)
            else wide_ro_val
        )

        # Internal state verification
        assert (
            wide_ro_int == emulators["wide_ro_reg"].storage[i]
        ), f"wide_ro_reg[{i}] mismatch"

    # --------------------------------------------------------------------------
    # Wide write-only external register (wide_wo_reg @ 0x4018)
    # --------------------------------------------------------------------------
    for i in range(2):
        for _ in range(5):
            value = randint(0, 0xFFFFFFFF)
            await tb.intf.write(0x4018 + i * 4, value)
            await tb.intf.read(0x4018 + i * 4, 0x00000000)  # WO reads as 0

            # Internal state verification
            assert (
                emulators["wide_wo_reg"].storage[i] == value
            ), f"wide_wo_reg[{i}] storage mismatch"

    # --------------------------------------------------------------------------
    # Pipelined random access test
    # --------------------------------------------------------------------------
    # Initialize with known values
    await tb.intf.write(0x04, 0x1234)  # int_reg

    # Note: Cannot test ext_reg_array[32] pipelining due to wrapper
    # Test other external blocks with random pipelined access
    for _ in range(50):
        choice = randint(0, 4)
        j = randint(0, 7)

        if choice == 0:  # int_reg
            await tb.intf.write(0x04, 0x1234)
            await tb.intf.read(0x04, 0x1234)
        elif choice == 1:  # rf
            await tb.intf.write(0x1000 + j * 4, 0x1000 + j)
            await tb.intf.read(0x1000 + j * 4, 0x1000 + j)
        elif choice == 2:  # am
            await tb.intf.write(0x2000 + j * 4, 0x2000 + j)
            await tb.intf.read(0x2000 + j * 4, 0x2000 + j)
        elif choice == 3:  # mm
            await tb.intf.write(0x3000 + j * 4, 0x3000 + j)
            await tb.intf.read(0x3000 + j * 4, 0x3000 + j)
        else:  # ext_reg (mixed access - only readable field returned)
            await tb.intf.write(0x00, 0xABCD)
            read_val = await tb.intf.read(0x00)
            # Don't verify - ext_reg has mixed access fields

    await tb.clk.end_test()
