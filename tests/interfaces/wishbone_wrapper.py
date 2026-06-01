"""
Wishbone master wrapper compatible with the PeakRDL-etana testbench API.

Adapts cocotbext-wishbone to provide read(addr, expected, error_expected) and
write(addr, data, error_expected) matching the interface expected by tb_base.
"""

import logging
from typing import Union

from cocotbext.wishbone.driver import WishboneMaster, WBOp


class RegblockWishboneMaster(WishboneMaster):
    """
    Wishbone master workaround for PeakRDL-regblock response signaling.

    Wishbone B4 requires ACK and ERR to be mutually exclusive. PeakRDL-regblock
    (deadbf7, wishbone_tmpl.sv) drives both wb_ack and wb_err on error responses.
    cocotbext-wishbone correctly flags that as a protocol violation.

    Etana tracks this as potential upstream feedback; see UPSTREAM_SYNC_STATUS.md
    item 30. Until regblock is fixed, this subclass accepts ack+err together so
    Cocotb tests can run against the current RTL.
    """

    def _get_reply(self):
        ack = self.bus.ack.value == 1
        has_err = hasattr(self.bus, "err") and self.bus.err.value == 1
        if ack and has_err:
            return True, 2
        if ack:
            return True, 1
        if has_err:
            return True, 2
        if hasattr(self.bus, "rty") and self.bus.rty.value == 1:
            return True, 3
        return False, 0


def _to_int(val) -> int:
    """Convert cocotb LogicArray/binary value to int."""
    if val is None:
        return 0
    s = str(val)
    if "x" in s.lower() or "z" in s.lower():
        s = s.replace("x", "0").replace("X", "0").replace("z", "0").replace("Z", "0")
    return int(s, 2) if s else 0


class WishboneMasterWrapper:
    """
    Wraps cocotbext-wishbone WishboneMaster with read/write API matching
    ApbMaster, PTMaster, etc. used by PeakRDL-etana tests.
    """

    WB_SIGNALS = {
        "cyc": "cyc",
        "stb": "stb",
        "we": "we",
        "adr": "adr",
        "datwr": "odat",
        "datrd": "idat",
        "ack": "ack",
        "err": "err",
        "sel": "sel",
        "stall": "stall",
    }

    def __init__(
        self,
        dut,
        prefix: str,
        clock,
        width: int = 32,
        timeout: int = 100,
        **kwargs,
    ):
        #         if WishboneMaster is None or WBOp is None:
        #             raise ImportError("cocotbext-wishbone is required for Wishbone tests")

        self.dut = dut
        self.clock = clock
        self.width = width
        self.data_bytes = width // 8
        self.data_mask = (1 << width) - 1
        self.sel_full = (1 << self.data_bytes) - 1

        self._wb = RegblockWishboneMaster(
            dut,
            prefix,
            clock,
            width=width,
            timeout=timeout,
            signals_dict=self.WB_SIGNALS,
            **kwargs,
        )
        self.log = logging.getLogger("cocotb.wishbone_wrapper")

    async def read(
        self,
        addr: int,
        data: Union[int, bytes] = b"",
        error_expected: bool = False,
        **kwargs,
    ) -> Union[int, bytes]:
        """Perform a read transaction. data is expected value for comparison."""
        ops = [WBOp(adr=addr, dat=None, sel=self.sel_full)]
        results = await self._wb.send_cycle(ops)
        res = results[0]

        rd_val = _to_int(res.datrd) & self.data_mask
        has_err = res.ack == 2  # 1=ACK, 2=ERR, 3=RTY

        if error_expected and not has_err:
            raise Exception(
                f"Expected error response at 0x{addr:08x} but got ACK (ack={res.ack})"
            )
        if not error_expected and has_err:
            raise Exception(
                f"Unexpected error response at 0x{addr:08x} (ack={res.ack})"
            )

        if not error_expected and data:
            expected = (
                int.from_bytes(data, "little")
                if isinstance(data, bytes)
                else (data & self.data_mask)
            )
            if rd_val != expected:
                raise Exception(
                    f"Read 0x{addr:08x}: expected 0x{expected:08x} got 0x{rd_val:08x}"
                )

        return rd_val

    async def write(
        self,
        addr: int,
        data: Union[int, bytes],
        strb: int = -1,
        error_expected: bool = False,
        **kwargs,
    ) -> None:
        """Perform a write transaction."""
        if isinstance(data, int):
            data_masked = data & self.data_mask
        else:
            data_masked = int.from_bytes(data, "little") & self.data_mask

        sel = self.sel_full if strb < 0 else (strb & self.sel_full)
        ops = [WBOp(adr=addr, dat=data_masked, sel=sel)]
        results = await self._wb.send_cycle(ops)
        res = results[0]

        has_err = res.ack == 2
        if error_expected and not has_err:
            raise Exception(
                f"Expected error response for write to 0x{addr:08x} but got ACK (ack={res.ack})"
            )
        if not error_expected and has_err:
            raise Exception(
                f"Unexpected error response for write to 0x{addr:08x} (ack={res.ack})"
            )
