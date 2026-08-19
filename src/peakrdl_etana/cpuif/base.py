from typing import TYPE_CHECKING, List
import inspect
import os

import jinja2 as jj

from ..utils import clog2, is_pow2, roundup_pow2

if TYPE_CHECKING:
    from ..exporter import RegblockExporter


class CpuifBase:

    # Path is relative to the location of the class that assigns this variable
    template_path = ""

    # When True, the CPUIF exposes a combinational early request channel during
    # the address/SETUP phase (before cpuif_req is registered).
    supports_early_req = False

    def __init__(self, exp: "RegblockExporter"):
        self.exp = exp
        self.reset = exp.ds.top_node.cpuif_reset

    @property
    def addr_width(self) -> int:
        return self.exp.ds.addr_width

    @property
    def data_width(self) -> int:
        return self.exp.ds.cpuif_data_width

    @property
    def data_width_bytes(self) -> int:
        return self.data_width // 8

    @property
    def port_declaration(self) -> str:
        raise NotImplementedError()

    @property
    def parameters(self) -> List[str]:
        """
        Optional list of additional parameters this CPU interface provides to
        the module's definition
        """
        return []

    @property
    def early_req_expr(self) -> str:
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support early external read"
        )

    @property
    def early_req_is_wr_expr(self) -> str:
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support early external read"
        )

    @property
    def early_addr_expr(self) -> str:
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support early external read"
        )

    def _get_template_path_class_dir(self) -> str:
        """
        Traverse up the MRO and find the first class that explicitly assigns
        template_path. Returns the directory that contains the class definition.
        """
        for cls in inspect.getmro(self.__class__):
            if "template_path" in cls.__dict__:
                class_dir = os.path.dirname(inspect.getfile(cls))
                return class_dir
        raise RuntimeError

    def get_implementation(self) -> str:
        class_dir = self._get_template_path_class_dir()
        loader = jj.FileSystemLoader(class_dir)
        jj_env = jj.Environment(
            loader=loader,
            undefined=jj.StrictUndefined,
        )

        context = {
            "cpuif": self,
            "ds": self.exp.ds,
            "get_always_ff_event": self.exp.dereferencer.get_always_ff_event,
            "get_resetsignal": self.exp.dereferencer.get_resetsignal,
            "clog2": clog2,
            "is_pow2": is_pow2,
            "roundup_pow2": roundup_pow2,
        }

        template = jj_env.get_template(self.template_path)
        return template.render(context)
