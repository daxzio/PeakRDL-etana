from interfaces.clkreset import Clk
from interfaces.clkreset import Reset


class testbench:
    def __init__(self, dut, reset_sense=1, reset_length=2):

        period = 10
        self.clk = Clk(dut, period, clkname="clk")
        if not reset_sense is None:
            self.reset = Reset(dut, self.clk, reset_sense=reset_sense, resetname="rst")

        if hasattr(dut, "s_cpuif_req"):
            from interfaces.passthrough import PTBus, PTMaster

            self.pt_bus = PTBus.from_prefix(dut, "s_cpuif")
            self.intf = PTMaster(self.pt_bus, getattr(dut, "clk"))
        elif hasattr(dut, "s_apb_penable"):
            from cocotbext.apb import ApbBus
            from cocotbext.apb import ApbMaster

            self.apb_bus = ApbBus.from_prefix(dut, "s_apb")
            self.intf = ApbMaster(self.apb_bus, getattr(dut, "clk"))
        elif hasattr(dut, "s_ahb_hsel"):
            from cocotbext.ahb import AHBBus

            # from cocotbext.ahb import AHBMaster
            from interfaces.ahbpipeline_wrapper import AHBPipelineMasterDX

            self.ahb_bus = AHBBus.from_prefix(dut, "s_ahb")
            self.intf = AHBPipelineMasterDX(
                self.ahb_bus, getattr(dut, "clk"), getattr(dut, "rst")
            )

            # self.intf = AHBMaster(ahb_bus, getattr(dut, "clk"), getattr(dut, "rst"))
        elif hasattr(dut, "s_axil_awvalid"):
            from interfaces.axi_wrapper import AxiWrapper

            self.intf = AxiWrapper(dut, "s_axil", "clk", "rst")
        elif hasattr(dut, "s_obi_req"):
            from cocotbext.obi import ObiBus, ObiMaster

            self.obi_bus = ObiBus.from_prefix(dut, "s_obi")
            self.intf = ObiMaster(self.obi_bus, getattr(dut, "clk"))
        elif hasattr(dut, "avalon_read"):
            from cocotbext.avalon import AvalonBus, AvalonMaster

            self.avalon_bus = AvalonBus.from_prefix(dut, "avalon")
            self.intf = AvalonMaster(self.avalon_bus, getattr(dut, "clk"))
        else:
            raise Exception("Unsupported interface")

        for attr in dir(dut):
            if attr.startswith("hwif_"):
                sig = getattr(dut, attr)
                setattr(self, attr, sig)
                # Only initialize inputs, not outputs
                if attr.startswith("hwif_in_"):
                    sig.value = 0
