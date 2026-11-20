from __future__ import annotations

import os
import shutil
from typing import TYPE_CHECKING

from .cells import cell_filenames
from .generator import CdcImplementationGenerator

if TYPE_CHECKING:
    from ..exporter import RegblockExporter

CDC_CELL_DIR = os.path.dirname(os.path.abspath(__file__))
CDC_CELL_FILES = tuple(
    f"etana_cdc{kind}_{style}.sv"
    for style in ("rst", "rst_n", "arst", "arst_n")
    for kind in ("", "_sync")
)


class Cdc:
    def __init__(self, exp: RegblockExporter) -> None:
        self.exp = exp
        self._gen = CdcImplementationGenerator(exp)

    def get_implementation(self) -> str:
        return self._gen.get_implementation()

    def write_support_files(self, output_dir: str) -> None:
        if not (self.exp.ds.has_cdc_regs and self.exp.ds.cdc_emit_cells):
            return
        reset_name = self.exp.dereferencer.default_resetsignal_name
        for name in cell_filenames(reset_name):
            shutil.copyfile(
                os.path.join(CDC_CELL_DIR, name), os.path.join(output_dir, name)
            )
