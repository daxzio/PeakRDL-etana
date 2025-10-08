from typing import TYPE_CHECKING, List

from .bases import NextStateConditional

if TYPE_CHECKING:
    from systemrdl.node import FieldNode
    from ..exporter import RegblockExporter


class WideFieldSubwordWrite(NextStateConditional):
    """Handles subword writes for wide register fields."""

    def __init__(
        self,
        exp: "RegblockExporter",
        subword_idx: int,
        accesswidth: int,
        regwidth: int,
        strb_path: str,
        strb_index_str: str = "",
    ):
        super().__init__(exp)
        self.subword_idx = subword_idx
        self.accesswidth = accesswidth
        self.regwidth = regwidth
        self.strb_path = strb_path
        self.strb_index_str = strb_index_str

    def is_match(self, field: "FieldNode") -> bool:
        """Check if this field spans multiple subwords and overlaps with this subword."""
        if not hasattr(field, "_is_wide_field"):
            return False

        subword_start = self.subword_idx * self.accesswidth
        subword_end = (self.subword_idx + 1) * self.accesswidth - 1

        # Check if field overlaps with this subword
        return field.low <= subword_end and field.high >= subword_start

    def get_predicate(self, field: "FieldNode") -> str:
        """Generate the condition for this subword write."""
        # For arrayed registers, include array index before subword index
        # For non-arrayed, just use subword index
        if self.strb_index_str:
            # Arrayed: path[array_idx][subword_idx]
            return f"({self.strb_path}{self.strb_index_str}[{self.subword_idx}] && decoded_req_is_wr)"
        else:
            # Non-arrayed: path[subword_idx]
            return f"({self.strb_path}[{self.subword_idx}] && decoded_req_is_wr)"

    def get_assignments(self, field: "FieldNode") -> List[str]:
        """Generate the assignments for this subword write."""
        subword_start = self.subword_idx * self.accesswidth

        # Calculate the slice within this subword
        field_low_in_subword = max(field.low - subword_start, 0)
        field_high_in_subword = min(field.high - subword_start, self.accesswidth - 1)

        # Calculate the field slice in the full field
        field_low_in_full = subword_start + field_low_in_subword
        field_high_in_full = subword_start + field_high_in_subword

        # Use bit-swapped data/biten for MSB0 fields
        if field.msb < field.lsb:
            biten_src = "decoded_wr_biten_bswap"
            data_src = "decoded_wr_data_bswap"
        else:
            biten_src = "decoded_wr_biten"
            data_src = "decoded_wr_data"

        # Generate the bit enable and data slices
        biten_slice = f"{biten_src}[{field_high_in_subword}:{field_low_in_subword}]"
        data_slice = f"{data_src}[{field_high_in_subword}:{field_low_in_subword}]"

        return [
            f"next_c[{field_high_in_full}:{field_low_in_full}] = (next_c[{field_high_in_full}:{field_low_in_full}] & ~{biten_slice}) | ({data_slice} & {biten_slice});",
            "load_next_c = '1;",
        ]

    def comment(self) -> str:  # type: ignore[override]
        return f"SW write to subword {self.subword_idx}"
