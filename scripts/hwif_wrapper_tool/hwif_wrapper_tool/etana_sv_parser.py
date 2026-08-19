"""
Parse etana-generated SystemVerilog module port lists.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class EtanaPort:
    raw: str
    direction: str
    port_type: str
    name: str
    packed_dim: str
    unpacked_dims: str

    @property
    def is_hwif(self) -> bool:
        return False


@dataclass
class EtanaHwifPort(EtanaPort):
    @property
    def is_hwif(self) -> bool:
        return True


def _parse_port_line(line: str) -> EtanaPort:
    line = line.strip().rstrip(",")
    match = re.match(
        r"^(input|output)\s+(wire|logic)\s+(?:(\[[^\]]+\])\s+)?(\w+)(.*)$",
        line,
    )
    if not match:
        raise ValueError(f"Could not parse port line: {line!r}")

    direction, port_type, packed_dim, name, tail = match.groups()
    packed_dim = packed_dim or ""
    unpacked_dims = tail.strip()
    return EtanaPort(
        raw=line,
        direction=direction,
        port_type=port_type,
        name=name,
        packed_dim=packed_dim,
        unpacked_dims=unpacked_dims,
    )


def parse_etana_module_ports(
    sv_path: str,
    in_prefix: str,
    out_prefix: str,
    module_name: Optional[str] = None,
) -> Tuple[List[EtanaPort], List[EtanaHwifPort]]:
    with open(sv_path, encoding="utf-8") as f:
        content = f.read()

    mod_match = re.search(
        r"module\s+(\w+)\s*\((.*?)\);",
        content,
        re.DOTALL,
    )
    if not mod_match:
        raise ValueError(f"No module declaration found in {sv_path}")

    found_name = mod_match.group(1)
    if module_name and found_name != module_name:
        raise ValueError(
            f"Expected module {module_name!r} in {sv_path}, found {found_name!r}"
        )

    cpu_ports: List[EtanaPort] = []
    hwif_ports: List[EtanaHwifPort] = []

    for raw_line in mod_match.group(2).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("//"):
            continue

        port = _parse_port_line(line)
        if port.name.startswith(f"{in_prefix}_") or port.name.startswith(
            f"{out_prefix}_"
        ):
            hwif_ports.append(
                EtanaHwifPort(
                    raw=port.raw,
                    direction=port.direction,
                    port_type=port.port_type,
                    name=port.name,
                    packed_dim=port.packed_dim,
                    unpacked_dims=port.unpacked_dims,
                )
            )
        else:
            cpu_ports.append(port)

    return cpu_ports, hwif_ports


def parse_etana_hwif_csv(csv_path: str) -> Dict[str, Tuple[str, str]]:
    """
    Returns mapping of etana port name -> (direction, rdl_path).
    """
    mapping: Dict[str, Tuple[str, str]] = {}
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            mapping[row["signal_name"]] = (row["direction"], row["rdl_path"])
    return mapping
