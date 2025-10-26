#!/usr/bin/env python3
"""
Standalone HWIF Wrapper Generator Script

Usage:
    python3 generate_wrapper.py design.rdl -o output/ [options]

No installation required - just run this script directly!
Requires: peakrdl-regblock to be installed
"""

import sys
import os
import argparse
import tempfile

# Add the package directory to Python path so we can import modules
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

# Import our modules
from hwif_wrapper_tool.parser import parse_hwif_report  # noqa: E402
from hwif_wrapper_tool.wrapper_builder import WrapperBuilder  # noqa: E402


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Generate SystemVerilog wrapper that flattens hwif structs"
    )

    parser.add_argument("rdl_files", nargs="+", help="One or more RDL files to compile")

    parser.add_argument(
        "-o", "--output", required=True, help="Output directory for generated files"
    )

    # Note: choices will be dynamically set based on available interfaces
    parser.add_argument(
        "--cpuif",
        default="apb3",
        help="CPU interface type (default: apb3). Available choices depend on peakrdl-regblock version.",
    )

    parser.add_argument("--module-name", help="Override module name")

    parser.add_argument("--package-name", help="Override package name")

    parser.add_argument(
        "--type-style",
        choices=["lexical", "hier"],
        default="lexical",
        help="HWIF struct type name style (default: lexical)",
    )

    parser.add_argument(
        "--rename", help="Override the top-component's instantiated name"
    )

    args = parser.parse_args()

    try:
        # Import here to avoid issues if not installed
        from systemrdl import RDLCompiler
        from peakrdl_regblock import RegblockExporter
        from peakrdl_regblock.udps import ALL_UDPS
        from peakrdl_regblock.identifier_filter import kw_filter as kwf

        # Dynamically build CPU interface map based on what's available
        # This ensures compatibility with different peakrdl-regblock versions
        cpuif_map = {}

        # Helper function to safely import and register interface
        def register_interface(module_name, class_name, key):
            try:
                module = __import__(
                    f"peakrdl_regblock.cpuif.{module_name}", fromlist=[class_name]
                )
                if hasattr(module, class_name):
                    cpuif_map[key] = getattr(module, class_name)
                    return True
            except (ImportError, AttributeError):
                pass
            return False

        # Register all known interfaces (gracefully skip if not available)
        register_interface("passthrough", "PassthroughCpuif", "passthrough")
        register_interface("apb3", "APB3_Cpuif", "apb3")
        register_interface("apb3", "APB3_Cpuif_flattened", "apb3-flat")
        register_interface("apb4", "APB4_Cpuif", "apb4")
        register_interface("apb4", "APB4_Cpuif_flattened", "apb4-flat")
        register_interface("axi4lite", "AXI4Lite_Cpuif", "axi4-lite")
        register_interface("axi4lite", "AXI4Lite_Cpuif_flattened", "axi4-lite-flat")
        register_interface("avalon", "Avalon_Cpuif", "avalon-mm")
        register_interface("avalon", "Avalon_Cpuif_flattened", "avalon-mm-flat")
        register_interface("ahb", "AHB_Cpuif", "ahb")
        register_interface("ahb", "AHB_Cpuif_flattened", "ahb-flat")
        register_interface("obi", "OBI_Cpuif", "obi")
        register_interface("obi", "OBI_Cpuif_flattened", "obi-flat")

        # Ensure at least APB3 is available (should always be present)
        if "apb3" not in cpuif_map:
            raise RuntimeError(
                "peakrdl-regblock installation is missing required APB3 interface"
            )

        # Compile RDL
        rdlc = RDLCompiler()

        # Register PeakRDL-regblock UDPs
        for udp in ALL_UDPS:
            rdlc.register_udp(udp)

        for rdl_file in args.rdl_files:
            rdlc.compile_file(rdl_file)

        # Elaborate with optional rename
        if args.rename:
            root = rdlc.elaborate(top_def_name=None, inst_name=args.rename)
        else:
            root = rdlc.elaborate()

        # Get CPU interface class
        if args.cpuif not in cpuif_map:
            available = ", ".join(sorted(cpuif_map.keys()))
            raise ValueError(
                f"CPU interface '{args.cpuif}' is not available in this peakrdl-regblock version.\n"
                f"Available interfaces: {available}\n"
                f"You may need to upgrade peakrdl-regblock: pip install --upgrade peakrdl-regblock"
            )

        cpuif_cls = cpuif_map[args.cpuif]

        # Create temporary directory for hwif report
        with tempfile.TemporaryDirectory() as temp_dir:
            # Export with hwif report enabled
            exp = RegblockExporter()
            exp.export(
                root,
                temp_dir,
                cpuif_cls=cpuif_cls,
                module_name=args.module_name,
                package_name=args.package_name,
                generate_hwif_report=True,
                reuse_hwif_typedefs=(args.type_style == "lexical"),
            )

            # Get the actual module and package names
            if args.module_name is None:
                actual_module_name = kwf(root.top.inst_name)
            else:
                actual_module_name = args.module_name

            if args.package_name is None:
                actual_package_name = f"{actual_module_name}_pkg"
            else:
                actual_package_name = args.package_name

            # Create output directory
            os.makedirs(args.output, exist_ok=True)

            # Check if hwif report exists
            report_path = os.path.join(temp_dir, f"{actual_module_name}_hwif.rpt")

            if not os.path.exists(report_path):
                # No report means no hwif signals - generate wrapper with empty lists
                input_signals = []
                output_signals = []
            else:
                # Parse hwif report
                input_signals, output_signals = parse_hwif_report(report_path)

            # Note: Generate wrapper even if no hwif signals (empty lists are fine)

            # Read module file from temp directory
            module_path = os.path.join(temp_dir, f"{actual_module_name}.sv")
            with open(module_path, "r", encoding="utf-8") as f:
                module_content = f.read()

            # Build wrapper
            builder = WrapperBuilder(
                module_name=actual_module_name,
                package_name=actual_package_name,
                inst_name=root.top.inst_name,
                module_content=module_content,
                input_signals=input_signals,
                output_signals=output_signals,
            )

            wrapper_content = builder.generate()

            # Write wrapper file
            wrapper_path = os.path.join(args.output, f"{actual_module_name}_wrapper.sv")
            with open(wrapper_path, "w", encoding="utf-8") as f:
                f.write(wrapper_content)

            print(f"Generated wrapper: {args.output}/{actual_module_name}_wrapper.sv")
            print("\n✅ Wrapper generation complete!")

    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
