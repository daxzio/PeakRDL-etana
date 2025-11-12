from ..base import CpuifBase
from ...utils import clog2


class Avalon_Cpuif_flattened(CpuifBase):
    template_path = "avalon_tmpl.sv"

    @property
    def port_declaration(self) -> str:
        lines = [
            self._decl("input wire", 1, self.signal("read")),
            self._decl("input wire", 1, self.signal("write")),
            self._decl("output reg", 1, self.signal("waitrequest")),
            self._decl("input wire", self.word_addr_width, self.signal("address")),
            self._decl("input wire", self.data_width, self.signal("writedata")),
            self._decl("input wire", self.data_width_bytes, self.signal("byteenable")),
            self._decl("output reg", 1, self.signal("readdatavalid")),
            self._decl("output reg", 1, self.signal("writeresponsevalid")),
            self._decl("output reg", self.data_width, self.signal("readdata")),
            self._decl("output reg", 2, self.signal("response")),
        ]
        return ",\n".join(lines)

    def signal(self, name: str) -> str:
        return "avalon_" + name

    @property
    def word_addr_width(self) -> int:
        # Avalon agents use word addressing, therefore address width is reduced
        return self.addr_width - clog2(self.data_width_bytes)
