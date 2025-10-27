import re
import logging
from collections import deque
from typing import Deque, Tuple, Any, Union

from cocotb import start_soon
from cocotb.triggers import RisingEdge, Event
from cocotb_bus.bus import Bus


def resolve_x_int(x):
    if re.search("[xz]", str(x.value), re.I):
        y = re.sub("[xz]", "0", str(x.value), flags=re.I)
        return int(y)
    return int(x.value)


class PTBus(Bus):

    _signals = [
        "req",
        "req_is_wr",
        "addr",
        "wr_data",
        "wr_biten",
        "req_stall_wr",
        "req_stall_rd",
        "rd_ack",
        "rd_err",
        "rd_data",
        "wr_ack",
        "wr_err",
    ]
    _optional_signals = []

    def __init__(
        self, entity=None, prefix=None, signals=None, optional_signals=None, **kwargs
    ):
        if signals is None:
            signals = self._signals
        if optional_signals is None:
            optional_signals = self._optional_signals
        super().__init__(
            entity, prefix, signals, optional_signals=optional_signals, **kwargs
        )

    @classmethod
    def from_entity(cls, entity, **kwargs):
        return cls(entity, **kwargs)

    @classmethod
    def from_prefix(cls, entity, prefix, **kwargs):
        return cls(entity, prefix, **kwargs)


class PTMaster:
    def __init__(
        self, bus, clock, name="master", timeout_cycles=1000, **kwargs
    ) -> None:
        #         super().__init__(bus, clock, name="master", **kwargs)
        self.name = name
        self.bus = bus
        self.clock = clock
        self.timeout_cycles = timeout_cycles  # -1 disables timeout
        if bus._name:
            self.log = logging.getLogger(f"cocotb.pt_{name}.{bus._name}")
        else:
            self.log = logging.getLogger(f"cocotb.pt_{name}")
        self.log.setLevel(logging.INFO)
        self.log.info(f"Passthrough {self.name}")
        #         self.log.info(f"cocotbext-pt version {__version__}")
        #         self.log.info(f"Copyright (c) 2024-{datetime.datetime.now().year} Daxzio")
        #         self.log.info("https://github.com/daxzio/cocotbext-apb")
        self.address_width = len(self.bus.addr)
        self.wwidth = len(self.bus.wr_data)
        self.rwidth = len(self.bus.rd_data)
        self.rbytes = int(self.rwidth / 8)
        self.wbytes = int(self.wwidth / 8)
        self.rdata_mask = 2**self.rwidth - 1
        self.wdata_mask = 2**self.wwidth - 1

        self.log.info(f"Passthrough {self.name} configuration:")
        self.log.info(f"  Address width: {self.address_width} bits")
        if self.timeout_cycles >= 0:
            self.log.info(f"  Timeout: {self.timeout_cycles} clock cycles")
        else:
            self.log.info("  Timeout: disabled")
        #         self.log.info(f"  Byte size: {self.byte_size} bits")
        #         self.log.info(f"  Data width: {self.wwidth} bits ({self.byte_lanes} bytes)")

        self.log.info("Passthrough signals:")
        for sig in sorted(
            list(set().union(self.bus._signals, self.bus._optional_signals))
        ):
            if hasattr(self.bus, sig):
                self.log.info(f"  {sig} width: {len(getattr(self.bus, sig))} bits")
            else:
                self.log.info(f"  {sig}: not present")

        self.queue_tx: Deque[Tuple[bool, int, bytes, int, bool, int]] = deque()
        self.queue_rx: Deque[Tuple[bytes, int]] = deque()
        self.tx_id = 0

        self.sync = Event()

        self._idle = Event()
        self._idle.set()

        self.bus.req.value = 0
        self.bus.req_is_wr.value = 0
        self.bus.addr.value = 0
        self.bus.wr_data.value = 0
        self.bus.wr_biten.value = 0

        self._run_coroutine_obj: Any = None
        self._restart()

    async def write(
        self,
        addr: int,
        data: Union[int, bytes],
        strb: int = -1,
        error_expected: bool = False,
    ) -> None:
        self.write_nowait(addr, data, strb, error_expected)
        await self._idle.wait()

    def write_nowait(
        self,
        addr: int,
        data: Union[int, bytes],
        strb: int = -1,
        error_expected: bool = False,
    ) -> None:
        """ """
        self.tx_id += 1
        if isinstance(data, int):
            datab = data.to_bytes(self.wbytes, "little")
        else:
            datab = data
        self.queue_tx.append((True, addr, datab, strb, error_expected, self.tx_id))
        self.sync.set()
        self._idle.clear()

    async def read(
        self,
        addr: int,
        data: Union[int, bytes] = bytes(),
        error_expected: bool = False,
    ) -> bytes:
        rx_id = self.read_nowait(addr, data, error_expected)
        found = False
        while not found:
            while self.queue_rx:
                ret, tx_id = self.queue_rx.popleft()
                if rx_id == tx_id:
                    found = True
                    break
            await RisingEdge(self.clock)
        await self._idle.wait()
        return ret

    def read_nowait(
        self,
        addr: int,
        data: Union[int, bytes] = bytes(),
        error_expected: bool = False,
    ) -> int:
        if isinstance(data, int):
            if data > self.rdata_mask:
                self.log.warning(
                    f"Read data 0x{data:08x} exceeds width expected 0x{self.rdata_mask:08x}"
                )
            datab = data.to_bytes(self.rbytes, "little")
        else:
            datab = data
        self.tx_id += 1
        self.queue_tx.append((False, addr, datab, -1, error_expected, self.tx_id))
        self.sync.set()
        self._idle.clear()
        return self.tx_id

    def _restart(self) -> None:
        if self._run_coroutine_obj is not None:
            self._run_coroutine_obj.kill()
        self._run_coroutine_obj = start_soon(self._run())

    @property
    def count_tx(self) -> int:
        return len(self.queue_tx)

    @property
    def empty_tx(self) -> bool:
        return not self.queue_tx

    @property
    def count_rx(self) -> int:
        return len(self.queue_rx)

    @property
    def empty_rx(self) -> bool:
        return not self.queue_rx

    @property
    def idle(self) -> bool:
        return self.empty_tx and self.empty_rx

    def clear(self) -> None:
        """Clears the RX and TX queues"""
        self.queue_tx.clear()
        self.queue_rx.clear()

    async def wait(self) -> None:
        """Wait for idle"""
        await self._idle.wait()

    async def _run(self):
        await RisingEdge(self.clock)
        while True:
            while not self.queue_tx:
                self._idle.set()
                self.sync.clear()
                await self.sync.wait()

            (
                write,
                addr,
                data,
                strb,
                error_expected,
                tx_id,
            ) = self.queue_tx.popleft()

            if addr < 0 or addr >= 2**self.address_width:
                raise ValueError("Address out of range")

            self.bus.req.value = 1
            self.bus.req_is_wr.value = write
            self.bus.addr.value = addr
            if write:
                data_int = int.from_bytes(data, byteorder="little")
                self.log.info(f"Write addr: 0x{addr:08x} data: 0x{data_int:08x}")
                self.bus.wr_data.value = data_int & self.wdata_mask
                if -1 == strb:
                    self.bus.wr_biten.value = self.wdata_mask
                else:
                    self.bus.wr_biten.value = strb
                await RisingEdge(self.clock)

                # Wait for write ack with timeout
                # Note: req_stall_wr is NOT checked here - it only prevents NEW requests
                # Once wr_ack is asserted, the transaction is complete
                cycle_count = 0
                while not self.bus.wr_ack.value:
                    await RisingEdge(self.clock)
                    cycle_count += 1
                    if self.timeout_cycles >= 0 and cycle_count >= self.timeout_cycles:
                        msg = f"Write timeout: No wr_ack after {cycle_count} cycles (addr=0x{addr:08x})"
                        self.log.critical(msg)
                        raise Exception(msg)

                if not self.bus.wr_err.value == error_expected:
                    msg = f"WR_ERR: incorrect error received {self.bus.wr_err.value}"
                    self.log.critical(msg)
                    raise Exception(msg)
            #                 if self.bus.rd_err.value:
            #                     raise Exception(f"RD_ERR received in write mode")
            else:
                self.log.info(f"Read addr: 0x{addr:08x}")
                await RisingEdge(self.clock)

                # Wait for read ack with timeout
                # Note: req_stall_rd is NOT checked here - it only prevents NEW requests
                # Once rd_ack is asserted, the transaction is complete
                cycle_count = 0
                while not self.bus.rd_ack.value:
                    await RisingEdge(self.clock)
                    cycle_count += 1
                    if self.timeout_cycles >= 0 and cycle_count >= self.timeout_cycles:
                        msg = f"Read timeout: No rd_ack after {cycle_count} cycles (addr=0x{addr:08x})"
                        self.log.critical(msg)
                        raise Exception(msg)

                if not self.bus.rd_err.value == error_expected:
                    msg = f"RD_ERR: incorrect error received {self.bus.rd_err.value}"
                    self.log.critical(msg)
                    raise Exception(msg)
                #                 ret = resolve_x_int(self.bus.rd_data)
                ret = int(self.bus.rd_data.value)
                self.log.info(f"Value read: 0x{ret:08x}")
                if not data == bytes():
                    data_int = int.from_bytes(data, byteorder="little")
                    if not data_int == ret:
                        raise Exception(
                            f"Expected 0x{data_int:08x} doesn't match returned 0x{ret:08x}"
                        )
                self.queue_rx.append((ret.to_bytes(self.rbytes, "little"), tx_id))

            self.bus.req.value = 0
            self.bus.req_is_wr.value = 0
            self.bus.addr.value = 0
            self.bus.wr_data.value = 0
            self.bus.wr_biten.value = 0

            self.sync.set()
