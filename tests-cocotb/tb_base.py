from cocotbext.apb import ApbBus
from cocotbext.apb import ApbMaster

from interfaces.clkreset import Clk
from interfaces.clkreset import Reset

from interfaces.passthrough import PTBus, PTMaster
from interfaces.axi_driver import AxiDriver


class testbench:
    def __init__(self, dut, reset_sense=1):

        period = 10
        self.clk = Clk(dut, period, clkname="clk")
        self.reset = Reset(dut, self.clk, reset_sense=reset_sense, resetname="rst")

        if hasattr(dut, "s_cpuif_req"):
            pt_bus = PTBus.from_prefix(dut, "s_cpuif")
            self.intf = PTMaster(pt_bus, getattr(dut, "clk"))
        elif hasattr(dut, "s_apb_penable"):
            apb_bus = ApbBus.from_prefix(dut, "s_apb")
            self.intf = ApbMaster(apb_bus, getattr(dut, "clk"))
        elif hasattr(dut, "s_axil_awvalid"):
            apb_bus = ApbBus.from_prefix(dut, "s_apb")
            self.intf = AxiDriver(dut, "s_axil", "clk")
        else:
            raise Exception("Unsupported interface")

        #         exit()
        #         print(dir(dut))
        #         if hasattr(dut, 'hwif_out'):
        #             print(dir(dut.hwif_out))
        #         else:
        for attr in dir(dut):
            if attr.startswith("hwif_"):
                #                 print(attr)
                setattr(self, attr, getattr(dut, attr))


#         exit()
