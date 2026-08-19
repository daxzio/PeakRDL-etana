from typing import List

from ..base import CpuifBase
from ...utils import clog2


class OBI_Cpuif_flattened(CpuifBase):
    template_path = "obi_tmpl.sv"
    supports_early_req = True

    @property
    def port_declaration(self) -> str:
        lines = [
            # OBI Request Channel (A)
            "input wire " + self.signal("req"),
            "output logic " + self.signal("gnt"),
            f"input wire [{self.addr_width-1}:0] " + self.signal("addr"),
            "input wire " + self.signal("we"),
            f"input wire [{self.data_width//8-1}:0] " + self.signal("be"),
            f"input wire [{self.data_width-1}:0] " + self.signal("wdata"),
            "input wire [ID_WIDTH-1:0] " + self.signal("aid"),
            # OBI Response Channel (R)
            "output logic " + self.signal("rvalid"),
            "input wire " + self.signal("rready"),
            f"output logic [{self.data_width-1}:0] " + self.signal("rdata"),
            "output logic " + self.signal("err"),
            "output logic [ID_WIDTH-1:0] " + self.signal("rid"),
        ]
        return ",\n".join(lines)

    def signal(self, name: str) -> str:
        return "s_obi_" + name

    @property
    def early_req_expr(self) -> str:
        # Do not use s_obi_gnt or cpuif_rd_ack: both sit on combo paths through
        # decode/hwif ack (Verilator UNOPTFLAT). Overlap the next early read
        # using the registered cpuif_req pulse (same cycle the SRAM rd_ack
        # returns). Write→read turnaround is excluded by the cpuif write pulse.
        req = self.signal("req")
        we = self.signal("we")
        rready = self.signal("rready")
        return (
            f"{req} & ~{we} & ~(cpuif_req & cpuif_req_is_wr) & "
            f"(~exec_valid | (cpuif_req & ~cpuif_req_is_wr) "
            f"| (exec_held & (~rsp_valid | {rready})))"
        )

    @property
    def early_req_is_wr_expr(self) -> str:
        return self.signal("we")

    @property
    def early_addr_expr(self) -> str:
        if self.data_width_bytes == 1:
            return f"{self.signal('addr')}[{self.addr_width-1}:0]"
        return (
            f"{{{self.signal('addr')}[{self.addr_width-1}:"
            f"{clog2(self.data_width_bytes)}], "
            f"{clog2(self.data_width_bytes)}'b0}}"
        )

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
