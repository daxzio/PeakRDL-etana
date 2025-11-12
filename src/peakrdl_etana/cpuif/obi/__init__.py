from typing import List

from ..base import CpuifBase


class OBI_Cpuif_flattened(CpuifBase):
    template_path = "obi_tmpl.sv"

    @property
    def port_declaration(self) -> str:
        lines = [
            # OBI Request Channel (A)
            self._decl("input wire", 1, self.signal("req")),
            self._decl("output wire", 1, self.signal("gnt")),
            self._decl("input wire", self.addr_width, self.signal("addr")),
            self._decl("input wire", 1, self.signal("we")),
            self._decl("input wire", self.data_width // 8, self.signal("be")),
            self._decl("input wire", self.data_width, self.signal("wdata")),
            "input wire [ID_WIDTH-1:0] " + self.signal("aid"),
            # OBI Response Channel (R)
            self._decl("output wire", 1, self.signal("rvalid")),
            self._decl("input wire", 1, self.signal("rready")),
            self._decl("output wire", self.data_width, self.signal("rdata")),
            self._decl("output wire", 1, self.signal("err")),
            "output wire [ID_WIDTH-1:0] " + self.signal("rid"),
        ]
        return ",\n".join(lines)

    def signal(self, name: str) -> str:
        return "s_obi_" + name

    @property
    def parameters(self) -> List[str]:
        return ["parameter ID_WIDTH = 1"]

    @property
    def regblock_latency(self) -> int:
        return max(self.exp.ds.min_read_latency, self.exp.ds.min_write_latency)

    @property
    def max_outstanding(self) -> int:
        """
        OBI supports multiple outstanding transactions.
        Best performance when max outstanding is design latency + 1.
        """
        return self.regblock_latency + 1
