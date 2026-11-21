"""Test bench helpers for the CDC register tests."""

from __future__ import annotations

import logging
import os
import random
from pathlib import Path

from cocotb import start_soon
from cocotb.clock import Clock
from cocotb.triggers import (
    FallingEdge,
    ReadOnly,
    RisingEdge,
    SimTimeoutError,
    ValueChange,
    with_timeout,
)
from cocotb.utils import get_sim_time

from tb_base import testbench

BUS_PERIOD_PS = 10000

# CDC_RESET value -> (reset sense, reset port name)
_RESETS = {
    "rst": (1, "rst"),
    "rst_n": (0, "rst_n"),
    "arst": (1, "arst"),
    "arst_n": (0, "arst_n"),
}

log = logging.getLogger("cdc_tb")


def _bit(sig) -> int:
    try:
        return int(sig.value)
    except ValueError:
        return 0


class CdcTB(testbench):
    def __init__(self, dut, clocks: dict[str, int]):
        style = os.environ.get("CDC_RESET", "rst")
        sense, name = _RESETS[style]
        super().__init__(dut, reset_sense=sense, resetname=name)
        self.dut = dut
        self.reset_sense = sense
        self.reset_sig = getattr(dut, name)
        self.has_strb = hasattr(dut, "s_apb_pstrb")
        self.has_latency = hasattr(dut, "s_apb_psel")

        t_dst = os.environ.get("CDC_T_DST_PS")
        self.clocks: dict[str, Clock] = {}
        for clk_name, period_ps in clocks.items():
            if t_dst is not None:
                period_ps = int(t_dst)
            clk = Clock(getattr(dut, clk_name), period_ps, unit="ps")
            clk.start()
            self.clocks[clk_name] = clk

        fast_mode = os.environ.get("CDC_FAST_MODE")
        if fast_mode is not None:
            for attr in dir(dut):
                if attr.endswith("_fast_mode_en"):
                    getattr(dut, attr).value = int(fast_mode)

    def stop_clock(self, name: str) -> None:
        self.clocks[name].stop()

    def start_clock(self, name: str) -> None:
        self.clocks[name].start()

    async def _count_cycles(self) -> int:
        """Count cycles with psel high up to and including the one with pready."""
        cycles = 0
        while True:
            await RisingEdge(self.dut.clk)
            if _bit(self.dut.s_apb_psel):
                cycles += 1
                if _bit(self.dut.s_apb_pready):
                    return cycles

    async def _timed(self, op, timeout_cycles: int | None):
        if timeout_cycles is None:
            return await op
        try:
            return await with_timeout(
                start_soon(op), timeout_cycles * BUS_PERIOD_PS, "ps"
            )
        except SimTimeoutError as err:
            raise AssertionError(
                f"bus access not complete after {timeout_cycles} bus cycles"
            ) from err

    async def write(self, addr: int, data: int, strb: int = -1) -> int:
        counter = start_soon(self._count_cycles()) if self.has_latency else None

        async def op():
            if self.has_strb:
                await self.intf.write(addr, data, strb)
            else:
                await self.intf.write(addr, data)
            return await counter if counter else 0

        try:
            return await op()
        finally:
            if counter:
                counter.cancel()

    async def read(
        self, addr: int, timeout_cycles: int | None = None
    ) -> tuple[int, int]:
        counter = start_soon(self._count_cycles()) if self.has_latency else None

        async def op():
            raw = await self.intf.read(addr)
            data = (
                int.from_bytes(raw, byteorder="little")
                if isinstance(raw, (bytes, bytearray))
                else int(raw)
            )
            return data, (await counter if counter else 0)

        try:
            return await self._timed(op(), timeout_cycles)
        finally:
            if counter:
                counter.cancel()

    async def reset_pulse(self, cycles: int = 4) -> None:
        self.reset_sig.value = self.reset_sense
        for _ in range(cycles):
            await RisingEdge(self.dut.clk)
        self.reset_sig.value = int(not self.reset_sense)
        await RisingEdge(self.dut.clk)


class ChangeRecord:
    """Records changes of signals with the time and the rising edge they follow."""

    def __init__(self, dut, signals: dict[str, str]):
        self.dut = dut
        self.signals = signals
        self.changes: list[tuple[int, str, int]] = []
        self.violations: list[str] = []
        self.last_edge: dict[str, int | None] = {c: None for c in set(signals.values())}
        self.started = False

    async def _edges(self, clk_name: str) -> None:
        clk = getattr(self.dut, clk_name)
        while True:
            await RisingEdge(clk)
            self.last_edge[clk_name] = int(get_sim_time("ps"))

    async def _watch(self, sig_name: str, clk_name: str) -> None:
        sig = getattr(self.dut, sig_name)
        while True:
            await ValueChange(sig)
            # Wait until every task of this time step has run, so the edge time is current.
            await ReadOnly()
            now = int(get_sim_time("ps"))
            edge = self.last_edge[clk_name]
            self.changes.append((now, sig_name, int(sig.value)))
            if edge is None or not 0 <= now - edge <= 1:
                msg = f"{sig_name} changed at {now} ps, last {clk_name} edge {edge} ps"
                self.violations.append(msg)
                raise AssertionError(msg)

    def start(self) -> None:
        if self.started:
            return
        self.started = True
        for clk_name in self.last_edge:
            start_soon(self._edges(clk_name))
        for sig_name, clk_name in self.signals.items():
            start_soon(self._watch(sig_name, clk_name))

    def take(self) -> list[tuple[int, str, int]]:
        assert not self.violations, self.violations
        changes, self.changes = self.changes, []
        return changes


class MovingInputs:
    """Drives each input with (mult * counter + add) mod 2**width, counter on a falling edge."""

    def __init__(self, dut, clock: str, inputs: dict[str, tuple[int, int, int]]):
        for name, (mult, _, _) in inputs.items():
            assert mult % 2 == 1, f"{name}: multiplier must be odd to be invertible"
        self.dut = dut
        self.clock = clock
        self.inputs = inputs
        self.counter = 0

    async def _run(self) -> None:
        clk = getattr(self.dut, self.clock)
        while True:
            await FallingEdge(clk)
            self.counter += 1
            for name, (mult, add, width) in self.inputs.items():
                getattr(self.dut, name).value = (mult * self.counter + add) % (
                    1 << width
                )

    def start(self) -> None:
        start_soon(self._run())

    def decode(self, name: str, value: int) -> int:
        """Return the counter value, modulo 2**width, that produced value."""
        mult, add, width = self.inputs[name]
        mask = (1 << width) - 1
        return ((value - add) * pow(mult, -1, 1 << width)) & mask


class DstAccCount:
    """Counts the one-cycle dst_acc_en pulses of a domain, e.g. prefix "cdc_sync_clk"."""

    def __init__(self, dut, prefix: str):
        self.count = 0
        self.errors: list[str] = []
        self.sig = getattr(dut, f"{prefix}_dst_acc_en")
        self.clk = getattr(dut, prefix.removeprefix("cdc_"))
        start_soon(self._run())

    async def _run(self) -> None:
        prev = 0
        while True:
            await RisingEdge(self.clk)
            cur = _bit(self.sig)
            if cur and prev:
                self.errors.append("dst_acc_en high for more than one cycle")
            if cur and not prev:
                self.count += 1
            prev = cur

    def take(self) -> int:
        assert not self.errors, self.errors
        count, self.count = self.count, 0
        return count


def rtl_text() -> str:
    return Path("etana-rtl/regblock.sv").read_text()


def seed() -> int:
    value = (
        int(os.environ["CDC_SEED"])
        if "CDC_SEED" in os.environ
        else random.randrange(1 << 32)
    )
    log.info("CDC_SEED=%d", value)
    random.seed(value)
    return value
