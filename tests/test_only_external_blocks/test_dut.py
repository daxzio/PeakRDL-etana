"""
Test only external blocks.

Ports the intent of PeakRDL-regblock's SV test_only_external_blocks into Cocotb:
- Two external memories:
  - mem1 @ 0x0000 size 0x10 bytes
  - mem2 @ 0x0200 size 0x90 bytes
- Random read/write within each range
- A burst of interleaved accesses to both blocks

This test is meant to validate that external-block address decode + req/addr
plumbing works even when there are no internal registers.
"""

import sys
from pathlib import Path

from cocotb import start_soon, test
from cocotb.triggers import RisingEdge

# Add parent directory to path to access shared test modules
test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))

from tb_base import testbench  # noqa: E402


class ExternalMemEmulator:
    """
    Simple byte-addressed external memory emulator for hwif_out_<name>_*

    Supports both etana (flattened) and regblock wrapper (flattened wrapper ports)
    since both expose the same set of external-block signals:
      - hwif_out_<name>_req
      - hwif_out_<name>_req_is_wr
      - hwif_out_<name>_addr
      - hwif_out_<name>_wr_data
      - hwif_out_<name>_wr_biten
      - hwif_in_<name>_rd_data
      - hwif_in_<name>_rd_ack / wr_ack
    """

    def __init__(self, dut, clk, name: str, size_bytes: int):
        self.clk = clk
        self.name = name

        self.req = getattr(dut, f"hwif_out_{name}_req")
        self.req_is_wr = getattr(dut, f"hwif_out_{name}_req_is_wr")
        self.addr = getattr(dut, f"hwif_out_{name}_addr")
        self.wr_data = getattr(dut, f"hwif_out_{name}_wr_data")
        self.wr_biten = getattr(dut, f"hwif_out_{name}_wr_biten")

        self.rd_data = getattr(dut, f"hwif_in_{name}_rd_data")
        self.rd_ack = getattr(dut, f"hwif_in_{name}_rd_ack")
        self.wr_ack = getattr(dut, f"hwif_in_{name}_wr_ack")

        # Storage as 32-bit words
        self.n_words = size_bytes // 4
        self.mem = [0] * self.n_words

        self.rd_data.value = 0
        self.rd_ack.value = 0
        self.wr_ack.value = 0

    @staticmethod
    def _apply_biten(old: int, new: int, biten: int) -> int:
        out = old
        for bit in range(32):
            if (biten >> bit) & 1:
                if (new >> bit) & 1:
                    out |= 1 << bit
                else:
                    out &= ~(1 << bit)
        return out

    async def run(self):
        while True:
            await RisingEdge(self.clk)
            self.rd_ack.value = 0
            self.wr_ack.value = 0

            try:
                if int(self.req.value) != 1:
                    continue
                is_wr = int(self.req_is_wr.value)
                byte_addr = int(self.addr.value)
            except ValueError:
                continue

            word_idx = (byte_addr // 4) % self.n_words

            if is_wr:
                wdata = int(self.wr_data.value)
                wmask = int(self.wr_biten.value)
                self.mem[word_idx] = self._apply_biten(self.mem[word_idx], wdata, wmask)
                self.wr_ack.value = 1
            else:
                self.rd_data.value = self.mem[word_idx]
                self.rd_ack.value = 1


@test()
async def test_dut_only_external_blocks(dut):
    tb = testbench(dut)
    await tb.clk.wait_clkn(200)

    # Start emulators for both external blocks
    mem1 = ExternalMemEmulator(dut, tb.clk.clk, "mem1", size_bytes=0x10)
    mem2 = ExternalMemEmulator(dut, tb.clk.clk, "mem2", size_bytes=0x90)
    start_soon(mem1.run())
    start_soon(mem2.run())

    # Simple read/write tests (random within each range)
    import random

    for _ in range(32):
        x = random.getrandbits(32)
        addr = 0x0000 + random.randrange(0, 0x10 // 4) * 4
        await tb.intf.write(addr, x)
        await tb.intf.read(addr, x)

    for _ in range(32):
        x = random.getrandbits(32)
        addr = 0x0200 + random.randrange(0, 0x90 // 4) * 4
        await tb.intf.write(addr, x)
        await tb.intf.read(addr, x)

    # Interleaved accesses: initialize with known values
    for i in range(0x10 // 4):
        await tb.intf.write(0x0000 + i * 4, 0x1000 + i)
    for i in range(0x90 // 4):
        await tb.intf.write(0x0200 + i * 4, 0x3000 + i)

    # Random mix of reads/writes across both blocks
    for _ in range(256):
        which = random.randrange(2)
        if which == 0:
            i = random.randrange(0x10 // 4)
            addr = 0x0000 + i * 4
            x = 0x1000 + i
        else:
            i = random.randrange(0x90 // 4)
            addr = 0x0200 + i * 4
            x = 0x3000 + i

        if random.randrange(2) == 0:
            await tb.intf.write(addr, x)
        else:
            await tb.intf.read(addr, x)

    await tb.clk.end_test()
