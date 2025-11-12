from ..base import CpuifBase


class APB3_Cpuif_flattened(CpuifBase):

    template_path = "apb3_tmpl.sv"

    @property
    def port_declaration(self) -> str:
        lines = [
            self._decl("input wire", 1, self.signal("psel")),
            self._decl("input wire", 1, self.signal("penable")),
            self._decl("input wire", 1, self.signal("pwrite")),
            self._decl("input wire", self.addr_width, self.signal("paddr")),
            self._decl("input wire", self.data_width, self.signal("pwdata")),
            self._decl("output wire", 1, self.signal("pready")),
            self._decl("output wire", self.data_width, self.signal("prdata")),
            self._decl("output wire", 1, self.signal("pslverr")),
        ]
        return ",\n".join(lines)

    def signal(self, name: str) -> str:
        return "s_apb_" + name
