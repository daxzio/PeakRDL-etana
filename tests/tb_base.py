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
        #             self.intf.intra_delay = 1
        elif hasattr(dut, "s_ahb_hsel"):
            from cocotbext.ahb import AHBBus

            # from cocotbext.ahb import AHBMaster
            from interfaces.ahb_wrapper import AHBMasterDX

            self.ahb_bus = AHBBus.from_prefix(dut, "s_ahb")
            self.intf = AHBMasterDX(
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
                    # Try to initialize as an unpacked array first
                    # Unpacked arrays need element-by-element initialization
                    initialized = False

                    # Method 1: Check if len() works and it's > 1 (arrays typically have multiple elements)
                    try:
                        array_len = len(sig)
                        if array_len > 1:
                            # Try to initialize as array
                            try:
                                # Test if indexing works
                                _ = sig[0]
                                # Initialize all elements
                                for i in range(array_len):
                                    try:
                                        sig[i].value = 0
                                    except Exception:
                                        pass
                                initialized = True
                            except (TypeError, IndexError, AttributeError):
                                # len() worked but indexing failed - might be a special type
                                pass
                    except (TypeError, AttributeError):
                        pass

                    # Method 2: If array initialization didn't work, try scalar
                    if not initialized:
                        try:
                            sig.value = 0
                        except Exception:
                            # Skip if we can't initialize
                            pass
