from ..base import CpuifBase


class AHBPipline_Cpuif_flattened(CpuifBase):
    template_path = "ahbpipline_tmpl.sv"

    @property
    def port_declaration(self) -> str:
        lines = [
            self._decl("input wire", 1, self.signal("hsel")),
            self._decl("input wire", 1, self.signal("hwrite")),
            self._decl("input wire", 2, self.signal("htrans")),
            self._decl("input wire", 3, self.signal("hsize")),
            self._decl("input wire", self.addr_width, self.signal("haddr")),
            self._decl("input wire", self.data_width, self.signal("hwdata")),
            self._decl("output wire", 1, self.signal("hready")),
            self._decl("output wire", self.data_width, self.signal("hrdata")),
            self._decl("output wire", 1, self.signal("hresp")),
        ]
        return ",\n".join(lines)

    def signal(self, name: str) -> str:
        return "s_ahb_" + name
