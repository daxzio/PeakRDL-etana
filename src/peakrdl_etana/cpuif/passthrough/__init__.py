from ..base import CpuifBase


class PassthroughCpuif(CpuifBase):
    template_path = "passthrough_tmpl.sv"

    @property
    def port_declaration(self) -> str:
        lines = [
            self._decl("input wire", 1, "s_cpuif_req"),
            self._decl("input wire", 1, "s_cpuif_req_is_wr"),
            self._decl("input wire", self.addr_width, "s_cpuif_addr"),
            self._decl("input wire", self.data_width, "s_cpuif_wr_data"),
            self._decl("input wire", self.data_width, "s_cpuif_wr_biten"),
            self._decl("output wire", 1, "s_cpuif_req_stall_wr"),
            self._decl("output wire", 1, "s_cpuif_req_stall_rd"),
            self._decl("output wire", 1, "s_cpuif_rd_ack"),
            self._decl("output wire", 1, "s_cpuif_rd_err"),
            self._decl("output wire", self.data_width, "s_cpuif_rd_data"),
            self._decl("output wire", 1, "s_cpuif_wr_ack"),
            self._decl("output wire", 1, "s_cpuif_wr_err"),
        ]
        return ",\n".join(lines)
