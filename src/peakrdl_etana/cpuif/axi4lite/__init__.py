from ..base import CpuifBase


class AXI4Lite_Cpuif_flattened(CpuifBase):

    template_path = "axi4lite_tmpl.sv"

    @property
    def port_declaration(self) -> str:
        lines = [
            self._decl("output reg", 1, self.signal("awready")),
            self._decl("input wire", 1, self.signal("awvalid")),
            self._decl("input wire", self.addr_width, self.signal("awaddr")),
            self._decl("input wire", 3, self.signal("awprot")),
            self._decl("output reg", 1, self.signal("wready")),
            self._decl("input wire", 1, self.signal("wvalid")),
            self._decl("input wire", self.data_width, self.signal("wdata")),
            self._decl("input wire", self.data_width_bytes, self.signal("wstrb")),
            self._decl("input wire", 1, self.signal("bready")),
            self._decl("output reg", 1, self.signal("bvalid")),
            self._decl("output reg", 2, self.signal("bresp")),
            self._decl("output reg", 1, self.signal("arready")),
            self._decl("input wire", 1, self.signal("arvalid")),
            self._decl("input wire", self.addr_width, self.signal("araddr")),
            self._decl("input wire", 3, self.signal("arprot")),
            self._decl("input wire", 1, self.signal("rready")),
            self._decl("output reg", 1, self.signal("rvalid")),
            self._decl("output reg", self.data_width, self.signal("rdata")),
            self._decl("output reg", 2, self.signal("rresp")),
        ]
        return ",\n".join(lines)

    def signal(self, name: str) -> str:
        return "s_axil_" + name

    @property
    def regblock_latency(self) -> int:
        return max(self.exp.ds.min_read_latency, self.exp.ds.min_write_latency)

    @property
    def max_outstanding(self) -> int:
        """
        Best pipelined performance is when the max outstanding transactions
        is the design's latency + 2.
        Anything beyond that does not have any effect, aside from adding unnecessary
        logic and additional buffer-bloat latency.
        """
        return self.regblock_latency + 2

    @property
    def resp_buffer_size(self) -> int:
        """
        Response buffer size must be greater or equal to max outstanding
        transactions to prevent response overrun.
        """
        return self.max_outstanding
