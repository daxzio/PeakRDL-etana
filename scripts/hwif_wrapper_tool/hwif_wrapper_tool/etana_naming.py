"""
Etana-compatible hwif port naming (matches peakrdl_etana.utils.IndexedPath).
"""
from __future__ import annotations

import re

VALUE_TERMS = frozenset({"value", "next"})

TERMINAL_PROPS = frozenset(
    {
        "we",
        "wel",
        "hwclr",
        "hwset",
        "swwe",
        "swwel",
        "incr",
        "decr",
        "incrvalue",
        "decrvalue",
        "swmod",
        "swacc",
        "anded",
        "ored",
        "xored",
        "rd_swacc",
        "wr_swacc",
        "rd_swmod",
        "wr_swmod",
        "req",
        "req_is_wr",
        "intr",
        "halt",
        "addr",
        "rd_ack",
        "wr_ack",
    }
)


def indexed_path_join(parts: list[str]) -> str:
    """Apply etana IndexedPath reg/field redundancy collapse."""
    if len(parts) >= 2 and parts[-1] == parts[-2]:
        return "_".join(parts[:-1])
    return "_".join(parts)


def struct_path_to_etana_suffix(struct_path: str) -> str:
    """
    Convert a regblock hwif struct path to an etana port suffix (no i_/o_ prefix).

    Examples:
        hwif_in.INPUT_PER_DOMAIN[0:3].input_per_domain.value -> input_per_domain
        hwif_out.VOUT_IOUT[0:15].IOUT.value -> vout_iout_iout
        hwif_in.r1.f.next[7:0] -> r1_f
        hwif_in.r1.f.we -> r1_f_we
        hwif_in.ext_reg.rd_data.whatever_a[1:0] -> ext_reg_rd_data_whatever_a
    """
    path = re.sub(r"\[\d+(?::\d+)?\]$", "", struct_path)
    path = re.sub(r"\[(-?\d+):(-?\d+)\]", "", path)
    path = re.sub(r"\[(-?\d+)\]", "", path)

    if path.startswith("hwif_in."):
        rest = path[len("hwif_in.") :]
    elif path.startswith("hwif_out."):
        rest = path[len("hwif_out.") :]
    else:
        raise ValueError(f"Not a hwif struct path: {struct_path!r}")

    parts = rest.split(".")
    prop: str | None = None

    if parts[-1] in TERMINAL_PROPS:
        prop = parts[-1]
        hier = parts[:-1]
    elif parts[-1] in VALUE_TERMS:
        hier = parts[:-1]
    else:
        hier = parts

    name = indexed_path_join([part.lower() for part in hier])
    if prop:
        return f"{name}_{prop}"
    return name


def _normalize_struct_path(path: str) -> str:
    """Strip bit ranges and array dimensions for hierarchy comparison."""
    path = re.sub(r"\[\d+(?::\d+)?\]$", "", path)
    path = re.sub(r"\[(-?\d+):(-?\d+)\]", "", path)
    path = re.sub(r"\[(-?\d+)\]", "", path)
    return path


def external_reg_data_aliases(
    struct_path: str,
    in_prefix: str,
    out_prefix: str,
    all_struct_paths: list[str] | None = None,
) -> list[str]:
    """
    Single-field external registers omit the field suffix in etana port names.

    Only emits an alias when the register has exactly one non-reserved field
    at that bus interface (rd_data / wr_data / wr_biten).
    """
    path = _normalize_struct_path(struct_path)
    match = re.match(
        r"hwif_(in|out)\.([^.]+)\.(rd_data|wr_data|wr_biten)\.([^.]+)$",
        path,
    )
    if not match:
        return []

    side, reg, kind, field = match.groups()
    if field.startswith("_reserved_"):
        return []

    if all_struct_paths is not None:
        bus_prefix = f"hwif_{side}.{reg}.{kind}."
        sibling_fields: set[str] = set()
        for raw_path in all_struct_paths:
            if "_reserved_" in raw_path:
                continue
            norm = _normalize_struct_path(raw_path)
            if not norm.startswith(bus_prefix):
                continue
            tail = norm[len(bus_prefix) :]
            if tail and "." not in tail:
                sibling_fields.add(tail)
        if len(sibling_fields) != 1:
            return []

    prefix = in_prefix if side == "in" else out_prefix
    return [f"{prefix}_{indexed_path_join([reg.lower(), kind])}"]


def etana_port_name(struct_path: str, in_prefix: str, out_prefix: str) -> str:
    """Full etana-style port name including i_/o_ (or custom) prefix."""
    prefix = in_prefix if struct_path.startswith("hwif_in.") else out_prefix
    return f"{prefix}_{struct_path_to_etana_suffix(struct_path)}"


def rdl_path_to_struct_path(rdl_path: str, direction: str) -> str | None:
    """
    Map an etana hwif CSV rdl_path to a regblock struct path.

    Handles register fields and out-of-hierarchy signals (e.g. r5.f_next_value).
    """
    parts = rdl_path.split(".")
    if len(parts) < 2:
        return None

    reg = parts[1]
    if len(parts) == 3:
        leaf = parts[2]
        hwif = "hwif_in" if direction == "input" else "hwif_out"

        if direction == "input":
            if leaf.endswith("_next_value"):
                field = leaf[: -len("_next_value")]
                return f"{hwif}.{reg}.{field}.next"
            if leaf.endswith("_incrvalue"):
                field = leaf[: -len("_incrvalue")]
                return f"{hwif}.{reg}.{field}.incrvalue"
            if leaf.endswith("_decrvalue"):
                field = leaf[: -len("_decrvalue")]
                return f"{hwif}.{reg}.{field}.decrvalue"
            for prop in (
                "we",
                "wel",
                "hwclr",
                "hwset",
                "incr",
                "decr",
                "swwe",
                "swwel",
            ):
                if leaf.endswith(f"_{prop}"):
                    field = leaf[: -(len(prop) + 1)]
                    return f"{hwif}.{reg}.{field}.{prop}"

        return f"{hwif}.{reg}.{leaf}.{'next' if direction == 'input' else 'value'}"

    return None
