#!/usr/bin/env python3
"""
Standalone VHDL HWIF Wrapper Generator Script

Usage:
    python3 generate_wrapper_vhdl.py design.rdl -o output/ [options]

No installation required - just run this script directly!
Requires: peakrdl-regblock-vhdl to be installed
"""

import sys
import os
import argparse
import tempfile

# Add the package directory to Python path so we can import modules
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

# Import our modules
from hwif_wrapper_tool_vhdl.vhdl_parser import parse_vhdl_package  # noqa: E402
from hwif_wrapper_tool_vhdl.vhdl_wrapper_builder import VhdlWrapperBuilder  # noqa: E402


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Generate VHDL wrapper that flattens hwif records"
    )

    parser.add_argument("rdl_files", nargs="+", help="One or more RDL files to compile")

    parser.add_argument(
        "-o", "--output", required=True, help="Output directory for generated files"
    )

    parser.add_argument(
        "--cpuif",
        default="apb3",
        choices=[
            "passthrough",
            "apb3",
            "apb3-flat",
            "apb4",
            "apb4-flat",
        ],
        help="CPU interface type (default: apb3)",
    )

    parser.add_argument("--module-name", help="Override module name")

    parser.add_argument("--package-name", help="Override package name")

    parser.add_argument(
        "--rename", help="Override the top-component's instantiated name"
    )

    args = parser.parse_args()

    try:
        # Import here to avoid issues if not installed
        from systemrdl import RDLCompiler
        from peakrdl_regblock_vhdl import RegblockExporter
        from peakrdl_regblock_vhdl.cpuif import apb3, apb4, passthrough
        from peakrdl_regblock_vhdl.udps import ALL_UDPS
        from peakrdl_regblock_vhdl.identifier_filter import kw_filter as kwf

        # Map CPU interface names to classes
        cpuif_map = {
            "passthrough": passthrough.PassthroughCpuif,
            "apb3": apb3.APB3_Cpuif,
            "apb3-flat": apb3.APB3_Cpuif_flattened,
            "apb4": apb4.APB4_Cpuif,
            "apb4-flat": apb4.APB4_Cpuif_flattened,
        }

        # Compile RDL
        rdlc = RDLCompiler()

        # Register PeakRDL-regblock-vhdl UDPs
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
        cpuif_cls = cpuif_map.get(args.cpuif, apb3.APB3_Cpuif)

        # Create temporary directory for VHDL generation
        with tempfile.TemporaryDirectory() as temp_dir:
            # Export VHDL
            exp = RegblockExporter()
            exp.export(
                root,
                temp_dir,
                cpuif_cls=cpuif_cls,
                module_name=args.module_name,
                package_name=args.package_name,
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

            # Parse the package file
            package_path = os.path.join(temp_dir, f"{actual_package_name}.vhd")

            if not os.path.exists(package_path):
                print(f"❌ Error: Package file not found: {package_path}")
                sys.exit(1)

            parser = parse_vhdl_package(package_path)

            # Find the top-level record types
            in_record_type, out_record_type = parser.get_top_level_records()

            # Check if there are any hwif signals
            if not in_record_type and not out_record_type:
                print("ℹ️  No hwif signals found in design - generating empty wrapper")
                print("   Design has no hardware interface records")
            else:
                print(f"Found hwif records:")
                if in_record_type:
                    print(f"  Input:  {in_record_type}")
                if out_record_type:
                    print(f"  Output: {out_record_type}")

            # Read entity file
            entity_path = os.path.join(temp_dir, f"{actual_module_name}.vhd")
            with open(entity_path, "r", encoding="utf-8") as f:
                entity_content = f.read()

            # Build wrapper
            builder = VhdlWrapperBuilder(
                module_name=actual_module_name,
                package_name=actual_package_name,
                entity_content=entity_content,
                parser=parser,
                in_record_type=in_record_type,
                out_record_type=out_record_type,
            )

            wrapper_content = builder.generate()

            # Write wrapper file
            wrapper_path = os.path.join(
                args.output, f"{actual_module_name}_wrapper.vhd"
            )
            with open(wrapper_path, "w", encoding="utf-8") as f:
                f.write(wrapper_content)

            print(
                f"\n✅ Generated wrapper: {args.output}/{actual_module_name}_wrapper.vhd"
            )
            print(f"   Flattened {len(builder.in_signals)} input signals")
            print(f"   Flattened {len(builder.out_signals)} output signals")

    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
