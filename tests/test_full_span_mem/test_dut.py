"""
Full-span external memory: in-memory emulator + structural checks.

The sim top is sw=rw. Read-only and write-only variants are generated
alongside and checked so always-true address compares stay omitted.
"""

import re
import sys
from pathlib import Path

from cocotb import start_soon, test
from cocotb.triggers import RisingEdge

test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))

from tb_base import testbench  # noqa: E402

RTL_DIR = Path(__file__).parent / "etana-rtl"
N_WORDS = 16
SIZE_BYTES = N_WORDS * 4


class InMemoryMem:
    """Same-cycle external mem model backed by a Python list."""

    def __init__(self, dut, clk, name: str = "ram"):
        self.clk = clk
        self.req = getattr(dut, f"hwif_out_{name}_req")
        self.addr = getattr(dut, f"hwif_out_{name}_addr")
        self.req_is_wr = getattr(dut, f"hwif_out_{name}_req_is_wr", None)
        self.wr_data = getattr(dut, f"hwif_out_{name}_wr_data", None)
        self.wr_biten = getattr(dut, f"hwif_out_{name}_wr_biten", None)
        self.rd_data = getattr(dut, f"hwif_in_{name}_rd_data", None)
        self.rd_ack = getattr(dut, f"hwif_in_{name}_rd_ack", None)
        self.wr_ack = getattr(dut, f"hwif_in_{name}_wr_ack", None)

        self.mem = [0] * N_WORDS
        if self.rd_data is not None:
            self.rd_data.value = 0
        if self.rd_ack is not None:
            self.rd_ack.value = 0
        if self.wr_ack is not None:
            self.wr_ack.value = 0

    @staticmethod
    def _apply_biten(old: int, new: int, biten: int) -> int:
        return (old & ~biten) | (new & biten)

    async def run(self):
        while True:
            await RisingEdge(self.clk)
            if self.rd_ack is not None:
                self.rd_ack.value = 0
            if self.wr_ack is not None:
                self.wr_ack.value = 0

            try:
                if int(self.req.value) != 1:
                    continue
                byte_addr = int(self.addr.value)
                is_wr = int(self.req_is_wr.value) if self.req_is_wr is not None else 0
            except ValueError:
                continue

            word_idx = (byte_addr // 4) % N_WORDS
            if is_wr:
                if self.wr_data is None or self.wr_ack is None:
                    continue
                wdata = int(self.wr_data.value)
                wmask = (
                    int(self.wr_biten.value)
                    if self.wr_biten is not None
                    else 0xFFFFFFFF
                )
                self.mem[word_idx] = self._apply_biten(self.mem[word_idx], wdata, wmask)
                self.wr_ack.value = 1
            elif self.rd_data is not None and self.rd_ack is not None:
                self.rd_data.value = self.mem[word_idx]
                self.rd_ack.value = 1


def _sv(name: str) -> str:
    path = RTL_DIR / name
    assert path.exists(), f"missing generated RTL {path}"
    return path.read_text()


def _assert_full_span_rtl(sv: str, access: str) -> None:
    # Comparisons (not NBA assignments like `cpuif_addr <= '0`)
    assert "(cpuif_addr <=" not in sv, "full-span decode still compares cpuif_addr"
    assert "(rd_mux_addr <=" not in sv, "full-span readback still compares rd_mux_addr"
    assert "rd_mux_addr" not in sv, "full-span DUT still declares unused rd_mux_addr"

    if access == "rw":
        assert re.search(
            r"decoded_reg_strb_ram\s*=\s*cpuif_req_masked\s*;", sv
        ), "rw strobe should be unqualified cpuif_req_masked"
        assert "hwif_in_ram_rd_ack" in sv and "hwif_in_ram_wr_ack" in sv
        assert "hwif_out_ram_req_is_wr" in sv
    elif access == "r":
        assert re.search(
            r"decoded_reg_strb_ram\s*=\s*cpuif_req_masked\s*&\s*!cpuif_req_is_wr\s*;",
            sv,
        ), "r strobe should be reads only"
        assert "hwif_in_ram_rd_ack" in sv
        assert "hwif_in_ram_wr_ack" not in sv
        assert "hwif_out_ram_req_is_wr" not in sv
    elif access == "w":
        assert re.search(
            r"decoded_reg_strb_ram\s*=\s*cpuif_req_masked\s*&\s*cpuif_req_is_wr\s*;",
            sv,
        ), "w strobe should be writes only"
        assert "hwif_in_ram_wr_ack" in sv
        assert "hwif_in_ram_rd_ack" not in sv
        assert "hwif_out_ram_req_is_wr" in sv
    else:
        raise ValueError(access)


@test()
async def test_dut_full_span_mem(dut):
    _assert_full_span_rtl(_sv("regblock.sv"), "rw")
    _assert_full_span_rtl(_sv("regblock_r.sv"), "r")
    _assert_full_span_rtl(_sv("regblock_w.sv"), "w")

    tb = testbench(dut)
    await tb.clk.wait_clkn(200)
    mem = InMemoryMem(dut, tb.clk.clk, "ram")
    start_soon(mem.run())

    golden = []
    for i in range(N_WORDS):
        val = (0xA5A50000 + i) & 0xFFFFFFFF
        golden.append(val)
        await tb.intf.write(i * 4, val)

    for i, val in enumerate(golden):
        await tb.intf.read(i * 4, val)
        assert mem.mem[i] == val

    # Byte-enable / biten path: overwrite low 16 bits of word 0 if the CPUIF
    # exposes strobes. A full-word write still works as a fallback.
    await tb.intf.write(0x00, 0x1234ABCD)
    await tb.intf.read(0x00, 0x1234ABCD)
    assert mem.mem[0] == 0x1234ABCD

    await tb.clk.end_test()
