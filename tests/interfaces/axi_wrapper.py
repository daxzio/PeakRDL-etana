import math
import logging
import itertools
from random import randint, seed
from cocotbext.axi import (
    AxiBus,
    AxiMaster,
    AxiLiteBus,
    AxiLiteMaster,
    AxiStreamBus,
    AxiStreamSource,
    AxiStreamSink,
    AxiStreamMonitor,
)


def tobytes(val, length=4):
    array = []
    for i in range(length):
        array.append((val >> (8 * i)) & 0xFF)
    return bytearray(array)


def tointeger(val):
    result = 0
    for i, j in enumerate(val):
        # print(i, j)
        result += int(j) << (8 * i)
    return result


def cycle_pause(seednum=7):
    seed(seednum)
    length = randint(0, 0xFFF)
    array = []
    for i in range(length):
        x = randint(0, 5)
        if 0 == x:
            array.append(1)
        else:
            array.append(0)
    return itertools.cycle(array)


class AxiWrapper:
    def __init__(
        self, dut, axi_prefix="s_axi", clk_name="s_aclk", reset_name=None, seednum=None
    ):
        self.log = logging.getLogger("cocotb.AxiWrapper")
        self.enable_logging()

        # Detect if this is AXI4-Lite (prefix contains "axil") or full AXI4
        is_axi_lite = "axil" in axi_prefix.lower()

        if is_axi_lite:
            # Use AXI4-Lite bus and master
            if reset_name is None:
                self.axi_master = AxiLiteMaster(
                    AxiLiteBus.from_prefix(dut, axi_prefix), getattr(dut, clk_name)
                )
            else:
                self.axi_master = AxiLiteMaster(
                    AxiLiteBus.from_prefix(dut, axi_prefix),
                    getattr(dut, clk_name),
                    getattr(dut, reset_name),
                )
        else:
            # Use full AXI4 bus and master
            if reset_name is None:
                self.axi_master = AxiMaster(
                    AxiBus.from_prefix(dut, axi_prefix), getattr(dut, clk_name)
                )
            else:
                self.axi_master = AxiMaster(
                    AxiBus.from_prefix(dut, axi_prefix),
                    getattr(dut, clk_name),
                    getattr(dut, reset_name),
                )
        self.is_axi_lite = is_axi_lite
        if not is_axi_lite:
            self.arid = 4
            self.awid = 4
        self.axi_master.write_if.log.setLevel(logging.WARNING)
        self.axi_master.read_if.log.setLevel(logging.WARNING)
        if seednum is not None:
            self.base_seed = seednum
        else:
            self.base_seed = randint(0, 0xFFFFFF)
        seed(self.base_seed)
        self.log.debug(f"Seed is set to {self.base_seed}")

    @property
    def length(self):
        if self.len is None:
            if not 0 == self.data and self.data is not None:
                return max(math.ceil(math.log2(self.data) / 8), 4)
            else:
                return 4
        return self.len

    @property
    def returned_val(self):
        if hasattr(self.read_op, "data"):
            if hasattr(self.read_op.data, "data"):
                return tointeger(self.read_op.data.data)
            else:
                return tointeger(self.read_op.data)
        else:
            return tointeger(self.read_op)

    def enable_logging(self):
        self.log.setLevel(logging.DEBUG)

    def disable_logging(self):
        self.log.setLevel(logging.WARNING)

    def enable_write_backpressure(self, seednum=None):
        if seednum is not None:
            self.base_seed = seednum
        self.axi_master.write_if.aw_channel.set_pause_generator(
            cycle_pause(self.base_seed + 1)
        )
        self.axi_master.write_if.w_channel.set_pause_generator(
            cycle_pause(self.base_seed + 2)
        )
        self.axi_master.write_if.b_channel.set_pause_generator(
            cycle_pause(self.base_seed + 3)
        )

    def enable_read_backpressure(self, seednum=None):
        if seednum is not None:
            self.base_seed = seednum
        self.axi_master.read_if.r_channel.set_pause_generator(
            cycle_pause(self.base_seed + 4)
        )
        self.axi_master.read_if.ar_channel.set_pause_generator(
            cycle_pause(self.base_seed + 5)
        )

    def enable_backpressure(self, seednum=None):
        self.enable_write_backpressure(seednum)
        self.enable_read_backpressure(seednum)

    def disable_backpressure(self):
        self.axi_master.write_if.aw_channel.set_pause_generator(
            itertools.cycle(
                [
                    0,
                ]
            )
        )
        self.axi_master.write_if.w_channel.set_pause_generator(
            itertools.cycle(
                [
                    0,
                ]
            )
        )
        self.axi_master.write_if.b_channel.set_pause_generator(
            itertools.cycle(
                [
                    0,
                ]
            )
        )

        self.axi_master.read_if.r_channel.set_pause_generator(
            itertools.cycle(
                [
                    0,
                ]
            )
        )
        self.axi_master.read_if.ar_channel.set_pause_generator(
            itertools.cycle(
                [
                    0,
                ]
            )
        )

    async def poll(self, addr, data, length=None, debug=False):
        self.log.debug(f"Poll  0x{addr:08x}: for 0x{data:04x}")
        while True:
            await self.read(addr, debug=debug)
            if data == self.returned_val:
                self.log.debug("Condition Satisified")
                break
        return

    def check_read(self, debug=True):
        if debug:
            self.log.debug(
                f"Read  0x{self.addr:08x}: 0x{self.returned_val:0{self.length*2}x}"
            )
        if not self.returned_val == self.data and self.data is not None:
            raise Exception(
                f"Expected 0x{self.data:08x} doesn't match returned 0x{self.returned_val:08x}"
            )

    async def read(
        self, addr, data=None, length=None, debug=True, error_expected=False
    ):
        self.addr = addr
        self.data = data
        self.len = length
        if self.is_axi_lite:
            self.read_op = await self.axi_master.read(self.addr, self.length)
        else:
            self.read_op = await self.axi_master.read(
                self.addr, self.length, arid=self.arid
            )

        # Check for error response
        if hasattr(self.read_op, "resp"):
            # resp values: 0b00=OKAY, 0b01=EXOKAY, 0b10=SLVERR, 0b11=DECERR
            resp_val = (
                int(self.read_op.resp)
                if hasattr(self.read_op.resp, "__int__")
                else self.read_op.resp
            )
            has_error = resp_val != 0  # Non-zero response indicates error

            if error_expected and not has_error:
                raise Exception(
                    f"Expected error response at 0x{addr:08x} but got OKAY (resp={resp_val})"
                )
            elif not error_expected and has_error:
                raise Exception(
                    f"Unexpected error response at 0x{addr:08x}: resp={resp_val}"
                )

        if not error_expected:
            self.check_read(debug)
        return self.read_op

    async def write(
        self, addr, data=None, length=None, debug=True, error_expected=False
    ):
        self.len = length
        self.addr = addr
        if data is None:
            self.data = 0
            for i in range(0, self.length, 4):
                self.data = self.data | (randint(0, 0xFFFFFFFF) << i * 8)
        else:
            self.data = data
        self.writedata = self.data
        if debug:
            self.log.debug(f"Write 0x{self.addr:08x}: 0x{self.data:0{self.length*2}x}")
        bytesdata = tobytes(self.data, self.length)
        if self.is_axi_lite:
            write_resp = await self.axi_master.write(addr, bytesdata)
        else:
            write_resp = await self.axi_master.write(addr, bytesdata, awid=self.arid)

        # Check for error response
        if write_resp is not None and hasattr(write_resp, "resp"):
            # resp values: 0b00=OKAY, 0b01=EXOKAY, 0b10=SLVERR, 0b11=DECERR
            resp_val = (
                int(write_resp.resp)
                if hasattr(write_resp.resp, "__int__")
                else write_resp.resp
            )
            has_error = resp_val != 0  # Non-zero response indicates error

            if error_expected and not has_error:
                raise Exception(
                    f"Expected error response for write to 0x{addr:08x} but got OKAY (resp={resp_val})"
                )
            elif not error_expected and has_error:
                raise Exception(
                    f"Unexpected error response for write to 0x{addr:08x}: resp={resp_val}"
                )

    async def rmodw(self, addr, data, length=None, debug=True):
        await self.read(addr, length=None, debug=False)
        newdata = data | self.returned_val
        if debug:
            self.log.debug(
                f"RmodW 0x{addr:08x}: 0x{self.returned_val:0{self.length*2}x} | 0x{data:0{self.length*2}x} -> 0x{newdata:0{self.length*2}x}"
            )
        await self.write(addr, newdata, length=None, debug=False)

    def init_read(self, *args, **kwargs):
        self.read_op = self.axi_master.init_read(*args, **kwargs)

    def read_nowait(self, addr, data=None, length=None, debug=True):
        self.addr = addr
        self.data = data
        self.len = length
        if self.is_axi_lite:
            self.init_read(self.addr, self.length)
        else:
            self.init_read(self.addr, self.length, arid=self.arid)
        if debug:
            self.log.debug(f"Read  0x{addr:08x}:")

    def write_nowait(self, addr, data=None, length=None, debug=True):
        self.len = length
        self.addr = addr
        if data is None:
            self.data = 0
            for i in range(0, self.length, 4):
                self.data = self.data | (randint(0, 0xFFFFFFFF) << i * 8)
        else:
            self.data = data
        self.writedata = self.data
        if debug:
            self.log.debug(f"Write 0x{self.addr:08x}: 0x{self.data:08x}")
        bytesdata = tobytes(self.data, self.length)
        if self.is_axi_lite:
            self.write_op = self.axi_master.init_write(self.addr, bytesdata)
        else:
            self.write_op = self.axi_master.init_write(
                self.addr, bytesdata, awid=self.arid
            )


class AxiStreamDriver:
    def __init__(
        self, dut, axi_prefix="m_axi", clk_name="m_aclk", reset_name=None, seednum=None
    ):
        self.log = logging.getLogger("cocotb.AxiStreamDriver")
        self.enable_logging()

        if reset_name is None:
            self.axis_source = AxiStreamSource(
                AxiStreamBus.from_prefix(dut, axi_prefix), getattr(dut, clk_name)
            )
        else:
            self.axis_source = AxiStreamSource(
                AxiStreamBus.from_prefix(dut, axi_prefix),
                getattr(dut, clk_name),
                dut.reset,
            )
        self.axis_source.log.setLevel(logging.WARNING)
        # self.enable_backpressure()

    def enable_logging(self):
        self.log.setLevel(logging.DEBUG)

    def disable_logging(self):
        self.log.setLevel(logging.WARNING)

    def enable_backpressure(self):
        base_seed = randint(0, 0xFFFFFF)
        self.axis_source.set_pause_generator(cycle_pause(base_seed))

    def disable_backpressure(self):
        self.axis_source.set_pause_generator(
            itertools.cycle(
                [
                    0,
                ]
            )
        )

    async def write(self, data, length=None):
        if length is None:
            if 0 == data:
                length = 4
            else:
                length = math.ceil(math.log2(data) / 32) * 4
        self.log.debug(f"Write 0x{data:08x}")
        bytesdata = tobytes(data, length)
        await self.axis_source.write(bytesdata)


class AxiStreamReceiver:
    def __init__(
        self, dut, axi_prefix="s_axi", clk_name="s_aclk", reset_name=None, seednum=None
    ):
        self.log = logging.getLogger("cocotb.AxiStreamSink")
        self.enable_logging()

        self.axis_sink = AxiStreamSink(
            AxiStreamBus.from_prefix(dut, axi_prefix), getattr(dut, clk_name)
        )
        self.axis_sink.log.setLevel(logging.WARNING)
        self.axis_mon = AxiStreamMonitor(
            AxiStreamBus.from_prefix(dut, axi_prefix), getattr(dut, clk_name)
        )
        if seednum is not None:
            self.base_seed = seednum
        else:
            self.base_seed = randint(0, 0xFFFFFF)
        seed(self.base_seed)
        self.log.debug(f"Seed is set to {self.base_seed}")

    @property
    def length(self):
        if self.len is None:
            if not 0 == self.data and self.data is not None:
                return math.ceil(math.log2(self.data) / 32) * 4
            else:
                return 4
        return self.len

    @property
    def returned_val(self):
        if hasattr(self.read_op, "data"):
            return tointeger(self.read_op.data)
        else:
            return tointeger(self.read_op)

    def check_read(self, debug=True):
        if debug:
            self.log.debug(f"Receive:          0x{self.returned_val:0{self.length*2}x}")
        if not self.returned_val == self.data and self.data is not None:
            raise Exception(
                f"Expected 0x{self.data:08x} doesn't match returned 0x{self.returned_val:08x}"
            )

    def enable_logging(self):
        self.log.setLevel(logging.DEBUG)

    def disable_logging(self):
        self.log.setLevel(logging.WARNING)

    def pause(self):
        self.axis_sink.pause = True

    def unpause(self):
        self.axis_sink.pause = False

    def enable_backpressure(self, seednum=None):
        if seednum is not None:
            self.base_seed = seednum
        self.axis_sink.set_pause_generator(cycle_pause(self.base_seed))

    async def recv(self, data=None, debug=False):
        self.data = data
        self.len = None
        self.read_op = await self.axis_sink.recv()
        self.check_read(debug)
        return self.read_op
