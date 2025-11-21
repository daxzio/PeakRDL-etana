from typing import TYPE_CHECKING, Dict, Type, List, Any
import functools
import sys

from peakrdl.plugins.exporter import (
    ExporterSubcommandPlugin,
)  # pylint: disable=import-error
from peakrdl.config import schema  # pylint: disable=import-error

from .exporter import RegblockExporter
from .cpuif import CpuifBase, apb3, apb4, axi4lite, passthrough, avalon, ahb, obi
from .udps import ALL_UDPS
from . import entry_points

if TYPE_CHECKING:
    import argparse
    from systemrdl.node import AddrmapNode


class Choice(schema.String):
    """
    Schema that matches against a specific set of allowed strings

    Base PeakRDL does not have this schema yet. Polyfill here for now until it
    is added and widely available.
    """

    def __init__(self, choices: List[str]) -> None:
        super().__init__()
        self.choices = choices

    def extract(self, data: Any, path: str, err_ctx: str) -> Any:
        s = super().extract(data, path, err_ctx)
        if s not in self.choices:
            raise schema.SchemaException(
                f"{err_ctx}: Value '{s}' is not a valid choice. Must be one of: {','.join(self.choices)}"
            )
        return s


class Exporter(ExporterSubcommandPlugin):
    short_desc = "Generate a SystemVerilog control/status register (CSR) block"

    udp_definitions = ALL_UDPS

    cfg_schema = {
        "cpuifs": {"*": schema.PythonObjectImport()},
        "default_reset": Choice(["rst", "rst_n", "arst", "arst_n"]),
    }

    @functools.lru_cache()
    def get_cpuifs(self) -> Dict[str, Type[CpuifBase]]:

        # All built-in CPUIFs - FLATTENED SIGNALS ONLY (no SystemVerilog structs)
        cpuifs = {
            "passthrough": passthrough.PassthroughCpuif,
            "apb3-flat": apb3.APB3_Cpuif_flattened,
            "apb4-flat": apb4.APB4_Cpuif_flattened,
            "ahb-flat": ahb.AHB_Cpuif_flattened,
            "axi4-lite-flat": axi4lite.AXI4Lite_Cpuif_flattened,
            "avalon-mm-flat": avalon.Avalon_Cpuif_flattened,
            "obi-flat": obi.OBI_Cpuif_flattened,
        }

        # Load any cpuifs specified via entry points
        for ep, dist in entry_points.get_entry_points("peakrdl_regblock.cpuif"):
            name = ep.name
            cpuif = ep.load()
            if name in cpuifs:
                raise RuntimeError(
                    f"A plugin for 'peakrdl-regblock' tried to load cpuif '{name}' but it already exists"
                )
            if not issubclass(cpuif, CpuifBase):
                raise RuntimeError(
                    f"A plugin for 'peakrdl-regblock' tried to load cpuif '{name}' but it not a CpuifBase class"
                )
            cpuifs[name] = cpuif

        # Load any CPUIFs via config import
        for name, cpuif in self.cfg["cpuifs"].items():
            if name in cpuifs:
                raise RuntimeError(
                    f"A plugin for 'peakrdl-regblock' tried to load cpuif '{name}' but it already exists"
                )
            if not issubclass(cpuif, CpuifBase):
                raise RuntimeError(
                    f"A plugin for 'peakrdl-regblock' tried to load cpuif '{name}' but it not a CpuifBase class"
                )
            cpuifs[name] = cpuif

        return cpuifs

    def add_exporter_arguments(self, arg_group: "argparse._ActionsContainer") -> None:
        cpuifs = self.get_cpuifs()

        arg_group.add_argument(
            "--cpuif",
            choices=cpuifs.keys(),
            default="apb4-flat",
            help="Select the CPU interface protocol to use (flattened signals only) [apb4-flat]",
        )

        arg_group.add_argument(
            "--module-name",
            metavar="NAME",
            default=None,
            help="Override the SystemVerilog module name",
        )

        arg_group.add_argument(
            "--package-name",
            metavar="NAME",
            default=None,
            help="Override the SystemVerilog package name",
        )

        arg_group.add_argument(
            "--type-style",
            dest="type_style",
            choices=["lexical", "hier"],
            default="lexical",
            help="""Choose how flattened signal names are generated.

        This fork uses flattened signals instead of SystemVerilog structs.
            The 'lexical' style will attempt to re-use signal definitions for
            equivalent hierarchical content where possible.
            The 'hier' style will generate signals using their full hierarchical paths. [lexical]
            """,
        )

        arg_group.add_argument(
            "--hwif-report",
            action="store_true",
            default=False,
            help="Generate a HWIF report file",
        )

        arg_group.add_argument(
            "--addr-width",
            type=int,
            default=None,
            help="""Override the CPU interface's address width. By default,
            address width is sized to the contents of the regblock.
            """,
        )

        arg_group.add_argument(
            "--rt-read-fanin",
            action="store_true",
            default=False,
            help="Enable additional read path retiming. Good for register blocks with large readback fan-in",
        )
        arg_group.add_argument(
            "--rt-read-response",
            action="store_true",
            default=False,
            help="Enable additional retiming stage between readback fan-in and cpu interface",
        )
        arg_group.add_argument(
            "--rt-external",
            help="Retime outputs to external components. Specify a comma-separated list of: reg,regfile,mem,addrmap,all",
        )

        arg_group.add_argument(
            "--default-reset",
            choices=["rst", "rst_n", "arst", "arst_n"],
            default=None,
            help="""Choose the default style of reset signal if not explicitly
            specified by the SystemRDL design. If unspecified, the default reset
            is active-high and synchronous [rst]""",
        )
        arg_group.add_argument(
            "--in-str",
            type=str,
            default="hwif_in",
            help="""Head of input port name, default \"hwif_in\"""",
        )
        arg_group.add_argument(
            "--out-str",
            type=str,
            default="hwif_out",
            help="""Head of output port name, default \"hwif_out\"""",
        )

        arg_group.add_argument(
            "--allow-wide-field-subwords",
            action="store_true",
            default=False,
            help="""Allow software-writable fields to span multiple subwords without write buffering.
            This bypasses SystemRDL specification rule 10.6.1-f and enables non-atomic writes to wide registers.""",
        )

        arg_group.add_argument(
            "--flatten-nested-blocks",
            action="store_true",
            default=False,
            help="""Flatten nested regfile and addrmap components into the parent address space
            instead of treating them as external interfaces. Memory (mem) blocks are always external
            per SystemRDL specification. Useful for simpler integration and better tool compatibility.""",
        )

        arg_group.add_argument(
            "--generate-template",
            action="store_true",
            default=False,
            help="""Generate an example template module showing how to instantiate the register block.
            The template includes APB interface at top-level and hardware interface signals declared
            internally with w_ prefix. Output file: {module_name}_example.sv""",
        )

        arg_group.add_argument(
            "--err-if-bad-addr",
            action="store_true",
            default=False,
            help="""Generate error responses for accesses to unmapped addresses""",
        )

        arg_group.add_argument(
            "--err-if-bad-rw",
            action="store_true",
            default=False,
            help="""Generate error responses for reads to write-only registers or writes to read-only registers""",
        )

    def do_export(self, top_node: "AddrmapNode", options: "argparse.Namespace") -> None:
        cpuifs = self.get_cpuifs()

        retime_external_reg = False
        retime_external_regfile = False
        retime_external_mem = False
        retime_external_addrmap = False
        if options.rt_external:
            for key in options.rt_external.split(","):
                key = key.strip().lower()
                if key == "reg":
                    retime_external_reg = True
                elif key == "regfile":
                    retime_external_regfile = True
                elif key == "mem":
                    retime_external_mem = True
                elif key == "addrmap":
                    retime_external_addrmap = True
                elif key == "all":
                    retime_external_reg = True
                    retime_external_regfile = True
                    retime_external_mem = True
                    retime_external_addrmap = True
                else:
                    print(
                        "error: invalid option for --rt-external: '%s'" % key,
                        file=sys.stderr,
                    )

        # Get default reset. Favor command-line over cfg. Fall back to 'rst'
        default_rst = options.default_reset or self.cfg["default_reset"] or "rst"
        if default_rst == "rst":
            default_reset_activelow = False
            default_reset_async = False
        elif default_rst == "rst_n":
            default_reset_activelow = True
            default_reset_async = False
        elif default_rst == "arst":
            default_reset_activelow = False
            default_reset_async = True
        elif default_rst == "arst_n":
            default_reset_activelow = True
            default_reset_async = True
        else:
            raise RuntimeError

        x = RegblockExporter()
        x.export(
            top_node,
            options.output,
            cpuif_cls=cpuifs[options.cpuif],
            module_name=options.module_name,
            package_name=options.package_name,
            reuse_hwif_typedefs=(options.type_style == "lexical"),
            retime_read_fanin=options.rt_read_fanin,
            retime_read_response=options.rt_read_response,
            retime_external_reg=retime_external_reg,
            retime_external_regfile=retime_external_regfile,
            retime_external_mem=retime_external_mem,
            retime_external_addrmap=retime_external_addrmap,
            generate_hwif_report=options.hwif_report,
            address_width=options.addr_width,
            default_reset_activelow=default_reset_activelow,
            default_reset_async=default_reset_async,
            in_str=options.in_str,
            out_str=options.out_str,
            allow_wide_field_subwords=options.allow_wide_field_subwords,
            flatten_nested_blocks=options.flatten_nested_blocks,
            generate_template=options.generate_template,
            err_if_bad_addr=options.err_if_bad_addr,
            err_if_bad_rw=options.err_if_bad_rw,
        )
