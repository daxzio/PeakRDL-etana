from ..base import CpuifBase


class AHB5_Cpuif_flattened(CpuifBase):
    template_path = "ahb5_tmpl.sv"

    @property
    def port_declaration(self) -> str:
        lines = [
            "input wire " + self.signal("hsel"),
            "input wire " + self.signal("hwrite"),
            "input wire [1:0] " + self.signal("htrans"),
            "input wire [2:0] " + self.signal("hsize"),
            "input wire [2:0] " + self.signal("hburst"),
            "input wire [3:0] " + self.signal("hprot"),
            "input wire " + self.signal("hmastlock"),
            "input wire " + self.signal("hnonsec"),
            "input wire " + self.signal("hexcl"),
            "input wire [3:0] " + self.signal("hmaster"),
            f"input wire [{self.addr_width-1}:0] " + self.signal("haddr"),
            f"input wire [{self.data_width-1}:0] " + self.signal("hwdata"),
            "input wire " + self.signal("hready"),
            "output logic " + self.signal("hready_resp"),
            f"output logic [{self.data_width-1}:0] " + self.signal("hrdata"),
            "output logic " + self.signal("hresp"),
            "output logic " + self.signal("hexokay"),
        ]
        return ",\n".join(lines)

    def signal(self, name: str) -> str:
        return "s_ahb_" + name
