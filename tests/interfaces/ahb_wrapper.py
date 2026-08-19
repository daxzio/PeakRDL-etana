import math
import logging
from collections import deque
from cocotb import start_soon
from cocotb.triggers import RisingEdge
from cocotb.utils import get_sim_time

from cocotbext.ahb import AHBBus, AHBLiteMaster, AHBMonitor, AHBTrans, AHBBurst


# from cocotbext.ahb import AHBMaster

from typing import Optional, Sequence, Union, Any, List
import collections.abc


def _is_seq(value: Any) -> bool:
    return isinstance(value, collections.abc.Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    )


class AHBMonitorDX(AHBMonitor):
    def __init__(
        self, bus: AHBBus, clock: str, reset: str, prefix: str = "", **kwargs: Any
    ) -> None:
        super().__init__(bus, clock, reset, **kwargs)
        self.prefix = prefix
        self.txn_receive = False
        self.enable_log_write = False
        self.enable_log_read = False
        start_soon(self._log_txn())

    async def _log_txn(self):
        self.log.setLevel(logging.DEBUG)
        while True:
            self.txn_receive = False
            self.txn = await self.wait_for_recv()
            self.txn_receive = True
            if (
                not AHBBurst.SINGLE == self.txn.burst
                and not AHBBurst.INCR == self.txn.burst
            ):
                raise AssertionError(f"Unsupported Burst type - {self.txn.burst.name}")
            if (
                not AHBTrans.NONSEQ == self.txn.trans
                and not AHBTrans.SEQ == self.txn.trans
            ):
                raise AssertionError(f"Unsupported Trans type - {self.txn.trans.name}")
            if self.txn.mode:
                if self.enable_log_write:
                    self.log.debug(
                        f"Write {self.prefix} 0x{self.txn.addr:08x} 0x{self.txn.wdata:08x} {self.txn.burst.name} {self.txn.trans.name}"
                    )
            else:
                if self.enable_log_read:
                    self.log.debug(
                        f"Read  {self.prefix} 0x{self.txn.addr:08x} 0x{self.txn.rdata:08x} {self.txn.burst.name} {self.txn.trans.name}"
                    )
            await RisingEdge(self.clk)

    def enable_write_logging(self):
        self.log.setLevel(logging.DEBUG)
        self.enable_log_write = True

    def enable_read_logging(self):
        self.log.setLevel(logging.DEBUG)
        self.enable_log_read = True


class AHBMasterDX(AHBLiteMaster):
    """PeakRDL-etana wrapper around upstream AHBLiteMaster.

    Blocking write()/read() stay sequential (one API call per beat). Packed
    traffic uses write_nowait()/read_nowait() then wait(), which drains the
    queue in one custom(pip=True) burst so address N+1 can overlap data N.
    """

    def __init__(
        self,
        bus: AHBBus,
        clock: str,
        reset: str,
        **kwargs,
    ):
        self.pip = True
        super().__init__(bus, clock, reset, **kwargs)
        self.buswidth = bus._data_width
        self.mask = (2**self.buswidth) - 1
        self.incr = int(self.buswidth / 8)
        self._pending: List[dict] = []
        self.queue_rx: deque = deque()
        self.tx_id = 0

    @property
    def count_rx(self) -> int:
        return len(self.queue_rx)

    def check_read(self, addr=None):
        if not self.returned_val == self.value and not -1 == self.value:
            raise Exception(
                f"Expected 0x{addr:08x} 0x{self.value:08x} doesn't match returned 0x{self.returned_val:08x}"
            )

    def prepare_addresses(
        self,
        address: Union[int, Sequence[int]],
        value: Union[int, Sequence[int]],
        mode: Union[int, Sequence[int]],
        length: None,
    ):
        if length is None:
            self.length = self.incr
        else:
            self.length = length
        if not math.log2(self.length).is_integer():
            raise Exception(f"Length {self.length} must be a power of 2!")

        if _is_seq(address):
            self.addresses = list(address)
            if _is_seq(mode):
                self.mode = list(mode)
            else:
                self.mode = [mode] * len(self.addresses)
            if _is_seq(value):
                self.values = list(value)
            elif value == -1:
                self.values = [-1] * len(self.addresses)
            else:
                self.values = [value & self.mask] * len(self.addresses)
            if len(self.values) != len(self.addresses) or len(self.mode) != len(
                self.addresses
            ):
                raise Exception(
                    f"Address/value/mode length mismatch: "
                    f"{len(self.addresses)}/{len(self.values)}/{len(self.mode)}"
                )
            return

        self.addresses = []
        self.mode = []
        self.values = []
        for i in range(self.length // self.incr):
            self.addresses.append(address + (i * self.incr))
            self.mode.append(mode)
            if -1 == value:
                self.values.append(value)
            else:
                self.values.append((value >> (i * self.buswidth)) & self.mask)

    def enable_backpressure(self):
        self.backpressure = True

    def disable_backpressure(self):
        self.backpressure = False

    def start_accept_monitor(self, edges: list) -> None:
        """Record sim time when an address phase is accepted (HTRANS[1] && HREADY)."""
        start_soon(self._monitor_accepts(edges))

    async def _monitor_accepts(self, edges: list) -> None:
        await RisingEdge(self.clk)
        while True:
            await RisingEdge(self.clk)
            try:
                if not self.bus.hready.value.is_resolvable:
                    continue
                if not self.bus.htrans.value.is_resolvable:
                    continue
                hsel = 1
                if self.bus.hsel_exist:
                    if not self.bus.hsel.value.is_resolvable:
                        continue
                    hsel = int(self.bus.hsel.value)
                htrans = int(self.bus.htrans.value)
                hready = int(self.bus.hready.value)
            except (ValueError, TypeError):
                continue
            if hsel and (htrans & 0x2) and hready:
                edges.append(get_sim_time("ns"))

    def _enqueue(self, address, value, mode, length, error_expected) -> List[int]:
        self.prepare_addresses(address, value, mode, length)
        tx_ids = []
        for addr, val, md in zip(self.addresses, self.values, self.mode):
            self.tx_id += 1
            tx_ids.append(self.tx_id)
            self._pending.append(
                {
                    "tx_id": self.tx_id,
                    "addr": addr,
                    "value": val,
                    "mode": md,
                    "error_expected": error_expected,
                }
            )
        return tx_ids

    def write_nowait(
        self,
        address: Union[int, Sequence[int]],
        value: Union[int, Sequence[int]],
        length: Optional[int] = None,
        error_expected: bool = False,
    ) -> None:
        """Queue write beats; drive them on wait() as one pipelined burst."""
        self._enqueue(address, value, 1, length, error_expected)

    def read_nowait(
        self,
        address: Union[int, Sequence[int]],
        value: Optional[Union[int, Sequence[int]]] = -1,
        length: Optional[int] = None,
        error_expected: bool = False,
    ) -> int:
        """Queue read beats; drive them on wait(). Returns the first tx-id."""
        tx_ids = self._enqueue(address, value, 0, length, error_expected)
        return tx_ids[0]

    def _check_beat(self, beat: dict, resp: dict, record_rx: bool = False) -> int:
        returned_val = int(resp["data"], 16)
        resp_val = resp.get("resp", 0)
        has_error = resp_val != 0
        addr = beat["addr"]

        if beat["error_expected"] and not has_error:
            raise Exception(
                f"Expected error response at 0x{addr:08x} but got OKAY (resp={resp_val})"
            )
        if not beat["error_expected"] and has_error:
            raise Exception(
                f"Unexpected error response at 0x{addr:08x}: resp={resp_val}"
            )

        if beat["mode"]:
            self.log.info(f"Write 0x{addr:08x}: 0x{beat['value']:08x}")
        else:
            self.log.info(f"Read  0x{addr:08x}: 0x{returned_val:08x}")
            if not beat["error_expected"]:
                self.returned_val = returned_val
                self.value = beat["value"]
                self.check_read(addr)
            if record_rx:
                self.queue_rx.append((returned_val, beat["tx_id"]))
        return returned_val

    async def wait(self, pip: Optional[bool] = True, **kwargs) -> Sequence[dict]:
        """Drain queued nowait beats in one custom() burst (pip=True overlaps phases)."""
        if not self._pending:
            return []
        pending = self._pending
        self._pending = []
        addrs = [b["addr"] for b in pending]
        values = [b["value"] if b["mode"] else 0 for b in pending]
        modes = [b["mode"] for b in pending]
        kwargs.setdefault("pip", pip)
        ret = await super().custom(addrs, values, mode=modes, **kwargs)
        if len(ret) != len(pending):
            raise Exception(
                f"Response count {len(ret)} does not match queued beats {len(pending)}"
            )
        for beat, resp in zip(pending, ret):
            self._check_beat(beat, resp, record_rx=True)
        return ret

    async def write(
        self,
        address: Union[int, Sequence[int]],
        value: Union[int, Sequence[int]],
        length: Optional[int] = None,
        error_expected: bool = False,
        **kwargs,
    ) -> Sequence[dict]:
        self.prepare_addresses(address, value, 1, length)  # type: ignore[arg-type]
        kwargs.setdefault("pip", self.pip)

        ret = await super().custom(
            self.addresses, self.values, mode=self.mode, **kwargs
        )

        pending = [
            {
                "tx_id": 0,
                "addr": addr,
                "value": val,
                "mode": 1,
                "error_expected": error_expected,
            }
            for addr, val in zip(self.addresses, self.values)
        ]
        for beat, resp in zip(pending, ret):
            self._check_beat(beat, resp)

        return ret

    async def read(
        self,
        address: Union[int, Sequence[int]],
        value: Optional[Union[int, Sequence[int]]] = -1,
        length: Optional[int] = None,
        error_expected: bool = False,
        **kwargs,
    ) -> Sequence[dict]:
        self.prepare_addresses(address, value, 0, length)  # type: ignore[arg-type]
        kwargs.setdefault("pip", self.pip)
        ret = await super().custom(
            self.addresses, [0] * len(self.addresses), mode=self.mode, **kwargs
        )

        pending = [
            {
                "tx_id": 0,
                "addr": addr,
                "value": val,
                "mode": 0,
                "error_expected": error_expected,
            }
            for addr, val in zip(self.addresses, self.values)
        ]
        returned = 0
        for beat, resp in zip(pending, ret):
            returned = self._check_beat(beat, resp)

        return returned  # type: ignore[return-value]
