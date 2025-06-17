# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2021 Spencer Chang
from cocotb.triggers import First
from cocotb.triggers import RisingEdge

from cocotbext.spi.exceptions import SpiFrameError
from cocotbext.spi.spi import reverse_word
from cocotbext.spi.spi import SpiBus
from cocotbext.spi.spi import SpiConfig
from cocotbext.spi.spi import SpiSlaveBase
from enum import Enum


class Commands(Enum):
    READ = 0x03
    FAST_READ = 0x0B
    RDID = 0x9F
    READ_ID = 0x90
    WREN = 0x06
    WRDI = 0x04
    PP = 0x02
    RDSR = 0x05
    WRR = 0x01
    RCR = 0x35
    BE = 0x60
    BE2 = 0xC7


class Memory:
    def __init__(self, data=None):
        self._data = data or {}
        self.depth = 4096

    def __getitem__(self, index):
        try:
            self._data[index]
        except KeyError:
            self._data[index] = 0xFF
        return self._data[index]

    def __setitem__(self, index, value):
        try:
            self._data[index] = self._data[index] & value
        except KeyError:
            self._data[index] = value

    def __len__(self):
        #         return len(self._data)
        return self.depth


#
#     def append(self, value):
#         self._data.append(value)
#
#     def extend(self, values):
#       self._data.extend(values)
#
#     def to_list(self):
#       return self._data


class S25FL(SpiSlaveBase):
    _config = SpiConfig(
        word_width=5 * 8,
        cpol=False,
        cpha=True,
        msb_first=True,
        frame_spacing_ns=400,
        cs_active_low=True,
    )

    def __init__(self, bus: SpiBus):
        self._mem = Memory()
        self._mem[0] = 0x12
        self._mem[1] = 0x34
        self._mem[2] = 0x56
        self._mem[3] = 0x78
        self._mem[4] = 0x9A

        self.id = [0x85, 0x16, 0x24]
        self.status = 0x38
        self.config_reg = 0x63

        self.write = False

        super().__init__(bus)

    async def _transaction(self, frame_start, frame_end):
        await frame_start
        self.idle.clear()

        # SCLK pin should be low at the chip select edge
        if bool(self._sclk.value):
            raise SpiFrameError("S25FL: sclk should be low at chip select edge")

        command = int(await self._shift(8))
        self.log.info(f"command 0x{command:02x} -> {Commands(command).name}")
        self.index = 0
        txn = False
        if Commands.READ.value == command:
            address = int(await self._shift(24))
            self.index = address
            array = self._mem
            txn = True
        elif Commands.FAST_READ.value == command:
            address = int(await self._shift(24))
            dummy = int(await self._shift(8))
            self.index = address
            array = self._mem
            txn = True
        elif Commands.RDID.value == command:
            array = self.id
            txn = True
        elif Commands.RDSR.value == command:
            array = [self.status]
            txn = True
        elif Commands.RCR.value == command:
            array = [self.config_reg]
            txn = True
        elif Commands.WRR.value == command:
            self.status = int(await self._shift(8))
            try:
                self.config_reg = int(await self._shift(8))
            except SpiFrameError:
                pass
        #             self.write = False
        elif Commands.WREN.value == command:
            self.write = True
            self.log.info(f"Enable Write")
        elif Commands.WRDI.value == command:
            #             self.write = False
            pass
        elif Commands.PP.value == command:
            address = int(await self._shift(24))
            self.index = address
            array = self._mem
            txn = True
        #             while True:
        #                 #tx_word = array[self.index]
        #                 tx_word = 0xff
        #                 try:
        #                     x = await self._shift(8, tx_word=tx_word)
        #                     content = int(x)
        #                     if self.write:
        #                         array[self.index] = content
        #                     self.index = (self.index + 1) % len(array)
        # #                     self.log.info(f"content 0x{content:02x}")
        #                 except SpiFrameError:
        #                     break
        else:
            raise Exception(f"Unimplemented command {Commands(command).name}")

        if txn:
            while True:
                if self.write:
                    tx_word = 0xFF
                else:
                    tx_word = array[self.index]
                try:
                    x = await self._shift(8, tx_word=tx_word)
                    content = int(x)
                    if self.write:
                        array[self.index] = content
                    self.index = (self.index + 1) % len(array)
                except SpiFrameError:
                    break

        if (
            Commands.WRDI.value == command
            or Commands.PP.value == command
            or Commands.WRR.value == command
        ):
            if self.write:
                self.log.info(f"Disable Write")
            self.write = False

        #         # end of frame
        #         if await First(frame_end, RisingEdge(self._sclk)) != frame_end:
        #             raise SpiFrameError("S25FL: clocked more than 40 bits")

        if bool(self._sclk.value):
            raise SpiFrameError("S25FL: sclk should be low at chip select edge")


#         if do_write:
#             self._registers[address] = content
