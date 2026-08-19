"""
Compute hwif vector bit layouts from PeakRDL-regblock package files.

sv2v packs SystemVerilog structs MSB-first: first-declared member at the MSB,
array index 0 at the MSB end of the array range.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class StructMember:
    type_name: str
    name: str
    array_sizes: List[int] = field(default_factory=list)


@dataclass
class StructDef:
    name: str
    members: List[StructMember] = field(default_factory=list)


@dataclass
class HwifLeaf:
    path: str
    msb: int
    lsb: int
    width: int


def parse_pkg_structs(pkg_content: str) -> Dict[str, StructDef]:
    """Parse typedef struct definitions from a regblock package file."""
    structs: Dict[str, StructDef] = {}

    for match in re.finditer(
        r"typedef\s+struct\s+(?:packed\s+)?\{(.*?)\}\s+(\w+)\s*;",
        pkg_content,
        re.DOTALL,
    ):
        body = match.group(1)
        name = match.group(2)
        members: List[StructMember] = []
        for line in body.splitlines():
            line = line.strip().rstrip(",")
            if not line or line.startswith("//"):
                continue
            member = _parse_member_line(line)
            if member is not None:
                members.append(member)
        structs[name] = StructDef(name=name, members=members)

    return structs


def _parse_member_line(line: str) -> Optional[StructMember]:
    line = line.rstrip(";").strip()
    array_sizes: List[int] = []
    while True:
        array_match = re.search(r"\[(\d+)\]\s*$", line)
        if not array_match:
            break
        array_sizes.insert(0, int(array_match.group(1)))
        line = line[: array_match.start()].strip()

    match = re.match(
        r"((?:logic(?:\s+signed)?(?:\s+\[[^\]]+\])?))\s+(\S+)\s*$",
        line,
    )
    if match:
        return StructMember(
            type_name=match.group(1).strip(),
            name=match.group(2),
            array_sizes=array_sizes,
        )

    parts = line.rsplit(None, 1)
    if len(parts) != 2:
        return None
    return StructMember(
        type_name=parts[0].strip(),
        name=parts[1],
        array_sizes=array_sizes,
    )


def logic_type_width(type_name: str) -> int:
    range_match = re.search(r"\[(-?\d+):(-?\d+)\]", type_name)
    if range_match:
        hi = int(range_match.group(1))
        lo = int(range_match.group(2))
        return abs(hi - lo) + 1
    if type_name.startswith("logic"):
        return 1
    raise ValueError(f"Expected logic type, got {type_name!r}")


def type_width(type_name: str, structs: Dict[str, StructDef]) -> int:
    if type_name.startswith("logic"):
        return logic_type_width(type_name)
    return struct_total_width(type_name, structs)


def struct_total_width(type_name: str, structs: Dict[str, StructDef]) -> int:
    struct = structs[type_name]
    total = 0
    for member in struct.members:
        member_width = type_width(member.type_name, structs)
        count = 1
        for size in member.array_sizes:
            count *= size
        total += member_width * count
    return total


def find_hwif_root_types(
    structs: Dict[str, StructDef], module_name: str
) -> Tuple[Optional[str], Optional[str]]:
    in_type = f"{module_name}__in_t"
    out_type = f"{module_name}__out_t"
    return (
        in_type if in_type in structs else None,
        out_type if out_type in structs else None,
    )


def compute_hwif_layout(
    structs: Dict[str, StructDef],
    in_type: Optional[str],
    out_type: Optional[str],
) -> Tuple[Dict[str, Tuple[int, int, int]], int, int]:
    """
    Return leaf map {path: (msb, lsb, width)}, in_width, out_width.
    """
    layout: Dict[str, Tuple[int, int, int]] = {}
    in_width = 0
    out_width = 0

    if in_type is not None:
        in_width = struct_total_width(in_type, structs)
        _pack_type(in_type, "hwif_in", in_width - 1, structs, layout)

    if out_type is not None:
        out_width = struct_total_width(out_type, structs)
        _pack_type(out_type, "hwif_out", out_width - 1, structs, layout)

    return layout, in_width, out_width


def _pack_type(
    type_name: str,
    path: str,
    cursor_msb: int,
    structs: Dict[str, StructDef],
    layout: Dict[str, Tuple[int, int, int]],
) -> int:
    if type_name.startswith("logic"):
        width = logic_type_width(type_name)
        lsb = cursor_msb - width + 1
        layout[path] = (cursor_msb, lsb, width)
        return cursor_msb - width

    struct = structs[type_name]
    cursor = cursor_msb
    for member in struct.members:
        member_path = f"{path}.{member.name}"
        if member.array_sizes:
            cursor = _pack_array(
                member.type_name,
                member_path,
                member.array_sizes,
                cursor,
                structs,
                layout,
            )
        else:
            cursor = _pack_type(member.type_name, member_path, cursor, structs, layout)
    return cursor


def _pack_array(
    type_name: str,
    path: str,
    array_sizes: List[int],
    cursor_msb: int,
    structs: Dict[str, StructDef],
    layout: Dict[str, Tuple[int, int, int]],
) -> int:
    elem_width = type_width(type_name, structs)

    def rec(dim: int, indices: List[int], block_msb: int) -> int:
        if dim == len(array_sizes):
            indexed_path = path + "".join(f"[{idx}]" for idx in indices)
            return _pack_type(type_name, indexed_path, block_msb, structs, layout)

        size = array_sizes[dim]
        sub_block_width = _tail_size(array_sizes, dim + 1, elem_width)
        final_cursor = block_msb
        for index in range(size):
            elem_msb = block_msb - index * sub_block_width
            final_cursor = rec(dim + 1, indices + [index], elem_msb)
        return final_cursor

    return rec(0, [], cursor_msb)


def _tail_size(array_sizes: List[int], dim: int, elem_width: int) -> int:
    count = 1
    for size in array_sizes[dim:]:
        count *= size
    return count * elem_width


def path_with_numeric_indices(path: str, indices: List[int]) -> str:
    """Replace [N:M] array ranges in a struct path with numeric indices."""
    idx = 0

    def replace_range(match: re.Match[str]) -> str:
        nonlocal idx
        if idx < len(indices):
            result = f"[{indices[idx]}]"
            idx += 1
            return result
        return match.group(0)

    return re.sub(r"\[\d+:\d+\]", replace_range, path)


def path_with_index(path: str, index_vars: List[str]) -> str:
    """Replace [N:M] array ranges in a struct path with index variables."""
    idx = 0

    def replace_range(match: re.Match[str]) -> str:
        nonlocal idx
        if idx < len(index_vars):
            result = f"[{index_vars[idx]}]"
            idx += 1
            return result
        return match.group(0)

    return re.sub(r"\[\d+:\d+\]", replace_range, path)


def slice_expr(vector: str, msb: int, lsb: int, width: int) -> str:
    if width == 1:
        return f"{vector}[{msb}]"
    return f"{vector}[{msb}:{lsb}]"
