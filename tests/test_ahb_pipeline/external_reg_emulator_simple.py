"""Simplified external register emulators (local copy for test_ahb_pipeline)

This module is copied from tests/test_external/external_reg_emulator_simple.py
with a small tweak so packed-array emulators can target different prefixes.
"""

import random

from cocotb.triggers import RisingEdge


class ExtRegEmulator:
    """Emulates ext_reg (my_reg_alt type) with correct bit positions

    Works with both:
    - Register-level signals (etana): hwif_out_ext_reg_wr_data
    - Field-level signals (regblock wrapper): hwif_out_ext_reg_wr_data_whatever_b/c

    Fields:
    - whatever_a[3:2]: sw=r, hw=w (read-only from SW)
    - whatever_b[4:4]: sw=w, hw=r (write-only from SW)
    - whatever_c[15:8]: sw=rw, hw=r (read-write)
    """

    def __init__(self, dut, clk):
        self.dut = dut
        self.clk = clk

        # Protocol signals
        self.req = dut.hwif_out_ext_reg_req
        self.req_is_wr = dut.hwif_out_ext_reg_req_is_wr

        # Try register-level signals first (etana), then field-level (regblock wrapper)
        self.wr_data_reg = getattr(dut, "hwif_out_ext_reg_wr_data", None)
        self.wr_biten_reg = getattr(dut, "hwif_out_ext_reg_wr_biten", None)
        self.rd_data_reg = getattr(dut, "hwif_in_ext_reg_rd_data", None)

        # Field-level signals (for regblock wrapper)
        self.wr_data_b = getattr(dut, "hwif_out_ext_reg_wr_data_whatever_b", None)
        self.wr_data_c = getattr(dut, "hwif_out_ext_reg_wr_data_whatever_c", None)
        self.wr_biten_b = getattr(dut, "hwif_out_ext_reg_wr_biten_whatever_b", None)
        self.wr_biten_c = getattr(dut, "hwif_out_ext_reg_wr_biten_whatever_c", None)
        self.rd_data_a = getattr(dut, "hwif_in_ext_reg_rd_data_whatever_a", None)
        self.rd_data_c_field = getattr(dut, "hwif_in_ext_reg_rd_data_whatever_c", None)

        # Acks
        self.rd_ack = dut.hwif_in_ext_reg_rd_ack
        self.wr_ack = dut.hwif_in_ext_reg_wr_ack

        # Internal storage (full 32-bit word)
        self.storage = 0

        # Initialize acks and read data to prevent X propagation
        self.rd_ack.value = 0
        self.wr_ack.value = 0
        if self.rd_data_reg is not None:
            self.rd_data_reg.value = 0
        if self.rd_data_a is not None:
            self.rd_data_a.value = 0
        if self.rd_data_c_field is not None:
            self.rd_data_c_field.value = 0

    async def run(self):
        """Run the emulator"""
        while True:
            await RisingEdge(self.clk)

            # Default: no acks
            self.rd_ack.value = 0
            self.wr_ack.value = 0

            # Handle X values gracefully
            try:
                req_val = int(self.req.value)
                req_is_wr_val = int(self.req_is_wr.value)
            except ValueError:
                continue

            if req_val == 1:
                if req_is_wr_val == 1:
                    # Write request
                    if self.wr_data_reg is not None:
                        # Register-level signals (etana)
                        wr_val = int(self.wr_data_reg.value)
                        wr_biten_val = int(self.wr_biten_reg.value)

                        # Apply bit-enable mask to update storage
                        for bit in range(32):
                            if (wr_biten_val >> bit) & 1:
                                if (wr_val >> bit) & 1:
                                    self.storage |= 1 << bit
                                else:
                                    self.storage &= ~(1 << bit)
                    else:
                        # Field-level signals (regblock wrapper)
                        # whatever_b: bit [4]
                        if self.wr_biten_b is not None and int(self.wr_biten_b.value):
                            b_val = int(self.wr_data_b.value)
                            self.storage = (self.storage & ~(1 << 4)) | (
                                (b_val & 1) << 4
                            )

                        # whatever_c: bits [15:8]
                        if self.wr_biten_c is not None:
                            c_biten = int(self.wr_biten_c.value)
                            c_val = int(self.wr_data_c.value)
                            for bit in range(8):
                                if (c_biten >> bit) & 1:
                                    storage_bit = 8 + bit
                                    if (c_val >> bit) & 1:
                                        self.storage |= 1 << storage_bit
                                    else:
                                        self.storage &= ~(1 << storage_bit)

                    self.wr_ack.value = 1
                else:
                    # Read request
                    if self.rd_data_reg is not None:
                        # Register-level signal (etana)
                        self.rd_data_reg.value = self.storage
                    else:
                        # Field-level signals (regblock wrapper)
                        # whatever_a: bits [3:2]
                        a_val = (self.storage >> 2) & 0x3
                        self.rd_data_a.value = a_val

                        # whatever_c: bits [15:8]
                        c_val = (self.storage >> 8) & 0xFF
                        self.rd_data_c_field.value = c_val

                    self.rd_ack.value = 1


class WideExtRegEmulator:
    """Emulates wide_ext_reg (my_wide_reg type) - 64-bit with 32-bit access

    Uses register-level rd_data/wr_data (64-bit) with subword access via req bits.
    Field: whatever (full 32-bit per subword)
    2 subwords total (64-bit regwidth, 32-bit accesswidth)
    """

    def __init__(self, dut, clk):
        self.dut = dut
        self.clk = clk

        # Protocol signals
        # req is 2-bit (one per subword)
        self.req = dut.hwif_out_wide_ext_reg_req
        self.req_is_wr = dut.hwif_out_wide_ext_reg_req_is_wr

        # Register-level data signals (64-bit wide)
        self.wr_data = dut.hwif_out_wide_ext_reg_wr_data
        self.wr_biten = dut.hwif_out_wide_ext_reg_wr_biten
        self.rd_data = dut.hwif_in_wide_ext_reg_rd_data

        # Acks
        self.rd_ack = dut.hwif_in_wide_ext_reg_rd_ack
        self.wr_ack = dut.hwif_in_wide_ext_reg_wr_ack

        # Storage for 2 subwords (test expects storage[0] and storage[1])
        self.storage = [0, 0]

        # Initialize acks and read data to prevent X propagation
        self.rd_ack.value = 0
        self.wr_ack.value = 0
        self.rd_data.value = 0

    async def run(self):
        """Run the emulator"""
        while True:
            await RisingEdge(self.clk)

            # Default: no acks
            self.rd_ack.value = 0
            self.wr_ack.value = 0

            # Handle X values gracefully
            try:
                req_val = int(self.req.value)
                req_is_wr_val = int(self.req_is_wr.value)
            except ValueError:
                # X or Z values present, skip this cycle
                continue

            # Check which subword is being accessed (bit 0 or bit 1 of req)
            for subword in range(2):
                if (req_val >> subword) & 1:
                    if req_is_wr_val == 1:
                        # Write request - write data to specific subword
                        wr_val = int(self.wr_data.value)
                        wr_biten_val = int(self.wr_biten.value)

                        # Apply bit-enable mask
                        for bit in range(32):
                            if (wr_biten_val >> bit) & 1:
                                if (wr_val >> bit) & 1:
                                    self.storage[subword] |= 1 << bit
                                else:
                                    self.storage[subword] &= ~(1 << bit)

                        self.wr_ack.value = 1
                    else:
                        # Read request - return only the accessed subword (32-bit)
                        self.rd_data.value = self.storage[subword]
                        self.rd_ack.value = 1
                    break  # Only one subword accessed at a time


class ExtRegArrayEmulator:
    """Emulates an external register array (32 entries by default).

    Supports etana's unpacked arrays (hwif_in_r2_rd_ack[31:0] etc).

    ack_delay: 0 for immediate ack; int for fixed delay; (min, max) for random delay per request.
    """

    def __init__(self, dut, clk, prefix="ext_reg_array", num_entries=32, ack_delay=0):
        self.dut = dut
        self.clk = clk
        self.prefix = prefix
        self.num_entries = num_entries
        if isinstance(ack_delay, (list, tuple)) and len(ack_delay) == 2:
            self._delay_min, self._delay_max = ack_delay
            self._delay_fixed = None
        else:
            self._delay_fixed = max(0, int(ack_delay))
            self._delay_min = self._delay_max = None

        out_prefix = f"hwif_out_{prefix}"
        in_prefix = f"hwif_in_{prefix}"

        # Protocol signals (unpacked arrays for etana)
        self.req = getattr(dut, f"{out_prefix}_req")
        self.req_is_wr = getattr(dut, f"{out_prefix}_req_is_wr")

        # Data signals (unpacked arrays)
        self.wr_data = getattr(dut, f"{out_prefix}_wr_data", None)
        self.wr_biten = getattr(dut, f"{out_prefix}_wr_biten", None)
        self.rd_data = getattr(dut, f"{in_prefix}_rd_data", None)

        # Field-level signals (regblock wrapper - single field 'whatever')
        if self.wr_data is None:
            self.wr_data = getattr(dut, f"{out_prefix}_wr_data_whatever")
            self.wr_biten = getattr(dut, f"{out_prefix}_wr_biten_whatever")
            self.rd_data = getattr(dut, f"{in_prefix}_rd_data_whatever")

        # Acks (unpacked arrays)
        self.rd_ack = getattr(dut, f"{in_prefix}_rd_ack")
        self.wr_ack = getattr(dut, f"{in_prefix}_wr_ack")

        # Storage for registers
        self.storage = [0] * num_entries

        # Initialize acks and read data (unpacked arrays - element by element)
        for i in range(num_entries):
            self.rd_ack[i].value = 0
            self.wr_ack[i].value = 0
            self.rd_data[i].value = 0

        # For delayed ack
        self._delay_count = 0
        self._delay_target = 0
        self._pending_idx = -1
        self._pending_rd = False
        self._pending_wr = False

    def _uses_delay(self):
        return (self._delay_fixed is not None and self._delay_fixed > 0) or (
            self._delay_min is not None and self._delay_max is not None
        )

    def _get_delay_for_request(self):
        if self._delay_fixed is not None and self._delay_fixed > 0:
            return self._delay_fixed
        return random.randint(self._delay_min, self._delay_max)

    async def run(self):
        """Run the emulator"""
        while True:
            await RisingEdge(self.clk)

            # Default: no acks (unpacked arrays)
            for i in range(self.num_entries):
                self.rd_ack[i].value = 0
                self.wr_ack[i].value = 0

            # Delayed-ack path: count down and ack when done
            if self._uses_delay() and self._pending_idx >= 0:
                self._delay_count += 1
                if self._delay_count >= self._delay_target:
                    i = self._pending_idx
                    if self._pending_rd:
                        self.rd_data[i].value = self._pending_rd_data
                        self.rd_ack[i].value = 1
                    else:
                        self.wr_ack[i].value = 1
                    self._pending_idx = -1
                    self._pending_rd = False
                    self._pending_wr = False
                    self._delay_count = 0
                continue

            # Check which array element is being accessed (unpacked arrays)
            for i in range(self.num_entries):
                try:
                    req_val = int(self.req[i].value)
                    if req_val == 0:
                        continue

                    is_wr = int(self.req_is_wr[i].value)
                    if is_wr == 1:
                        # Write request
                        element_data = int(self.wr_data[i].value)
                        element_biten = int(self.wr_biten[i].value)

                        for bit in range(32):
                            if (element_biten >> bit) & 1:
                                if (element_data >> bit) & 1:
                                    self.storage[i] |= 1 << bit
                                else:
                                    self.storage[i] &= ~(1 << bit)

                        if self._uses_delay():
                            self._pending_idx = i
                            self._pending_wr = True
                            self._delay_count = 0
                            self._delay_target = self._get_delay_for_request()
                        else:
                            self.wr_ack[i].value = 1
                    else:
                        # Read request
                        if self._uses_delay():
                            self._pending_idx = i
                            self._pending_rd = True
                            self._pending_rd_data = self.storage[i]
                            self._delay_count = 0
                            self._delay_target = self._get_delay_for_request()
                        else:
                            self.rd_data[i].value = self.storage[i]
                            self.rd_ack[i].value = 1
                    break
                except (ValueError, AttributeError):
                    continue


class ExternalBlockEmulator:
    """Emulates external memory/regfile blocks (rf, am, mm)

    Has address decoding for memory-like access
    Field: whatever (full 32-bit)
    """

    def __init__(self, dut, clk, prefix):
        """
        Args:
            prefix: 'hwif_out_rf', 'hwif_out_am', or 'hwif_out_mm'
        """
        self.dut = dut
        self.clk = clk
        self.name = prefix.replace("hwif_out_", "")  # For debug

        # Protocol signals
        hwif_in_prefix = prefix.replace("hwif_out_", "")
        self.req = getattr(dut, f"{prefix}_req")
        self.req_is_wr = getattr(dut, f"{prefix}_req_is_wr")
        self.addr = getattr(dut, f"{prefix}_addr")

        # Data signals (full 32-bit for mem/regfile)
        # Try both with and without _whatever suffix
        self.wr_data = getattr(dut, f"{prefix}_wr_data", None)
        if self.wr_data is None:
            self.wr_data = getattr(dut, f"{prefix}_wr_data_whatever", None)
        self.rd_data = getattr(dut, f"hwif_in_{hwif_in_prefix}_rd_data", None)

        # Acks
        self.rd_ack = getattr(dut, f"hwif_in_{hwif_in_prefix}_rd_ack")
        self.wr_ack = getattr(dut, f"hwif_in_{hwif_in_prefix}_wr_ack")

        # Memory storage (32 entries max)
        self.mem = [0] * 32

        # Initialize acks and read data to prevent X propagation
        self.rd_ack.value = 0
        self.wr_ack.value = 0
        if self.rd_data is not None:
            self.rd_data.value = 0

    async def run(self):
        """Run the emulator"""
        import logging

        log = logging.getLogger(f"cocotb.tb.{self.name}")

        while True:
            await RisingEdge(self.clk)

            # Default: no acks
            self.rd_ack.value = 0
            self.wr_ack.value = 0

            # Handle X values gracefully
            try:
                req_val = int(self.req.value)
                req_is_wr_val = int(self.req_is_wr.value)
                addr_val = int(self.addr.value)
            except ValueError:
                continue

            if req_val == 1:
                # Use byte addressing directly (test expects mem[byte_addr])
                idx = addr_val & 0x1F  # Mask to 32 bytes

                # Visible tracing
                try:
                    if req_is_wr_val == 1:
                        wr_val = 0
                        if self.wr_data is not None:
                            wr_val = int(self.wr_data.value)
                        log.debug(
                            f"[EXT-BLK {self.name}] WRITE addr=0x{addr_val:04x} (idx {idx}) data=0x{wr_val:08x}"
                        )
                        self.mem[idx] = wr_val
                        self.wr_ack.value = 1
                    else:
                        rd_val = self.mem[idx]
                        log.debug(
                            f"[EXT-BLK {self.name}] READ  addr=0x{addr_val:04x} (idx {idx}) data=0x{rd_val:08x}"
                        )
                        if self.rd_data is not None:
                            self.rd_data.value = rd_val
                        self.rd_ack.value = 1
                except Exception as error:
                    print(f"[EXT-BLK {self.name}] ERROR handling access: {error}")


class ExternalMemEmulator:
    """Emulates a simple external memory window with byte addressing.

    ack_delay_cycles: int or (min, max) tuple.
      - 0: no delay (immediate ack)
      - int > 0: fixed delay in cycles
      - (min, max): random delay from min to max cycles per request
    """

    def __init__(self, dut, clk, prefix="r3", num_entries=128, ack_delay_cycles=0):
        self.dut = dut
        self.clk = clk
        self.prefix = prefix
        self.num_entries = num_entries
        if isinstance(ack_delay_cycles, (list, tuple)) and len(ack_delay_cycles) == 2:
            self._delay_min, self._delay_max = ack_delay_cycles
            self._delay_fixed = None
        else:
            self._delay_fixed = max(0, int(ack_delay_cycles))
            self._delay_min = self._delay_max = None

        out_prefix = f"hwif_out_{prefix}"
        in_prefix = f"hwif_in_{prefix}"

        self.req = getattr(dut, f"{out_prefix}_req")
        self.req_is_wr = getattr(dut, f"{out_prefix}_req_is_wr")
        self.addr = getattr(dut, f"{out_prefix}_addr")
        self.wr_data = getattr(dut, f"{out_prefix}_wr_data")
        self.wr_biten = getattr(dut, f"{out_prefix}_wr_biten")

        self.rd_data = getattr(dut, f"{in_prefix}_rd_data")
        self.rd_ack = getattr(dut, f"{in_prefix}_rd_ack")
        self.wr_ack = getattr(dut, f"{in_prefix}_wr_ack")

        self.mem = [0] * num_entries

        self.rd_ack.value = 0
        self.wr_ack.value = 0
        self.rd_data.value = 0

        # For delayed ack
        self._delay_count = 0
        self._delay_target = 0
        self._pending_rd = False
        self._pending_wr = False
        self._pending_idx = 0
        self._pending_rd_data = 0

    def _uses_delay(self):
        return (
            self._delay_fixed is not None
            and self._delay_fixed > 0
            or (self._delay_min is not None and self._delay_max is not None)
        )

    def _get_delay_for_request(self):
        if self._delay_fixed is not None and self._delay_fixed > 0:
            return self._delay_fixed
        return random.randint(self._delay_min, self._delay_max)

    async def run(self):
        while True:
            await RisingEdge(self.clk)
            self.rd_ack.value = 0
            self.wr_ack.value = 0

            try:
                req_val = int(self.req.value)
                req_is_wr_val = int(self.req_is_wr.value)
                addr_val = int(self.addr.value)
            except ValueError:
                continue

            idx = addr_val & (self.num_entries - 1)

            if not self._uses_delay():
                if req_val == 0:
                    continue
                if req_is_wr_val == 1:
                    wr_val = int(self.wr_data.value)
                    wr_biten_val = int(self.wr_biten.value)
                    for bit in range(32):
                        if (wr_biten_val >> bit) & 1:
                            if (wr_val >> bit) & 1:
                                self.mem[idx] |= 1 << bit
                            else:
                                self.mem[idx] &= ~(1 << bit)
                    self.wr_ack.value = 1
                else:
                    self.rd_data.value = self.mem[idx]
                    self.rd_ack.value = 1
                continue

            # Delayed ack path
            if self._pending_rd or self._pending_wr:
                self._delay_count += 1
                if self._delay_count >= self._delay_target:
                    if self._pending_rd:
                        self.rd_data.value = self._pending_rd_data
                        self.rd_ack.value = 1
                    else:
                        self.wr_ack.value = 1
                    self._pending_rd = False
                    self._pending_wr = False
                    self._delay_count = 0
                continue

            if req_val == 0:
                continue

            if req_is_wr_val == 1:
                wr_val = int(self.wr_data.value)
                wr_biten_val = int(self.wr_biten.value)
                for bit in range(32):
                    if (wr_biten_val >> bit) & 1:
                        if (wr_val >> bit) & 1:
                            self.mem[idx] |= 1 << bit
                        else:
                            self.mem[idx] &= ~(1 << bit)
                if self._uses_delay():
                    self._pending_wr = True
                    self._delay_count = 0
                    self._delay_target = self._get_delay_for_request()
                else:
                    self.wr_ack.value = 1
            else:
                if self._uses_delay():
                    self._pending_rd = True
                    self._pending_rd_data = self.mem[idx]
                    self._delay_count = 0
                    self._delay_target = self._get_delay_for_request()
                else:
                    self.rd_data.value = self.mem[idx]
                    self.rd_ack.value = 1


class RoRegEmulator:
    """Emulates ro_reg - read-only external register (sw=r, hw=w)

    Works with both register-level and field-level signals.
    """

    def __init__(self, dut, clk):
        self.dut = dut
        self.clk = clk

        # Protocol
        self.req = dut.hwif_out_ro_reg_req
        self.req_is_wr = dut.hwif_out_ro_reg_req_is_wr

        # Try register-level signals first (etana), then field-level (regblock wrapper)
        self.rd_data = getattr(dut, "hwif_in_ro_reg_rd_data", None)
        if self.rd_data is None:
            self.rd_data = dut.hwif_in_ro_reg_rd_data_whatever

        self.rd_ack = dut.hwif_in_ro_reg_rd_ack

        # Storage (can be set by HW)
        self.storage = 0xDEADBEEF  # Default value

        # Initialize acks and read data to prevent X propagation
        self.rd_ack.value = 0
        self.rd_data.value = self.storage

    async def run(self):
        while True:
            await RisingEdge(self.clk)
            self.rd_ack.value = 0

            # Handle X values gracefully
            try:
                req_val = int(self.req.value)
                req_is_wr_val = int(self.req_is_wr.value)
            except ValueError:
                continue

            if req_val == 1 and req_is_wr_val == 0:
                # Read request only (RO register)
                self.rd_data.value = self.storage
                self.rd_ack.value = 1


class WoRegEmulator:
    """Emulates wo_reg - write-only external register (sw=w, hw=r)

    Works with both register-level and field-level signals.
    """

    def __init__(self, dut, clk):
        self.dut = dut
        self.clk = clk

        # Protocol
        self.req = dut.hwif_out_wo_reg_req
        self.req_is_wr = dut.hwif_out_wo_reg_req_is_wr

        # Try register-level signals first (etana), then field-level (regblock wrapper)
        self.wr_data = getattr(dut, "hwif_out_wo_reg_wr_data", None)
        self.wr_biten = getattr(dut, "hwif_out_wo_reg_wr_biten", None)

        # Field-level signals (regblock wrapper)
        if self.wr_data is None:
            self.wr_data = dut.hwif_out_wo_reg_wr_data_whatever
            self.wr_biten = dut.hwif_out_wo_reg_wr_biten_whatever

        self.wr_ack = dut.hwif_in_wo_reg_wr_ack

        # Storage (HW can read)
        self.storage = 0

        self.wr_ack.value = 0

    async def run(self):
        while True:
            await RisingEdge(self.clk)
            self.wr_ack.value = 0

            # Handle X values gracefully
            try:
                req_val = int(self.req.value)
                req_is_wr_val = int(self.req_is_wr.value)
            except ValueError:
                continue

            if req_val == 1 and req_is_wr_val == 1:
                # Write request only (WO register)
                wr_val = int(self.wr_data.value)
                wr_biten_val = int(self.wr_biten.value)

                # Apply bit-enable mask
                for bit in range(32):
                    if (wr_biten_val >> bit) & 1:
                        if (wr_val >> bit) & 1:
                            self.storage |= 1 << bit
                        else:
                            self.storage &= ~(1 << bit)

                self.wr_ack.value = 1


class WideRoRegEmulator:
    """Emulates wide_ro_reg - wide read-only (64-bit with 32-bit access)"""

    def __init__(self, dut, clk):
        self.dut = dut
        self.clk = clk

        # Protocol (2-bit req for 2 subwords)
        self.req = dut.hwif_out_wide_ro_reg_req
        self.req_is_wr = dut.hwif_out_wide_ro_reg_req_is_wr

        # Data
        self.rd_data = dut.hwif_in_wide_ro_reg_rd_data
        self.rd_ack = dut.hwif_in_wide_ro_reg_rd_ack

        # Storage for 2 subwords
        self.storage = [0xCAFEBABE, 0xDEADBEEF]

        # Initialize acks and read data to prevent X propagation
        self.rd_ack.value = 0
        self.rd_data.value = self.storage[0]  # Initialize to first subword

    async def run(self):
        while True:
            await RisingEdge(self.clk)
            self.rd_ack.value = 0

            # Handle X values gracefully
            try:
                req_val = int(self.req.value)
                req_is_wr_val = int(self.req_is_wr.value)
            except ValueError:
                continue

            for i in range(2):
                if (req_val >> i) & 1:
                    if req_is_wr_val == 0:
                        self.rd_data.value = self.storage[i]
                        self.rd_ack.value = 1
                    break


class WideWoRegEmulator:
    """Emulates wide_wo_reg - wide write-only (64-bit with 32-bit access)"""

    def __init__(self, dut, clk):
        self.dut = dut
        self.clk = clk

        # Protocol (2-bit req for 2 subwords)
        self.req = dut.hwif_out_wide_wo_reg_req
        self.req_is_wr = dut.hwif_out_wide_wo_reg_req_is_wr

        # Data
        self.wr_data = dut.hwif_out_wide_wo_reg_wr_data
        self.wr_ack = dut.hwif_in_wide_wo_reg_wr_ack

        # Storage for 2 subwords
        self.storage = [0, 0]

        self.wr_ack.value = 0

    async def run(self):
        while True:
            await RisingEdge(self.clk)
            self.wr_ack.value = 0

            # Handle X values gracefully
            try:
                req_val = int(self.req.value)
                req_is_wr_val = int(self.req_is_wr.value)
            except ValueError:
                continue

            for i in range(2):
                if (req_val >> i) & 1:
                    if req_is_wr_val == 1:
                        self.storage[i] = int(self.wr_data.value)
                        self.wr_ack.value = 1
                    break
