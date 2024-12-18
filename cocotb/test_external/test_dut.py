import re
from random import randint
from cocotb import test
from cocotb import start_soon
from cocotb.triggers import RisingEdge

from interfaces.clkrst import ClkReset
from cocotbext.apb import ApbMaster
from cocotbext.apb import ApbBus


def resolve_x_int(x):
    if re.search("[xz]", str(x), re.I):
        y = re.sub("[xz]", "0", str(x), flags=re.I)
        return int(y)
    return x.integer


class testbench:
    def __init__(self, dut, reset_sense=1, period=10):

        self.regwidth = 32
        #         self.n_regs = int(dut.N_REGS)
        self.mask = (2**self.regwidth) - 1
        self.incr = int(self.regwidth / 8)
        self.cr = ClkReset(dut, period, reset_sense=reset_sense, resetname="rst")
        self.dut = dut

        start_soon(self.respond_req_rd(self.cr.clk, dut, "hwif_in_ext_reg"))
        start_soon(self.respond_req_rd(self.cr.clk, dut, "hwif_in_ext_ret", delay=0))
        start_soon(self.respond_req_rd(self.cr.clk, dut, "hwif_in_ext_rex", delay=1))
        start_soon(self.respond_req_rd(self.cr.clk, dut, "hwif_in_ext_rew"))
        start_soon(self.respond_req_rd(self.cr.clk, dut, "hwif_in_ext_rea"))
        start_soon(self.respond_req_wr(self.cr.clk, dut, "hwif_in_ext_rew"))
        start_soon(self.respond_req_wr(self.cr.clk, dut, "hwif_in_ext_rez"))
        start_soon(self.respond_req_wr(self.cr.clk, dut, "hwif_in_ext_rea"))
        start_soon(self.respond_req_rd(self.cr.clk, dut, "hwif_in_ext_rea_array"))
        start_soon(self.respond_req_wr(self.cr.clk, dut, "hwif_in_ext_rea_array"))
        start_soon(self.respond_req_rd(self.cr.clk, dut, "hwif_in_ext_reg_array"))
        #         start_soon(self.respond_req_rd(self.cr.clk, dut,'hwif_in_wide_ext_reg'))
        start_soon(self.external_regfile(self.cr.clk, dut, "hwif_.+_wide_ext_reg"))
        start_soon(self.external_regfile(self.cr.clk, dut, "hwif_.+_rf", delay=-1))
        start_soon(self.external_regfile(self.cr.clk, dut, "hwif_.+_rx", delay=-1))
        #         start_soon(self.external_regfile(self.cr.clk, dut, 'hwif_.+_am', delay=-1))
        start_soon(self.external_regfile(self.cr.clk, dut, "hwif_.+_mm", delay=-1))

        apb_prefix = "s_apb"
        self.bus = ApbBus.from_prefix(dut, apb_prefix)
        clk_name = "clk"
        self.intf = ApbMaster(self.bus, getattr(dut, clk_name))

    async def respond_req_rd(self, clk, dut, prefix, delay=2):
        prefix_out = re.sub("_in_", "_out_", prefix)
        ack = getattr(dut, f"{prefix}_rd_ack")
        req = getattr(dut, f"{prefix_out}_req")
        ack.value = 0
        while True:
            await RisingEdge(clk)
            if not 0 == req.value:
                req_store = req.value
                for i in range(delay):
                    await RisingEdge(clk)
                if 1 == len(ack):
                    ack.value = 1
                else:
                    ack.value = req_store
                await RisingEdge(clk)
                ack.value = 0

    async def respond_req_wr(self, clk, dut, prefix, delay=2):
        prefix_out = re.sub("_in_", "_out_", prefix)
        req = getattr(dut, f"{prefix_out}_req")
        wr = getattr(dut, f"{prefix_out}_req_is_wr")
        ack = getattr(dut, f"{prefix}_wr_ack")
        read = False
        write = False
        #         rdata = {}
        #         wdata = {}
        inst_name = None
        data = []
        for i in range(len(req)):
            data.append(None)
        for attr in dir(dut):
            if attr.startswith(prefix) and attr.endswith("rd_data"):
                g = re.search("_([a-zA-Z0-9]+)_rd_data", attr)
                read = True
                rdata = getattr(dut, attr)
                rdata.value = 0
                #                 print(attr, g.group(0), g.group(1))
                inst_name = g.group(1)
            if attr.endswith(f"{inst_name}_wr_data"):
                write = True
                wdata = getattr(dut, attr)
        #                 print(attr)
        ack.value = 0
        while True:
            await RisingEdge(clk)
            if 1 == req.value:
                if not len(req) == len(ack):
                    index = (int(req.value) ** 2) - 1
                    print(int(req.value), index)
                else:
                    index = 0
                if 1 == wr.value and read and write:
                    data[index] = int(wdata.value)
                if 1 == wr.value and read and write:
                    rdata.value = data[index]
                for i in range(delay):
                    await RisingEdge(clk)
                ack.value = 1
                await RisingEdge(clk)
                ack.value = 0

    async def external_regfile(self, clk, dut, prefix, delay=0):
        rd_data = {}
        wr_data = {}
        wr_biten = {}
        #         apb_addr2 = {}
        for attr in sorted(dir(dut)):
            if g := re.search(f"{prefix}_(.+)_rd_data", attr):
                rd_data[g.group(1)] = getattr(dut, attr)
            elif g := re.search(f"{prefix}_rd_data", attr):
                rd_data[None] = getattr(dut, attr)
            if g := re.search(f"{prefix}.+rd_ack", attr):
                rd_ack = getattr(dut, attr)
            if g := re.search(f"{prefix}.+wr_ack", attr):
                wr_ack = getattr(dut, attr)
            if g := re.search(f"{prefix}.+addr", attr):
                apb_addr = getattr(dut, attr)
            if g := re.search(f"{prefix}.+req$", attr):
                req = getattr(dut, attr)
            if g := re.search(f"{prefix}.+req_is_wr", attr):
                req_is_wr = getattr(dut, attr)
            if g := re.search(f"{prefix}_(.+)_wr_data", attr):
                wr_data[g.group(1)] = getattr(dut, attr)
            elif g := re.search(f"{prefix}_wr_data", attr):
                wr_data[None] = getattr(dut, attr)
            if g := re.search(f"{prefix}_(.+)_wr_biten", attr):
                wr_biten[g.group(1)] = getattr(dut, attr)
            elif g := re.search(f"{prefix}_wr_biten", attr):
                wr_biten[None] = getattr(dut, attr)
        memory = {}
        for k in wr_data.keys():
            memory[k] = []
            for j in range(64):
                memory[k].append(0)
        while True:
            if -1 == delay:
                delay = randint(0, 4)
            else:
                delay = delay
            for k in rd_data:
                rd_data[k].value = 0
            rd_ack.value = 0
            wr_ack.value = 0
            if not 0 == resolve_x_int(req.value):
                #                 print("Request detected")
                for i in range(delay):
                    await RisingEdge(clk)
                if not len(req) == len(rd_ack):
                    addr = (int(req.value) ** 2) - 1
                else:
                    addr = int(apb_addr.value) >> 2
                if 1 == req_is_wr.value:
                    wr_ack.value = 1
                    for k in wr_data.keys():
                        memory[k][addr] = (int(wr_data[k]) & int(wr_biten[k])) | (
                            memory[k][addr] & ~(int(wr_biten[k]))
                        )
                else:
                    rd_ack.value = 1
                    for k in rd_data.keys():
                        rd_data[k].value = memory[k][addr]

            await RisingEdge(clk)


@test()
async def test_dut_basic(dut):
    tb = testbench(dut, reset_sense=1)

    await tb.cr.wait_clkn(200)

    #     await tb.intf.read(0x0000, 0x1)
    await tb.intf.write(0x0000, 0x12345678)
    await tb.intf.read(0x0000, 0x07654321)
    await tb.intf.read(0x0004, 0x37964932)
    await tb.intf.read(0x0008, 0x67843573)

    await tb.intf.read(0x000C, 0x0)
    await tb.intf.write(0x000C, 0x63456734)
    await tb.intf.read(0x000C, 0x63456734)

    await tb.intf.read(0x0010, 0x0)
    await tb.intf.write(0x0010, 0x63256734)
    await tb.intf.read(0x0010, 0x0)

    await tb.intf.read(0x0014, 0x60)
    await tb.intf.write(0x0014, 0x36763454)
    #
    await tb.intf.read(0x0100, 0x06757423)
    await tb.intf.read(0x0104, 0x1518D164)

    await tb.intf.read(0x1000)
    await tb.intf.read(0x1000, 0x0)
    await tb.intf.write(0x1000, 0x52344877)
    await tb.intf.write(0x1004, 0x85672345)
    await tb.intf.write(0x1008, 0x23765367, 0x1)
    await tb.intf.read(0x1000, 0x12344877)
    await tb.intf.read(0x1004, 0x05672345)
    await tb.intf.read(0x1008, 0x00000067)
    await tb.intf.write(0x1008, 0x98542373, 0x2)
    await tb.intf.read(0x1008, 0x00002367)

    await tb.intf.read(0x2000)
    await tb.intf.read(0x2000, 0x0)
    await tb.intf.write(0x2000, 0xFFFFFFFF)
    await tb.intf.read(0x2000, 0xF80000F0)

    await tb.intf.read(0x4000)
    await tb.intf.read(0x4000, 0x0)
    await tb.intf.write(0x4000, 0x45234877)
    await tb.intf.write(0x4004, 0x78562345)
    await tb.intf.write(0x4008, 0x62375367, 0x1)
    await tb.intf.read(0x4000, 0x45234877)
    await tb.intf.read(0x4004, 0x78562345)
    await tb.intf.read(0x4008, 0x00000067)
    await tb.intf.write(0x4008, 0x98542373, 0x2)
    await tb.intf.read(0x4008, 0x00002367)

    await tb.intf.read(0x300)
    await tb.intf.read(0x304)
    await tb.intf.write(0x300, 0x52344877)
    await tb.intf.write(0x304, 0x85672345)
    await tb.intf.read(0x300, 0x52344877)
    await tb.intf.read(0x304, 0x85672345)
    #     await tb.intf.read(0x3000)
    #     await tb.intf.read(0x3000, 0x0)
    #     await tb.intf.write(0x3000, 0x42534877)
    #     await tb.intf.write(0x3004, 0x75862345)
    #     await tb.intf.write(0x3008, 0x63275367, 0x1)
    #     await tb.intf.read(0x3000,  0x42534877)
    #     await tb.intf.read(0x3004,  0x75862345)
    #     await tb.intf.read(0x3008,  0x00000067)
    #     await tb.intf.write(0x3008, 0x98542373, 0x2)
    #     await tb.intf.read(0x3008,  0x00002367)

    await tb.cr.end_test(200)
