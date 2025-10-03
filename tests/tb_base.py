from interfaces.clkreset import Clk
from interfaces.clkreset import Reset


class testbench:
    def __init__(self, dut, reset_sense=1):

        period = 10
        self.clk = Clk(dut, period, clkname="clk")
        self.reset = Reset(dut, self.clk, reset_sense=reset_sense, resetname="rst")

        if hasattr(dut, "s_cpuif_req"):
            from interfaces.passthrough import PTBus, PTMaster

            pt_bus = PTBus.from_prefix(dut, "s_cpuif")
            self.intf = PTMaster(pt_bus, getattr(dut, "clk"))
        elif hasattr(dut, "s_apb_penable"):
            from cocotbext.apb import ApbBus
            from cocotbext.apb import ApbMaster

            apb_bus = ApbBus.from_prefix(dut, "s_apb")
            self.intf = ApbMaster(apb_bus, getattr(dut, "clk"))
        elif hasattr(dut, "s_axil_awvalid"):
            from interfaces.axi_driver import AxiDriver

            apb_bus = ApbBus.from_prefix(dut, "s_apb")
            self.intf = AxiDriver(dut, "s_axil", "clk")
        else:
            raise Exception("Unsupported interface")

        for attr in dir(dut):
            if attr.startswith("hwif_"):
                sig = getattr(dut, attr)
                setattr(self, attr, sig)
                # Only initialize inputs, not outputs
                if attr.startswith("hwif_in_"):
                    sig.value = 0
