"""Wide external register with two fields in different subwords.

Field a sits at [7:0] of subword 0. Field b sits at [47:40] of the
register, which is [15:8] of subword 1. Etana exposes one data port
per field. Regblock exposes one bus-width port for the active subword.
"""

import sys
from pathlib import Path

test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))

from cocotb import test, start_soon  # noqa: E402
from cocotb.triggers import RisingEdge  # noqa: E402
from tb_base import testbench  # noqa: E402


class WideMultiFieldEmulator:
    def __init__(self, dut, clk):
        self.clk = clk
        self.req = dut.hwif_out_wide2_req
        self.req_is_wr = dut.hwif_out_wide2_req_is_wr
        self.rd_ack = dut.hwif_in_wide2_rd_ack
        self.wr_ack = dut.hwif_in_wide2_wr_ack
        self.per_field = hasattr(dut, "hwif_out_wide2_wr_data_a")
        if self.per_field:
            self.wr_data_a = dut.hwif_out_wide2_wr_data_a
            self.wr_biten_a = dut.hwif_out_wide2_wr_biten_a
            self.wr_data_b = dut.hwif_out_wide2_wr_data_b
            self.wr_biten_b = dut.hwif_out_wide2_wr_biten_b
            self.rd_data_a = dut.hwif_in_wide2_rd_data_a
            self.rd_data_b = dut.hwif_in_wide2_rd_data_b
            self.rd_data_a.value = 0
            self.rd_data_b.value = 0
        else:
            self.wr_data = dut.hwif_out_wide2_wr_data
            self.wr_biten = dut.hwif_out_wide2_wr_biten
            self.rd_data = dut.hwif_in_wide2_rd_data
            self.rd_data.value = 0
        self.a = 0
        self.b = 0
        self.rd_ack.value = 0
        self.wr_ack.value = 0

    @staticmethod
    def _merge(old, data, biten, width):
        data &= (1 << width) - 1
        biten &= (1 << width) - 1
        return (old & ~biten) | (data & biten)

    async def run(self):
        while True:
            await RisingEdge(self.clk)
            self.rd_ack.value = 0
            self.wr_ack.value = 0
            try:
                req = int(self.req.value)
                is_wr = int(self.req_is_wr.value)
            except ValueError:
                continue
            if self.per_field:
                self.rd_data_a.value = self.a & 0xFF
                self.rd_data_b.value = self.b & 0xFF
                if req & 1 and is_wr:
                    self.a = self._merge(
                        self.a,
                        int(self.wr_data_a.value),
                        int(self.wr_biten_a.value),
                        8,
                    )
                    self.wr_ack.value = 1
                elif (req >> 1) & 1 and is_wr:
                    self.b = self._merge(
                        self.b,
                        int(self.wr_data_b.value),
                        int(self.wr_biten_b.value),
                        8,
                    )
                    self.wr_ack.value = 1
                elif req & 0x3 and not is_wr:
                    self.rd_ack.value = 1
            else:
                subword = 0 if (req & 1) else 1 if (req & 2) else None
                if subword is None:
                    continue
                if is_wr:
                    word = self._merge(
                        (self.a if subword == 0 else self.b << 8),
                        int(self.wr_data.value),
                        int(self.wr_biten.value),
                        32,
                    )
                    if subword == 0:
                        self.a = word & 0xFF
                    else:
                        self.b = (word >> 8) & 0xFF
                    self.wr_ack.value = 1
                else:
                    self.rd_data.value = self.a if subword == 0 else (self.b << 8)
                    self.rd_ack.value = 1


@test()
async def test_dut_wide_ext_multifield(dut):
    tb = testbench(dut)
    emu = WideMultiFieldEmulator(dut, tb.clk.clk)
    start_soon(emu.run())
    await tb.clk.wait_clkn(200)

    await tb.intf.read(0x0, 0)
    await tb.intf.read(0x4, 0)

    await tb.intf.write(0x0, 0xA5)
    await tb.intf.write(0x4, 0x5A00)

    await tb.intf.read(0x0, 0xA5)
    await tb.intf.read(0x4, 0x5A00)
    assert emu.a == 0xA5
    assert emu.b == 0x5A

    await tb.clk.end_test()
