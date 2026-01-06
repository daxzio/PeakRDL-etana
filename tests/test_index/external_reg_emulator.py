from cocotb.triggers import RisingEdge


class ExternalRegArrayEmulator:
    """Simple emulator for hwif_out_e[*] external register array.

    Each entry exposes two 8-bit fields (f and g) that map to bits [7:0] and
    [23:16] of the 32-bit CPU data bus. This emulator responds immediately to
    read/write requests, maintains internal storage for verification, and
    provides the required ack strobes to unblock the CPU interface.
    """

    NUM_REGS = 8

    def __init__(self, dut, clk):
        self.dut = dut
        self.clk = clk

        # Request side (driven by DUT)
        self.req = dut.hwif_out_e_req
        self.req_is_wr = dut.hwif_out_e_req_is_wr
        self.wr_data_f = dut.hwif_out_e_wr_data_f
        self.wr_biten_f = dut.hwif_out_e_wr_biten_f
        self.wr_data_g = dut.hwif_out_e_wr_data_g
        self.wr_biten_g = dut.hwif_out_e_wr_biten_g

        # Response side (driven by emulator)
        self.rd_ack = dut.hwif_in_e_rd_ack
        self.wr_ack = dut.hwif_in_e_wr_ack
        self.rd_data_f = dut.hwif_in_e_rd_data_f
        self.rd_data_g = dut.hwif_in_e_rd_data_g

        # Internal storage initialized to reset values from RDL
        self.storage_f = [0x11] * self.NUM_REGS
        self.storage_g = [0x11] * self.NUM_REGS

        # Initialize driven signals to safe defaults (unpacked arrays - initialize each element)
        for i in range(self.NUM_REGS):
            self.rd_ack[i].value = 0
            self.wr_ack[i].value = 0
            self.rd_data_f[i].value = 0
            self.rd_data_g[i].value = 0

    async def run(self):
        """Clocked process that services external requests."""
        while True:
            await RisingEdge(self.clk)
            # Default: deassert acknowledgments each cycle (unpacked arrays)
            for i in range(self.NUM_REGS):
                self.rd_ack[i].value = 0
                self.wr_ack[i].value = 0

            # Check each array element (unpacked arrays)
            for idx in range(self.NUM_REGS):
                try:
                    req_val = int(self.req[idx].value)
                    if req_val == 0:
                        continue

                    is_write = int(self.req_is_wr[idx].value)
                    if is_write:
                        self._handle_write(idx)
                    else:
                        self._handle_read(idx)
                    break  # Only one entry can be active per cycle
                except (ValueError, AttributeError):
                    # Ignore cycles with unknowns
                    continue

    def _handle_write(self, idx: int):
        # Unpacked arrays - access elements directly
        f_data = int(self.wr_data_f[idx].value)
        f_mask = int(self.wr_biten_f[idx].value)
        g_data = int(self.wr_data_g[idx].value)
        g_mask = int(self.wr_biten_g[idx].value)

        self.storage_f[idx] = self._apply_mask(self.storage_f[idx], f_data, f_mask, 8)
        self.storage_g[idx] = self._apply_mask(self.storage_g[idx], g_data, g_mask, 8)

        # Unpacked array - set element directly
        self.wr_ack[idx].value = 1

    def _handle_read(self, idx: int):
        # Unpacked arrays - set elements directly
        self.rd_data_f[idx].value = self.storage_f[idx]
        self.rd_data_g[idx].value = self.storage_g[idx]
        # Unpacked array - set element directly
        self.rd_ack[idx].value = 1

    @staticmethod
    def _apply_mask(current: int, new: int, mask: int, width: int) -> int:
        result = current
        for bit in range(width):
            if (mask >> bit) & 0x1:
                if (new >> bit) & 0x1:
                    result |= 1 << bit
                else:
                    result &= ~(1 << bit)
        return result


class ExternalMemEmulator:
    """Emulator for the hwif_out_mm external memory interface."""

    MEM_ENTRIES = 13

    def __init__(self, dut, clk):
        self.dut = dut
        self.clk = clk

        # Request interface
        self.req = dut.hwif_out_mm_req
        self.req_is_wr = dut.hwif_out_mm_req_is_wr
        self.addr = dut.hwif_out_mm_addr
        self.wr_data = dut.hwif_out_mm_wr_data
        self.wr_biten = dut.hwif_out_mm_wr_biten

        # Response interface
        self.rd_ack = dut.hwif_in_mm_rd_ack
        self.wr_ack = dut.hwif_in_mm_wr_ack
        self.rd_data = dut.hwif_in_mm_rd_data

        self.storage = [0] * self.MEM_ENTRIES

        self.rd_ack.value = 0
        self.wr_ack.value = 0
        self.rd_data.value = 0

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

            if req_val == 0:
                continue

            idx = addr_val >> 2
            if idx < 0 or idx >= self.MEM_ENTRIES:
                continue

            if req_is_wr_val:
                self._handle_write(idx)
            else:
                self._handle_read(idx)

    def _handle_write(self, idx: int):
        wr_val = int(self.wr_data.value)
        wr_biten = int(self.wr_biten.value)
        self.storage[idx] = self._apply_mask(self.storage[idx], wr_val, wr_biten, 32)
        self.wr_ack.value = 1

    def _handle_read(self, idx: int):
        self.rd_data.value = self.storage[idx]
        self.rd_ack.value = 1

    @staticmethod
    def _apply_mask(current: int, new: int, mask: int, width: int) -> int:
        result = current
        for bit in range(width):
            if (mask >> bit) & 0x1:
                if (new >> bit) & 0x1:
                    result |= 1 << bit
                else:
                    result &= ~(1 << bit)
        return result
