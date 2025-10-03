"""
Command Line Interface for HWIF Wrapper Generator
"""
import argparse
import sys
from .generator import generate_wrapper


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Generate SystemVerilog wrapper that flattens hwif structs"
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
            "axi4-lite",
            "axi4-lite-flat",
            "avalon-mm",
            "avalon-mm-flat",
        ],
        help="CPU interface type (default: apb3)",
    )

    parser.add_argument("--module-name", help="Override module name")

    parser.add_argument("--package-name", help="Override package name")

    parser.add_argument(
        "--type-style",
        choices=["lexical", "hier"],
        default="lexical",
        help="HWIF struct type name style (default: lexical)",
    )

    args = parser.parse_args()

    try:
        generate_wrapper(
            rdl_files=args.rdl_files,
            output_dir=args.output,
            cpuif=args.cpuif,
            module_name=args.module_name,
            package_name=args.package_name,
            reuse_hwif_typedefs=(args.type_style == "lexical"),
        )
        print("\n✅ Wrapper generation complete!")
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
