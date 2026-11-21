from __future__ import annotations

from typing import TYPE_CHECKING

from .generator import CdcImplementationGenerator

if TYPE_CHECKING:
    from ..exporter import RegblockExporter


class Cdc:
    def __init__(self, exp: RegblockExporter) -> None:
        self.exp = exp
        self._gen = CdcImplementationGenerator(exp)

    def get_implementation(self) -> str:
        return self._gen.get_implementation()
