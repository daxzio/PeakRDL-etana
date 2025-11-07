import logging
from cocotb import start_soon
from cocotb.triggers import RisingEdge

from cocotbext.ahb import AHBBus
from cocotbext.ahb import AHBLiteMaster
from cocotbext.ahb import AHBMonitor
from cocotbext.ahb import AHBTrans, AHBBurst

# from cocotbext.ahb import AHBMaster

from typing import Optional, Sequence, Union, Any
import collections.abc


class AHBLiteMonitorDX(AHBMonitor):
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


class AHBLiteMasterDX(AHBLiteMaster):
    def __init__(
        self,
        bus: AHBBus,
        clock: str,
        reset: str,
        **kwargs,
    ):
        self.pip = False
        super().__init__(bus, clock, reset, **kwargs)
        self.buswidth = bus._data_width
        self.mask = (2**self.buswidth) - 1
        self.incr = int(self.buswidth / 8)

    def check_read(self, addr=None):
        if not self.returned_val == self.value and not -1 == self.value:
            raise Exception(
                f"Expected 0x{addr:08x} 0x{self.value:08x} doesn't match returned 0x{self.returned_val:08x}"
            )

    def prepare_addresses(
        self,
        address: Union[int, Sequence[int]],
        value: Union[int, Sequence[int]],
        length: int = 1,
    ):
        if isinstance(address, collections.abc.Sequence):
            self.addresses = address
        else:
            self.addresses = []
            for i in range(length):
                self.addresses.append(address + (i * self.incr))
        if isinstance(value, collections.abc.Sequence):
            self.values = value
        else:
            self.values = []
            for i in range(length):
                if -1 == value:
                    self.values.append(value)
                else:
                    self.values.append((value >> (i * self.buswidth)) & self.mask)

    def enable_backpressure(self):
        self.backpressure = True

    def disable_backpressure(self):
        self.backpressure = False

    async def write(
        self,
        address: Union[int, Sequence[int]],
        value: Union[int, Sequence[int]],
        length: Optional[int] = 1,
        error_expected: bool = False,
        **kwargs,
    ) -> Sequence[dict]:
        self.prepare_addresses(address, value, length)  # type: ignore[arg-type]

        ret = await super().write(self.addresses, self.values, **kwargs)

        # Check for error response (hresp != 0)
        for i, x in enumerate(ret):
            self.log.info(f"Write 0x{self.addresses[i]:08x}: 0x{self.values[i]:08x}")
            resp_val = x.get("resp", 0)
            has_error = resp_val != 0

            if error_expected and not has_error:
                raise Exception(
                    f"Expected error response for write to 0x{self.addresses[i]:08x} but got OKAY (resp={resp_val})"
                )
            elif not error_expected and has_error:
                raise Exception(
                    f"Unexpected error response for write to 0x{self.addresses[i]:08x}: resp={resp_val}"
                )

        return ret

    async def read(
        self,
        address: Union[int, Sequence[int]],
        value: Optional[Union[int, Sequence[int]]] = -1,
        length: Optional[int] = 1,
        error_expected: bool = False,
        **kwargs,
    ) -> Sequence[dict]:
        self.prepare_addresses(address, value, length)  # type: ignore[arg-type]
        ret = await super().read(self.addresses, **kwargs)

        for i, x in enumerate(ret):
            self.returned_val = int(x["data"], 16)
            self.value = self.values[i]
            self.log.info(f"Read  0x{self.addresses[i]:08x}: 0x{self.returned_val:08x}")

            # Check for error response (hresp != 0)
            resp_val = x.get("resp", 0)
            has_error = resp_val != 0

            if error_expected and not has_error:
                raise Exception(
                    f"Expected error response at 0x{self.addresses[i]:08x} but got OKAY (resp={resp_val})"
                )
            elif not error_expected and has_error:
                raise Exception(
                    f"Unexpected error response at 0x{self.addresses[i]:08x}: resp={resp_val}"
                )

            if not error_expected:
                self.check_read(self.addresses[i])

        return int(ret[0]["data"], 16)  # type: ignore[return-value]
