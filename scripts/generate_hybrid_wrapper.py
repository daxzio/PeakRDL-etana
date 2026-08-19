#!/usr/bin/env python3
"""
Generate a drop-in hybrid top module for PeakRDL-regblock + sv2v output.

The hybrid flow produces:
  - <core>_pkg.sv / <core>.sv from peakrdl regblock
  - <core>.v from sv2v (flat hwif_in/hwif_out vectors)
  - <top>.sv from this script (etana-style flat ports via --in-str / --out-str)

Port names follow etana conventions (IndexedPath redundancy, external-reg rules, etc.)
derived from the regblock hwif report. No etana RTL input is required.

Usage:
    python3 generate_hybrid_wrapper.py regblock.rdl -o hybrid-rtl/ \\
        --cpuif apb4-flat --rename regblock_sub --top-name regblock
"""

from __future__ import annotations

import argparse
import os
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
tool_dir = os.path.join(script_dir, "hwif_wrapper_tool")
sys.path.insert(0, tool_dir)

from hwif_wrapper_tool.hybrid_builder import HybridBuilder  # noqa: E402
from hwif_wrapper_tool.parser import parse_hwif_report, HwifSignal  # noqa: E402
from hwif_wrapper_tool.etana_naming import (  # noqa: E402
    etana_port_name,
    external_reg_data_aliases,
    rdl_path_to_struct_path,
)
from hwif_wrapper_tool.etana_sv_parser import (  # noqa: E402
    parse_etana_hwif_csv,
    parse_etana_module_ports,
)


def _register_cpuif(
    cpuif_map: dict, module_name: str, class_name: str, key: str
) -> None:
    try:
        module = __import__(
            f"peakrdl_regblock.cpuif.{module_name}", fromlist=[class_name]
        )
        if hasattr(module, class_name):
            cpuif_map[key] = getattr(module, class_name)
    except (ImportError, AttributeError):
        pass


def _build_cpuif_map() -> dict:
    cpuif_map: dict = {}
    _register_cpuif(cpuif_map, "passthrough", "PassthroughCpuif", "passthrough")
    _register_cpuif(cpuif_map, "apb3", "APB3_Cpuif", "apb3")
    _register_cpuif(cpuif_map, "apb3", "APB3_Cpuif_flattened", "apb3-flat")
    _register_cpuif(cpuif_map, "apb4", "APB4_Cpuif", "apb4")
    _register_cpuif(cpuif_map, "apb4", "APB4_Cpuif_flattened", "apb4-flat")
    _register_cpuif(cpuif_map, "axi4lite", "AXI4Lite_Cpuif", "axi4-lite")
    _register_cpuif(cpuif_map, "axi4lite", "AXI4Lite_Cpuif_flattened", "axi4-lite-flat")
    _register_cpuif(cpuif_map, "avalon", "Avalon_Cpuif", "avalon-mm")
    _register_cpuif(cpuif_map, "avalon", "Avalon_Cpuif_flattened", "avalon-mm-flat")
    _register_cpuif(cpuif_map, "ahb", "AHB_Cpuif", "ahblite")
    _register_cpuif(cpuif_map, "ahb", "AHB_Cpuif_flattened", "ahblite-flat")
    _register_cpuif(cpuif_map, "ahb", "AHBPipeline_Cpuif", "ahb")
    _register_cpuif(cpuif_map, "ahb", "AHBPipeline_Cpuif_flattened", "ahb-flat")
    _register_cpuif(cpuif_map, "obi", "OBI_Cpuif", "obi")
    _register_cpuif(cpuif_map, "obi", "OBI_Cpuif_flattened", "obi-flat")
    _register_cpuif(cpuif_map, "wishbone", "Wishbone_Cpuif", "wishbone")
    _register_cpuif(cpuif_map, "wishbone", "Wishbone_Cpuif_flattened", "wishbone-flat")
    return cpuif_map


def _build_port_signal_map(
    input_signals,
    output_signals,
    in_prefix: str,
    out_prefix: str,
    etana_hwif_csv: str | None = None,
) -> dict:
    """Map etana port names to regblock HwifSignal entries."""
    by_struct = {sig.struct_path: sig for sig in input_signals + output_signals}
    all_struct_paths = list(by_struct.keys())
    by_port_name: dict = {}

    for sig in input_signals + output_signals:
        port_name = etana_port_name(sig.struct_path, in_prefix, out_prefix)
        by_port_name[port_name] = sig
        for alias in external_reg_data_aliases(
            sig.struct_path, in_prefix, out_prefix, all_struct_paths
        ):
            by_port_name.setdefault(alias, sig)

    if etana_hwif_csv and os.path.exists(etana_hwif_csv):
        csv_map = parse_etana_hwif_csv(etana_hwif_csv)
        for port_name, (direction, rdl_path) in csv_map.items():
            struct_path = rdl_path_to_struct_path(rdl_path, direction)
            if struct_path and struct_path in by_struct:
                by_port_name[port_name] = by_struct[struct_path]

    return by_port_name


def _match_etana_ports(
    etana_hwif_ports,
    port_signal_map: dict,
) -> dict:
    """Verify every etana hwif port maps to a regblock struct path."""
    matched: dict = {}
    missing = []
    for port in etana_hwif_ports:
        if port.name not in port_signal_map:
            missing.append(port.name)
        else:
            matched[port.name] = port_signal_map[port.name]

    if missing:
        raise ValueError(
            "Etana hwif ports without regblock struct mapping: "
            + ", ".join(sorted(missing))
        )
    return matched


def _apply_canonical_port_names(
    input_signals,
    output_signals,
    in_prefix: str,
    out_prefix: str,
    etana_hwif_csv: str | None = None,
) -> dict[str, HwifSignal]:
    """
    Select etana-style hwif ports from the regblock hwif report.

    Returns mapping of full port name -> HwifSignal (one port per etana connection).
    """
    by_struct = {
        sig.struct_path: sig
        for sig in input_signals + output_signals
        if "_reserved_" not in sig.struct_path
    }
    all_struct_paths = list(by_struct.keys())
    struct_to_port: dict[str, str] = {}

    for struct_path, sig in by_struct.items():
        aliases = external_reg_data_aliases(
            struct_path, in_prefix, out_prefix, all_struct_paths
        )
        struct_to_port[struct_path] = (
            aliases[0]
            if aliases
            else etana_port_name(struct_path, in_prefix, out_prefix)
        )

    if etana_hwif_csv and os.path.exists(etana_hwif_csv):
        for port_name, (direction, rdl_path) in parse_etana_hwif_csv(
            etana_hwif_csv
        ).items():
            struct_path = rdl_path_to_struct_path(rdl_path, direction)
            if struct_path and struct_path in by_struct:
                struct_to_port[struct_path] = port_name

    port_to_sig: dict[str, HwifSignal] = {}
    for struct_path, port_name in struct_to_port.items():
        sig = by_struct[struct_path]
        prefix = f"{sig.prefix}_"
        sig.port_name = (
            port_name[len(prefix) :] if port_name.startswith(prefix) else port_name
        )
        port_to_sig[port_name] = sig

    return port_to_sig


def generate_hybrid_wrapper(
    output_dir: str,
    core_name: str,
    top_name: str,
    in_prefix: str = "hwif_in",
    out_prefix: str = "hwif_out",
    etana_sv: str | None = None,
    etana_hwif_csv: str | None = None,
) -> str:
    pkg_path = os.path.join(output_dir, f"{core_name}_pkg.sv")
    core_sv_path = os.path.join(output_dir, f"{core_name}.sv")
    core_v_path = os.path.join(output_dir, f"{core_name}.v")
    report_path = os.path.join(output_dir, f"{core_name}_hwif.rpt")

    for path in (pkg_path, core_sv_path, core_v_path):
        if not os.path.exists(path):
            raise FileNotFoundError(f"Required input not found: {path}")

    with open(pkg_path, encoding="utf-8") as f:
        pkg_content = f.read()
    with open(core_sv_path, encoding="utf-8") as f:
        core_sv_content = f.read()
    with open(core_v_path, encoding="utf-8") as f:
        core_v_content = f.read()

    input_signals = []
    output_signals = []
    if os.path.exists(report_path):
        input_signals, output_signals = parse_hwif_report(report_path)
        for sig in input_signals:
            sig.prefix = in_prefix
        for sig in output_signals:
            sig.prefix = out_prefix

    etana_cpu_ports = None
    etana_hwif_ports = None
    port_signal_map = None

    if etana_sv:
        if not os.path.exists(etana_sv):
            raise FileNotFoundError(f"Etana SV file not found: {etana_sv}")
        if etana_hwif_csv is None:
            stem = os.path.splitext(os.path.basename(etana_sv))[0]
            candidate = os.path.join(os.path.dirname(etana_sv), f"{stem}_hwif.csv")
            if os.path.exists(candidate):
                etana_hwif_csv = candidate

        etana_cpu_ports, etana_hwif_ports = parse_etana_module_ports(
            etana_sv, in_prefix=in_prefix, out_prefix=out_prefix, module_name=top_name
        )
        name_map = _build_port_signal_map(
            input_signals,
            output_signals,
            in_prefix,
            out_prefix,
            etana_hwif_csv=etana_hwif_csv,
        )
        port_signal_map = _match_etana_ports(etana_hwif_ports, name_map)
    else:
        port_signal_map = _apply_canonical_port_names(
            input_signals,
            output_signals,
            in_prefix,
            out_prefix,
            etana_hwif_csv=etana_hwif_csv,
        )

    builder = HybridBuilder(
        top_name=top_name,
        core_name=core_name,
        core_sv_content=core_sv_content,
        core_v_content=core_v_content,
        pkg_content=pkg_content,
        input_signals=input_signals,
        output_signals=output_signals,
        in_prefix=in_prefix,
        out_prefix=out_prefix,
        etana_cpu_ports=etana_cpu_ports,
        etana_hwif_ports=etana_hwif_ports,
        port_signal_map=port_signal_map,
    )

    wrapper_content = builder.generate()
    wrapper_path = os.path.join(output_dir, f"{top_name}.sv")
    with open(wrapper_path, "w", encoding="utf-8") as f:
        f.write(wrapper_content)
    return wrapper_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a drop-in hybrid top module that wraps sv2v regblock output "
            "with etana-style flat hwif ports"
        )
    )
    parser.add_argument(
        "rdl_files",
        nargs="*",
        help="Optional RDL files (only needed to regenerate hwif report if missing)",
    )
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="Hybrid output directory containing regblock_sub artifacts",
    )
    parser.add_argument(
        "--cpuif",
        default="apb4-flat",
        help="CPU interface type used for regblock export (default: apb4-flat)",
    )
    parser.add_argument(
        "--rename",
        default="regblock_sub",
        help="Core module name produced by regblock/sv2v (default: regblock_sub)",
    )
    parser.add_argument(
        "--top-name",
        default="regblock",
        help="Drop-in top module name (default: regblock)",
    )
    parser.add_argument(
        "--in-str",
        default="hwif_in",
        help='Prefix for input hwif ports (default: "hwif_in")',
    )
    parser.add_argument(
        "--out-str",
        default="hwif_out",
        help='Prefix for output hwif ports (default: "hwif_out")',
    )
    parser.add_argument(
        "--etana-sv",
        default=None,
        help=(
            "Optional etana top module SV for port-declaration copy/validation "
            "(not required; naming is derived from the regblock hwif report)"
        ),
    )
    parser.add_argument(
        "--etana-hwif-csv",
        default=None,
        help=(
            "Optional etana hwif CSV for out-of-hierarchy signal port names "
            "(e.g. i_r5_f_next_value); auto-detected next to --etana-sv when set"
        ),
    )
    args = parser.parse_args()

    try:
        os.makedirs(args.output, exist_ok=True)
        report_path = os.path.join(args.output, f"{args.rename}_hwif.rpt")

        if not os.path.exists(report_path) and args.rdl_files:
            from peakrdl_regblock import RegblockExporter
            from peakrdl_regblock.udps import ALL_UDPS
            from systemrdl import RDLCompiler

            cpuif_map = _build_cpuif_map()
            if args.cpuif not in cpuif_map:
                available = ", ".join(sorted(cpuif_map.keys()))
                raise ValueError(
                    f"CPU interface '{args.cpuif}' is not available. "
                    f"Available: {available}"
                )

            rdlc = RDLCompiler()
            for udp in ALL_UDPS:
                rdlc.register_udp(udp)
            for rdl_file in args.rdl_files:
                rdlc.compile_file(rdl_file)
            root = rdlc.elaborate(top_def_name=None, inst_name=args.rename)

            exp = RegblockExporter()
            exp.export(
                root,
                args.output,
                cpuif_cls=cpuif_map[args.cpuif],
                generate_hwif_report=True,
            )

        wrapper_path = generate_hybrid_wrapper(
            output_dir=args.output,
            core_name=args.rename,
            top_name=args.top_name,
            in_prefix=args.in_str,
            out_prefix=args.out_str,
            etana_sv=args.etana_sv,
            etana_hwif_csv=args.etana_hwif_csv,
        )
        print(f"Generated hybrid top: {wrapper_path}")
        print("\n✅ Hybrid wrapper generation complete!")

    except Exception as exc:
        print(f"\n❌ Error: {exc}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
