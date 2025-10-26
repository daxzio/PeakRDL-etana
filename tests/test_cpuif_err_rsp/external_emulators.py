"""External register and memory emulators for test_cpuif_err_rsp

These emulators respond to the external register/memory protocol
and maintain internal storage that can be accessed for verification.

Pattern based on test_external/external_reg_emulator_simple.py
"""

from cocotb.triggers import RisingEdge


class SimpleExtRegEmulator:
    """Emulates a simple external register (32-bit, single field named 'f')"""

    def __init__(self, dut, clk, prefix):
        """Initialize emulator

        Args:
            dut: DUT instance
            clk: Clock signal
            prefix: Signal prefix (e.g., "hwif_out_er_rw")
        """
        self.dut = dut
        self.clk = clk
        self.prefix = prefix

        # Protocol signals (flattened) - field name is 'f'
        self.req = getattr(dut, f"{prefix}_req")
        self.req_is_wr = getattr(dut, f"{prefix}_req_is_wr")
        self.wr_data = getattr(dut, f"{prefix}_wr_data_f")
        self.wr_biten = getattr(dut, f"{prefix}_wr_biten_f")

        # Response signals
        in_prefix = prefix.replace("hwif_out", "hwif_in")
        self.rd_ack = getattr(dut, f"{in_prefix}_rd_ack")
        self.rd_data = getattr(dut, f"{in_prefix}_rd_data_f")
        self.wr_ack = getattr(dut, f"{in_prefix}_wr_ack")

        # Internal storage
        self.value = 0

        # Initialize response signals
        self.rd_ack.value = 0
        self.rd_data.value = 0
        self.wr_ack.value = 0

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
                    wr_val = int(self.wr_data.value)
                    wr_biten_val = int(self.wr_biten.value)

                    # Apply bit-enable mask
                    for bit in range(32):
                        if (wr_biten_val >> bit) & 1:
                            if (wr_val >> bit) & 1:
                                self.value |= 1 << bit
                            else:
                                self.value &= ~(1 << bit)

                    self.wr_ack.value = 1
                else:
                    # Read request
                    self.rd_data.value = self.value
                    self.rd_ack.value = 1


class SimpleExtRegReadOnly:
    """Emulates a read-only external register"""

    def __init__(self, dut, clk, prefix):
        self.dut = dut
        self.clk = clk
        self.prefix = prefix

        # Protocol signals
        self.req = getattr(dut, f"{prefix}_req")
        self.req_is_wr = getattr(dut, f"{prefix}_req_is_wr")

        # Response signals - field name is 'f'
        in_prefix = prefix.replace("hwif_out", "hwif_in")
        self.rd_ack = getattr(dut, f"{in_prefix}_rd_ack")
        self.rd_data = getattr(dut, f"{in_prefix}_rd_data_f")

        # Internal storage (can be set by test)
        self.value = 0

        # Initialize response signals
        self.rd_ack.value = 0
        self.rd_data.value = 0

    async def run(self):
        """Run the emulator"""
        while True:
            await RisingEdge(self.clk)

            # Default: no ack
            self.rd_ack.value = 0

            try:
                req_val = int(self.req.value)
                req_is_wr_val = int(self.req_is_wr.value)
            except ValueError:
                continue

            if req_val == 1 and req_is_wr_val == 0:
                # Read request only
                self.rd_data.value = self.value
                self.rd_ack.value = 1


class SimpleExtRegWriteOnly:
    """Emulates a write-only external register"""

    def __init__(self, dut, clk, prefix):
        self.dut = dut
        self.clk = clk
        self.prefix = prefix

        # Protocol signals - field name is 'f'
        self.req = getattr(dut, f"{prefix}_req")
        self.req_is_wr = getattr(dut, f"{prefix}_req_is_wr")
        self.wr_data = getattr(dut, f"{prefix}_wr_data_f")
        self.wr_biten = getattr(dut, f"{prefix}_wr_biten_f")

        # Response signals
        in_prefix = prefix.replace("hwif_out", "hwif_in")
        self.wr_ack = getattr(dut, f"{in_prefix}_wr_ack")

        # Internal storage (can be read by test)
        self.value = 0

        # Initialize response signals
        self.wr_ack.value = 0

    async def run(self):
        """Run the emulator"""
        while True:
            await RisingEdge(self.clk)

            # Default: no ack
            self.wr_ack.value = 0

            try:
                req_val = int(self.req.value)
                req_is_wr_val = int(self.req_is_wr.value)
            except ValueError:
                continue

            if req_val == 1 and req_is_wr_val == 1:
                # Write request only
                wr_val = int(self.wr_data.value)
                wr_biten_val = int(self.wr_biten.value)

                # Apply bit-enable mask
                for bit in range(32):
                    if (wr_biten_val >> bit) & 1:
                        if (wr_val >> bit) & 1:
                            self.value |= 1 << bit
                        else:
                            self.value &= ~(1 << bit)

                self.wr_ack.value = 1


class SimpleExtMemEmulator:
    """Emulates an external memory block"""

    def __init__(self, dut, clk, prefix, num_entries=4):
        self.dut = dut
        self.clk = clk
        self.prefix = prefix

        # Protocol signals
        self.req = getattr(dut, f"{prefix}_req")
        self.req_is_wr = getattr(dut, f"{prefix}_req_is_wr")
        self.addr = getattr(dut, f"{prefix}_addr")
        self.wr_data = getattr(dut, f"{prefix}_wr_data")
        self.wr_biten = getattr(dut, f"{prefix}_wr_biten")

        # Response signals
        in_prefix = prefix.replace("hwif_out", "hwif_in")
        self.rd_ack = getattr(dut, f"{in_prefix}_rd_ack")
        self.rd_data = getattr(dut, f"{in_prefix}_rd_data")
        self.wr_ack = getattr(dut, f"{in_prefix}_wr_ack")

        # Internal storage
        self.mem = [0] * num_entries

        # Initialize response signals
        self.rd_ack.value = 0
        self.rd_data.value = 0
        self.wr_ack.value = 0

    async def run(self):
        """Run the emulator"""
        while True:
            await RisingEdge(self.clk)

            # Default: no acks
            self.rd_ack.value = 0
            self.wr_ack.value = 0

            try:
                req_val = int(self.req.value)
                req_is_wr_val = int(self.req_is_wr.value)
                addr_val = int(self.addr.value)
            except ValueError:
                continue

            if req_val == 1:
                # Address is in bytes, divide by 4 for word index
                idx = (addr_val >> 2) % len(self.mem)

                if req_is_wr_val == 1:
                    # Write request
                    wr_val = int(self.wr_data.value)
                    wr_biten_val = int(self.wr_biten.value)

                    # Apply bit-enable mask
                    for bit in range(32):
                        if (wr_biten_val >> bit) & 1:
                            if (wr_val >> bit) & 1:
                                self.mem[idx] |= 1 << bit
                            else:
                                self.mem[idx] &= ~(1 << bit)

                    self.wr_ack.value = 1
                else:
                    # Read request
                    self.rd_data.value = self.mem[idx]
                    self.rd_ack.value = 1


class SimpleExtMemReadOnly:
    """Emulates a read-only external memory block"""

    def __init__(self, dut, clk, prefix, num_entries=4):
        self.dut = dut
        self.clk = clk
        self.prefix = prefix

        # Protocol signals
        self.req = getattr(dut, f"{prefix}_req")
        self.req_is_wr = getattr(dut, f"{prefix}_req_is_wr")
        self.addr = getattr(dut, f"{prefix}_addr")

        # Response signals
        in_prefix = prefix.replace("hwif_out", "hwif_in")
        self.rd_ack = getattr(dut, f"{in_prefix}_rd_ack")
        self.rd_data = getattr(dut, f"{in_prefix}_rd_data")
        self.wr_ack = getattr(dut, f"{in_prefix}_wr_ack")

        # Internal storage (can be set by test)
        self.mem = [0] * num_entries

        # Initialize response signals
        self.rd_ack.value = 0
        self.rd_data.value = 0
        self.wr_ack.value = 0

    async def run(self):
        """Run the emulator"""
        while True:
            await RisingEdge(self.clk)

            # Default: no ack
            self.rd_ack.value = 0
            self.wr_ack.value = 0

            try:
                req_val = int(self.req.value)
                req_is_wr_val = int(self.req_is_wr.value)
                addr_val = int(self.addr.value)
            except ValueError:
                continue

            if req_val == 1:
                # Address is in bytes, divide by 4 for word index
                idx = (addr_val >> 2) % len(self.mem)

                if req_is_wr_val == 0:
                    # Read request only
                    self.rd_data.value = self.mem[idx]
                    self.rd_ack.value = 1
                else:
                    # Write request - ack but don't modify
                    self.wr_ack.value = 1


class SimpleExtMemWriteOnly:
    """Emulates a write-only external memory block"""

    def __init__(self, dut, clk, prefix, num_entries=4):
        self.dut = dut
        self.clk = clk
        self.prefix = prefix

        # Protocol signals
        self.req = getattr(dut, f"{prefix}_req")
        self.req_is_wr = getattr(dut, f"{prefix}_req_is_wr")
        self.addr = getattr(dut, f"{prefix}_addr")
        self.wr_data = getattr(dut, f"{prefix}_wr_data")
        self.wr_biten = getattr(dut, f"{prefix}_wr_biten")

        # Response signals
        in_prefix = prefix.replace("hwif_out", "hwif_in")
        self.rd_ack = getattr(dut, f"{in_prefix}_rd_ack")
        self.rd_data = getattr(dut, f"{in_prefix}_rd_data")
        self.wr_ack = getattr(dut, f"{in_prefix}_wr_ack")

        # Internal storage (can be read by test)
        self.mem = [0] * num_entries

        # Initialize response signals
        self.rd_ack.value = 0
        self.rd_data.value = 0
        self.wr_ack.value = 0

    async def run(self):
        """Run the emulator"""
        while True:
            await RisingEdge(self.clk)

            # Default: no ack
            self.rd_ack.value = 0
            self.wr_ack.value = 0

            try:
                req_val = int(self.req.value)
                req_is_wr_val = int(self.req_is_wr.value)
                addr_val = int(self.addr.value)
            except ValueError:
                continue

            if req_val == 1:
                # Address is in bytes, divide by 4 for word index
                idx = (addr_val >> 2) % len(self.mem)

                if req_is_wr_val == 1:
                    # Write request only
                    wr_val = int(self.wr_data.value)
                    wr_biten_val = int(self.wr_biten.value)

                    # Apply bit-enable mask
                    for bit in range(32):
                        if (wr_biten_val >> bit) & 1:
                            if (wr_val >> bit) & 1:
                                self.mem[idx] |= 1 << bit
                            else:
                                self.mem[idx] &= ~(1 << bit)

                    self.wr_ack.value = 1
                else:
                    # Read request - ack but return 0
                    self.rd_data.value = 0
                    self.rd_ack.value = 1
