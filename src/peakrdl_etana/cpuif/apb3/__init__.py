from ..base import CpuifBase
from ...utils import clog2


class APB3_Cpuif_flattened(CpuifBase):

    template_path = "apb3_tmpl.sv"
    supports_early_req = True

    @property
    def port_declaration(self) -> str:
        lines = [
            "input wire " + self.signal("psel"),
            "input wire " + self.signal("penable"),
            "input wire " + self.signal("pwrite"),
            f"input wire [{self.addr_width-1}:0] " + self.signal("paddr"),
            f"input wire [{self.data_width-1}:0] " + self.signal("pwdata"),
            "output logic " + self.signal("pready"),
            f"output logic [{self.data_width-1}:0] " + self.signal("prdata"),
            "output logic " + self.signal("pslverr"),
        ]
        return ",\n".join(lines)

    def signal(self, name: str) -> str:
        return "s_apb_" + name

    @property
    def early_req_expr(self) -> str:
        return f"{self.signal('psel')} & ~is_active"

    @property
    def early_req_is_wr_expr(self) -> str:
        return self.signal("pwrite")

    @property
    def early_addr_expr(self) -> str:
        if self.data_width_bytes == 1:
            return f"{self.signal('paddr')}[{self.addr_width-1}:0]"
        return (
            f"{{{self.signal('paddr')}[{self.addr_width-1}:"
            f"{clog2(self.data_width_bytes)}], "
            f"{clog2(self.data_width_bytes)}'b0}}"
        )
