from ..base import CpuifBase


class Wishbone_Cpuif_flattened(CpuifBase):
    """
    Wishbone B4 (Classic) slave interface with flattened signals.
    Single-cycle, non-pipelined. Supports optional ERR_O for error reporting.
    """

    template_path = "wishbone_tmpl.sv"

    @property
    def port_declaration(self) -> str:
        lines = [
            "input wire " + self.signal("cyc"),
            "input wire " + self.signal("stb"),
            "input wire " + self.signal("we"),
            f"input wire [{self.addr_width-1}:0] " + self.signal("adr"),
            f"input wire [{self.data_width-1}:0] " + self.signal("dat_wr"),
            f"input wire [{self.data_width_bytes-1}:0] " + self.signal("sel"),
            "output logic " + self.signal("ack"),
            "output logic " + self.signal("err"),
            f"output logic [{self.data_width-1}:0] " + self.signal("dat_rd"),
        ]
        return ",\n".join(lines)

    def signal(self, name: str) -> str:
        return "s_wb_" + name
