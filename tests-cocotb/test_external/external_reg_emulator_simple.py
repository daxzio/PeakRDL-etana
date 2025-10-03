"""Simplified external register emulators

Hardcoded for specific register types in test_external:
- ext_reg: my_reg_alt with split fields
- wide_ext_reg: my_wide_reg with full 32-bit field, 2 subwords
- ext_reg_array[32]: Array of my_reg registers with full 32-bit field
"""

from cocotb.triggers import RisingEdge


class ExtRegEmulator:
    """Emulates ext_reg (my_reg_alt type) with correct bit positions"""

    def __init__(self, dut, clk):
        self.dut = dut
        self.clk = clk

        # Protocol signals
        self.req = dut.hwif_out_ext_reg_req
        self.req_is_wr = dut.hwif_out_ext_reg_req_is_wr

        # Write data signals (from SW)
        self.wr_data_b = dut.hwif_out_ext_reg_wr_data_whatever_b  # bit [4]
        self.wr_data_c = dut.hwif_out_ext_reg_wr_data_whatever_c  # bits [15:8]

        # Read data signals (to SW)
        self.rd_data_a = dut.hwif_in_ext_reg_rd_data_whatever_a  # bits [3:2]
        self.rd_data_c = dut.hwif_in_ext_reg_rd_data_whatever_c  # bits [15:8]

        # Acks
        self.rd_ack = dut.hwif_in_ext_reg_rd_ack
        self.wr_ack = dut.hwif_in_ext_reg_wr_ack

        # Internal storage (full 32-bit word)
        self.storage = 0

        # Initialize acks and read data to prevent X propagation
        self.rd_ack.value = 0
        self.wr_ack.value = 0
        self.rd_data_a.value = 0
        self.rd_data_c.value = 0

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
                    # Write request - update storage from SW writable fields
                    # whatever_b: bit [4]
                    b_val = int(self.wr_data_b.value)
                    self.storage = (self.storage & ~(1 << 4)) | ((b_val & 1) << 4)

                    # whatever_c: bits [15:8]
                    c_val = int(self.wr_data_c.value)
                    self.storage = (self.storage & ~(0xFF << 8)) | ((c_val & 0xFF) << 8)

                    self.wr_ack.value = 1
                else:
                    # Read request - return SW readable fields from storage
                    # whatever_a: bits [3:2] (HW can modify these)
                    a_val = (self.storage >> 2) & 0x3
                    self.rd_data_a.value = a_val

                    # whatever_c: bits [15:8]
                    c_val = (self.storage >> 8) & 0xFF
                    self.rd_data_c.value = c_val

                    self.rd_ack.value = 1


class WideExtRegEmulator:
    """Emulates wide_ext_reg (my_wide_reg type) - 64-bit with 32-bit access

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

        # Data signals (full 32-bit)
        self.wr_data = dut.hwif_out_wide_ext_reg_wr_data
        self.rd_data = dut.hwif_in_wide_ext_reg_rd_data

        # Acks
        self.rd_ack = dut.hwif_in_wide_ext_reg_rd_ack
        self.wr_ack = dut.hwif_in_wide_ext_reg_wr_ack

        # Storage for 2 subwords
        self.storage = [0, 0]

        # Current subword being accessed
        self.current_subword = 0

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
                        # Write request
                        wr_val = int(self.wr_data.value)
                        self.storage[subword] = wr_val
                        self.wr_ack.value = 1
                    else:
                        # Read request
                        self.rd_data.value = self.storage[subword]
                        self.rd_ack.value = 1
                    break  # Only one subword accessed at a time


class ExtRegArrayEmulator:
    """Emulates ext_reg_array[32] - array of 32 my_reg registers

    Uses packed array signals from wrapper (manually fixed)
    Field: whatever (full 32-bit)
    """

    def __init__(self, dut, clk):
        self.dut = dut
        self.clk = clk

        # Protocol signals (packed arrays)
        self.req = dut.hwif_out_ext_reg_array_req  # [31:0]
        self.req_is_wr = dut.hwif_out_ext_reg_array_req_is_wr  # scalar
        self.wr_data = dut.hwif_out_ext_reg_array_wr_data_whatever  # [31:0][31:0]
        self.rd_data = dut.hwif_in_ext_reg_array_rd_data_whatever  # [31:0][31:0]

        # Acks (packed)
        self.rd_ack = dut.hwif_in_ext_reg_array_rd_ack  # [31:0]
        self.wr_ack = dut.hwif_in_ext_reg_array_wr_ack  # [31:0]

        # Storage for 32 registers
        self.storage = [0] * 32

        # Initialize acks and read data to prevent X propagation
        self.rd_ack.value = 0
        self.wr_ack.value = 0
        # Initialize rd_data as packed array (can't index individual elements)
        # Cocotb will initialize the full packed array

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
            except ValueError:
                continue

            # Check which array element is being accessed
            for i in range(32):
                if (req_val >> i) & 1:
                    # Extract is_wr bit for element i from packed array
                    is_wr_packed = int(self.req_is_wr.value)
                    is_wr_bit = (is_wr_packed >> i) & 1
                    if is_wr_bit == 1:
                        # Write request - extract data for element i
                        # wr_data is [31:0][31:0], extract [i]
                        packed_data = int(self.wr_data.value)
                        element_data = (packed_data >> (i * 32)) & 0xFFFFFFFF
                        self.storage[i] = element_data

                        # Ack for element i
                        ack_val = 1 << i
                        self.wr_ack.value = ack_val
                    else:
                        # Read request - return data for element i
                        # The rd_data is a packed 2D array [31:0][31:0]
                        # We need to set just element [i] in the packed format
                        # Pack all storage into the signal (cocotb will extract element i)
                        packed_data = 0
                        for j in range(32):
                            packed_data |= self.storage[j] << (j * 32)
                        self.rd_data.value = packed_data

                        # Ack for element i
                        ack_val = 1 << i
                        self.rd_ack.value = ack_val
                    break  # Only one element at a time


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
    """Emulates ro_reg - read-only external register (sw=r, hw=w)"""

    def __init__(self, dut, clk):
        self.dut = dut
        self.clk = clk

        # Protocol
        self.req = dut.hwif_out_ro_reg_req
        self.req_is_wr = dut.hwif_out_ro_reg_req_is_wr

        # Data (only read data exists for RO)
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
    """Emulates wo_reg - write-only external register (sw=w, hw=r)"""

    def __init__(self, dut, clk):
        self.dut = dut
        self.clk = clk

        # Protocol
        self.req = dut.hwif_out_wo_reg_req
        self.req_is_wr = dut.hwif_out_wo_reg_req_is_wr

        # Data (only write data exists for WO)
        self.wr_data = dut.hwif_out_wo_reg_wr_data_whatever
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
                self.storage = int(self.wr_data.value)
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
