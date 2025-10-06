"""
Main Wrapper Generator
"""
import os
import tempfile
from typing import Optional
from systemrdl import RDLCompiler
from peakrdl_regblock import RegblockExporter
from .parser import parse_hwif_report
from .wrapper_builder import WrapperBuilder


def generate_wrapper(
    rdl_files: list,
    output_dir: str,
    cpuif: str = "apb3",
    module_name: Optional[str] = None,
    package_name: Optional[str] = None,
    **export_kwargs,
) -> None:
    """
    Generate regblock with hwif wrapper

    Parameters:
        rdl_files: List of RDL files to compile
        output_dir: Output directory for generated files
        cpuif: CPU interface type (default: "apb3")
        module_name: Override module name
        package_name: Override package name
        **export_kwargs: Additional kwargs to pass to RegblockExporter.export()
    """
    # Compile RDL
    rdlc = RDLCompiler()

    # Register PeakRDL-regblock UDPs
    from peakrdl_regblock.udps import ALL_UDPS

    for udp in ALL_UDPS:
        rdlc.register_udp(udp)

    for rdl_file in rdl_files:
        rdlc.compile_file(rdl_file)

    root = rdlc.elaborate()

    # Import CPU interface class
    from peakrdl_regblock.cpuif import apb3, apb4, axi4lite, passthrough, avalon

    cpuif_map = {
        "passthrough": passthrough.PassthroughCpuif,
        "apb3": apb3.APB3_Cpuif,
        "apb3-flat": apb3.APB3_Cpuif_flattened,
        "apb4": apb4.APB4_Cpuif,
        "apb4-flat": apb4.APB4_Cpuif_flattened,
        "axi4-lite": axi4lite.AXI4Lite_Cpuif,
        "axi4-lite-flat": axi4lite.AXI4Lite_Cpuif_flattened,
        "avalon-mm": avalon.Avalon_Cpuif,
        "avalon-mm-flat": avalon.Avalon_Cpuif_flattened,
    }

    cpuif_cls = cpuif_map.get(cpuif, apb4.APB4_Cpuif)

    # Create temporary directory for hwif report
    with tempfile.TemporaryDirectory() as temp_dir:
        # Export with hwif report enabled
        exp = RegblockExporter()
        exp.export(
            root,
            temp_dir,
            cpuif_cls=cpuif_cls,
            module_name=module_name,
            package_name=package_name,
            generate_hwif_report=True,
            **export_kwargs,
        )

        # Get the actual module and package names
        if module_name is None:
            from peakrdl_regblock.identifier_filter import kw_filter as kwf

            actual_module_name = kwf(root.top.inst_name)
        else:
            actual_module_name = module_name

        if package_name is None:
            actual_package_name = f"{actual_module_name}_pkg"
        else:
            actual_package_name = package_name

        # Copy base files to output
        import shutil

        os.makedirs(output_dir, exist_ok=True)

        shutil.copy2(
            os.path.join(temp_dir, f"{actual_package_name}.sv"),
            os.path.join(output_dir, f"{actual_package_name}.sv"),
        )
        shutil.copy2(
            os.path.join(temp_dir, f"{actual_module_name}.sv"),
            os.path.join(output_dir, f"{actual_module_name}.sv"),
        )

        # Check if hwif report exists
        report_path = os.path.join(temp_dir, f"{actual_module_name}_hwif.rpt")

        if not os.path.exists(report_path):
            print("No hwif report generated - design may not have hwif structs")
            return

        # Parse hwif report
        input_signals, output_signals = parse_hwif_report(report_path)

        if not input_signals and not output_signals:
            print("No hwif signals found - skipping wrapper generation")
            return

        # Read module file to extract info
        module_path = os.path.join(output_dir, f"{actual_module_name}.sv")
        with open(module_path, "r", encoding="utf-8") as f:
            module_content = f.read()

        # Build and write wrapper
        builder = WrapperBuilder(
            module_name=actual_module_name,
            package_name=actual_package_name,
            inst_name=root.top.inst_name,
            module_content=module_content,
            input_signals=input_signals,
            output_signals=output_signals,
        )

        wrapper_content = builder.generate()

        wrapper_path = os.path.join(output_dir, f"{actual_module_name}_wrapper.sv")
        with open(wrapper_path, "w", encoding="utf-8") as f:
            f.write(wrapper_content)

        print(f"Generated files in {output_dir}:")
        print(f"  - {actual_package_name}.sv")
        print(f"  - {actual_module_name}.sv")
        print(f"  - {actual_module_name}_wrapper.sv")
