from ..base import CpuifBase


class AHB_Cpuif_flattened(CpuifBase):
    template_path = "ahb_tmpl.sv"

    @property
    def port_declaration(self) -> str:
        lines = [
            "input wire " + self.signal("psel"),
            "input wire " + self.signal("pwrite"),
            #             "/* verilator lint_off UNUSEDSIGNAL */",
            "input wire " + self.signal("penable"),
            "input wire [2:0] " + self.signal("pprot"),
            #             "/* verilator lint_on UNUSEDSIGNAL */",
            f"input wire [{self.addr_width-1}:0] " + self.signal("paddr"),
            f"input wire [{self.data_width-1}:0] " + self.signal("pwdata"),
            f"input wire [{self.data_width_bytes-1}:0] " + self.signal("pstrb"),
            "output logic " + self.signal("pready"),
            f"output logic [{self.data_width-1}:0] " + self.signal("prdata"),
            "output logic " + self.signal("pslverr"),
        ]
        return ",\n".join(lines)

    def signal(self, name: str) -> str:
        return "s_ahb_" + name
