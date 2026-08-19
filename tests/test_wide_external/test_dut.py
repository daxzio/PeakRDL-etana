import sys
from pathlib import Path

# Add parent directory to path to access shared test modules
test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))
from cocotb import start_soon, test  # noqa: E402
from cocotb.triggers import RisingEdge  # noqa: E402

from tb_base import testbench  # noqa: E402


class WideExternalRegEmulator:
    """
    Emulate external wide register mram1 (regwidth=64, accesswidth=32)

    Wrapper exposes:
    - hwif_out_mram1_req        : [1:0] one-hot subword select
    - hwif_out_mram1_req_is_wr  : direction
    - hwif_out_mram1_wr_data    : 32-bit
    - hwif_out_mram1_wr_biten   : 32-bit
    - hwif_in_mram1_rd_data     : 32-bit (selected subword)
    - hwif_in_mram1_rd_ack / wr_ack
    """

    def __init__(self, dut, clk):
        self.clk = clk

        self.req = dut.hwif_out_mram1_req
        self.req_is_wr = dut.hwif_out_mram1_req_is_wr
        self.wr_data = dut.hwif_out_mram1_wr_data
        self.wr_biten = dut.hwif_out_mram1_wr_biten

        self.rd_data = dut.hwif_in_mram1_rd_data
        self.rd_ack = dut.hwif_in_mram1_rd_ack
        self.wr_ack = dut.hwif_in_mram1_wr_ack

        # 2x 32-bit subwords
        self.storage = [0, 0]

        self.rd_data.value = 0
        self.rd_ack.value = 0
        self.wr_ack.value = 0

    @staticmethod
    def _apply_biten(old: int, new: int, biten: int) -> int:
        # biten is 1-bit per data bit (Passthrough style)
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
                req_val = int(self.req.value)
                is_wr = int(self.req_is_wr.value)
            except ValueError:
                continue

            if req_val == 0:
                continue

            # Determine subword from one-hot req bits
            subword = 0 if (req_val & 0x1) else 1

            if is_wr:
                wdata = int(self.wr_data.value)
                wmask = int(self.wr_biten.value)
                self.storage[subword] = self._apply_biten(
                    self.storage[subword], wdata, wmask
                )
                self.wr_ack.value = 1
            else:
                self.rd_data.value = self.storage[subword]
                self.rd_ack.value = 1


class ExternalMemEmulator32:
    """
    Emulate external memory mm1 (memwidth=64, but wrapper interface is 32-bit)

    Wrapper exposes:
    - hwif_out_mm1_req, hwif_out_mm1_req_is_wr, hwif_out_mm1_addr
    - hwif_out_mm1_wr_data (32), hwif_out_mm1_wr_biten (32)
    - hwif_in_mm1_rd_data (32), hwif_in_mm1_rd_ack / wr_ack
    """

    def __init__(self, dut, clk):
        self.clk = clk

        self.req = dut.hwif_out_mm1_req
        self.req_is_wr = dut.hwif_out_mm1_req_is_wr
        self.addr = dut.hwif_out_mm1_addr
        self.wr_data = dut.hwif_out_mm1_wr_data
        self.wr_biten = dut.hwif_out_mm1_wr_biten

        self.rd_data = dut.hwif_in_mm1_rd_data
        self.rd_ack = dut.hwif_in_mm1_rd_ack
        self.rd_err = dut.hwif_in_mm1_rd_err
        self.wr_ack = dut.hwif_in_mm1_wr_ack
        self.wr_err = dut.hwif_in_mm1_wr_err

        # Store 32-bit words by word index
        self.storage = {}

        self.rd_data.value = 0
        self.rd_ack.value = 0
        self.rd_err.value = 0
        self.wr_ack.value = 0
        self.wr_err.value = 0

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
            self.rd_err.value = 0
            self.wr_ack.value = 0
            self.wr_err.value = 0

            try:
                if int(self.req.value) != 1:
                    continue
                is_wr = int(self.req_is_wr.value)
                byte_addr = int(self.addr.value)
            except ValueError:
                continue

            word_idx = byte_addr // 4

            if is_wr:
                wdata = int(self.wr_data.value)
                wmask = int(self.wr_biten.value)
                prev = self.storage.get(word_idx, 0)
                self.storage[word_idx] = self._apply_biten(prev, wdata, wmask)
                self.wr_ack.value = 1
            else:
                self.rd_data.value = self.storage.get(word_idx, 0)
                self.rd_ack.value = 1


@test()
async def test_dut_simple(dut):
    tb = testbench(dut)
    await tb.clk.wait_clkn(200)

    # Start external emulators
    mram1 = WideExternalRegEmulator(dut, tb.clk.clk)
    mm1 = ExternalMemEmulator32(dut, tb.clk.clk)
    start_soon(mram1.run())
    start_soon(mm1.run())

    # Wide external reg @ 0x10 (2 subwords: 0x10, 0x14)
    await tb.intf.read(0x0010, 0x0)
    await tb.intf.read(0x0014, 0x0)
    await tb.intf.write(0x0010, 0x12345678)
    await tb.intf.write(0x0014, 0x9ABCDEF0)
    await tb.intf.read(0x0010, 0x12345678)
    await tb.intf.read(0x0014, 0x9ABCDEF0)

    # Wide external mem @ 0x40000, size 0x40000 bytes
    # Verify lowest and highest word addresses to catch truncation issues
    base = 0x40000
    last = base + 0x40000 - 4
    await tb.intf.read(base, 0x0)
    await tb.intf.read(last, 0x0)
    await tb.intf.write(base, 0xCAFEBABE)
    await tb.intf.write(last, 0x0BADF00D)
    await tb.intf.read(base, 0xCAFEBABE)
    await tb.intf.read(last, 0x0BADF00D)

    await tb.clk.end_test()
