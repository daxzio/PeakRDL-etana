"""Simplified external register emulators

Hardcoded for specific register types in test_external:
- ext_reg: my_reg_alt with split fields
- wide_ext_reg: my_wide_reg with full 32-bit field, 2 subwords
- ext_reg_array[32]: Array of my_reg registers with full 32-bit field
"""

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
    """Emulates ext_reg_array[32] - array of 32 my_reg registers

    Uses register-level signals (not field-level).
    Field: whatever (full 32-bit)
    """

    def __init__(self, dut, clk):
        self.dut = dut
        self.clk = clk

        # Protocol signals (packed arrays)
        self.req = dut.hwif_out_ext_reg_array_req  # [31:0]
        self.req_is_wr = dut.hwif_out_ext_reg_array_req_is_wr  # scalar

        # Try register-level signals first (etana), then field-level (regblock wrapper)
        self.wr_data = getattr(dut, "hwif_out_ext_reg_array_wr_data", None)
        self.wr_biten = getattr(dut, "hwif_out_ext_reg_array_wr_biten", None)
        self.rd_data = getattr(dut, "hwif_in_ext_reg_array_rd_data", None)

        # Field-level signals (regblock wrapper - single field 'whatever')
        if self.wr_data is None:
            self.wr_data = dut.hwif_out_ext_reg_array_wr_data_whatever
            self.wr_biten = dut.hwif_out_ext_reg_array_wr_biten_whatever
            self.rd_data = dut.hwif_in_ext_reg_array_rd_data_whatever

        # Acks (now unpacked arrays)
        self.rd_ack = dut.hwif_in_ext_reg_array_rd_ack  # [31:0]
        self.wr_ack = dut.hwif_in_ext_reg_array_wr_ack  # [31:0]

        # Storage for 32 registers
        self.storage = [0] * 32

        # Initialize acks and read data to prevent X propagation
        # Unpacked arrays need to be initialized element by element
        for i in range(32):
            self.rd_ack[i].value = 0
            self.wr_ack[i].value = 0
            self.rd_data[i].value = 0

    async def run(self):
        """Run the emulator"""
        while True:
            await RisingEdge(self.clk)

            # Default: no acks (unpacked arrays - clear each element)
            for i in range(32):
                self.rd_ack[i].value = 0
                self.wr_ack[i].value = 0

            # Check which array element is being accessed (unpacked arrays - check each element)
            for i in range(32):
                try:
                    req_val = int(self.req[i].value)
                    if req_val == 0:
                        continue

                    # Check if write
                    is_wr = int(self.req_is_wr[i].value)
                    if is_wr == 1:
                        # Write request - get data and biten for element i (unpacked arrays)
                        element_data = int(self.wr_data[i].value)
                        element_biten = int(self.wr_biten[i].value)

                        # Apply bit-enable mask
                        for bit in range(32):
                            if (element_biten >> bit) & 1:
                                if (element_data >> bit) & 1:
                                    self.storage[i] |= 1 << bit
                                else:
                                    self.storage[i] &= ~(1 << bit)

                        # Ack for element i (unpacked array)
                        self.wr_ack[i].value = 1
                    else:
                        # Read request - return data for element i (unpacked array)
                        self.rd_data[i].value = self.storage[i]
                        # Ack for element i (unpacked array)
                        self.rd_ack[i].value = 1
                    break  # Only one element should be active at a time
                except (ValueError, AttributeError):
                    # Skip if value is X or other invalid
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
                except Exception as e:
                    print(f"[EXT-BLK {self.name}] ERROR handling access: {e}")


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
