"""
VHDL Package Parser
Parses VHDL package files to extract record type definitions
"""
import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class VhdlField:
    """Represents a field in a VHDL record"""

    name: str
    vhdl_type: str  # e.g., "std_logic", "std_logic_vector(31 downto 0)", etc.
    array_range: Optional[str] = None  # e.g., "(0 to 31)" for arrays

    def get_width_range(self) -> Optional[Tuple[int, int]]:
        """Extract width range from std_logic_vector type"""
        if "std_logic_vector" in self.vhdl_type:
            match = re.search(r"\((\d+)\s+downto\s+(\d+)\)", self.vhdl_type)
            if match:
                return (int(match.group(1)), int(match.group(2)))
        return None


@dataclass
class VhdlRecord:
    """Represents a VHDL record type"""

    type_name: str
    fields: List[VhdlField]
    is_array_element: bool = False


class VhdlPackageParser:
    """Parse VHDL package to extract record definitions"""

    def __init__(self, package_content: str):
        self.package_content = package_content
        self.records: Dict[str, VhdlRecord] = {}
        self._parse_records()

    def _parse_records(self):
        """Extract all record type definitions from package"""
        # Pattern to match: type <name> is record ... end record;
        # Support escaped names like \top.simple_in_t\ with dots and underscores
        # The type name must be on the same logical line (before "is record")
        record_pattern = re.compile(
            r"type\s+([^\n;]+?)\s+is\s+record\s+(.*?)\s+end\s+record\s*;",
            re.DOTALL | re.IGNORECASE,
        )

        for match in record_pattern.finditer(self.package_content):
            type_name = match.group(1).strip()
            record_body = match.group(2).strip()

            fields = self._parse_record_fields(record_body)
            self.records[type_name] = VhdlRecord(type_name, fields)

    def _parse_record_fields(self, record_body: str) -> List[VhdlField]:
        """Parse fields from record body"""
        fields = []

        # Split by semicolon and parse each field
        for line in record_body.split(";"):
            line = line.strip()
            if not line or line.startswith("--"):
                continue

            # Parse: field_name : type_spec
            # Need to handle:
            #   - Simple types: field : std_logic
            #   - Vector types: field : std_logic_vector(31 downto 0)
            #   - Record types: field : \type_name\
            #   - Array of records: field : \type_name\(0 to 31)

            # First, extract field name and everything after the colon
            colon_pos = line.find(":")
            if colon_pos < 0:
                continue

            field_name = line[:colon_pos].strip()
            type_part = line[colon_pos + 1 :].strip()

            # Check if this is an array of something
            # We need to distinguish:
            #   - std_logic_vector(31 downto 0) - this is ONE type
            #   - \some_type\(0 to 31) - this is an ARRAY of some_type
            #
            # Arrays have the range AFTER the type name (which ends with backslash or _t or similar)
            # std_logic_vector has the range as part of the type itself

            array_range = None
            field_type = type_part

            # Check if this looks like an array of records/types
            # Pattern: backslash-escaped type followed by array range
            if "\\" in type_part:
                # Split at the last backslash
                last_backslash = type_part.rfind("\\")
                after_backslash = type_part[last_backslash + 1 :].strip()

                # Check if what follows is an array range
                array_match = re.match(
                    r"(\((?:\d+\s+(?:to|downto)\s+\d+)\))\s*$", after_backslash
                )
                if array_match:
                    array_range = array_match.group(1)
                    field_type = type_part[: last_backslash + 1].strip()

            fields.append(VhdlField(field_name, field_type, array_range))

        return fields

    def flatten_record(
        self, record_name: str, prefix: str = "", path_prefix: str = ""
    ) -> List[Tuple[str, str, str, str]]:
        """
        Flatten a record type into individual signals

        Returns list of (signal_name, vhdl_type, direction, record_path) tuples
        - signal_name: flattened name like hwif_in_ext_reg_rd_ack
        - vhdl_type: type like std_logic or std_logic_vector(31 downto 0)
        - direction: 'in' or 'out'
        - record_path: original nested path like hwif_in.ext_reg.rd_ack
        """
        # Handle record names with or without backslashes
        lookup_name = record_name
        if not lookup_name.startswith("\\") and f"\\{lookup_name}\\" in self.records:
            lookup_name = f"\\{lookup_name}\\"

        if lookup_name not in self.records:
            return []

        record = self.records[lookup_name]
        flattened = []
        direction = "in" if "_in_t" in record_name else "out"

        for field in record.fields:
            field_path = f"{prefix}_{field.name}" if prefix else field.name
            record_path = f"{path_prefix}.{field.name}" if path_prefix else field.name

            # Check if field type is another record (has backslashes or is a known type)
            field_type = field.vhdl_type.strip()
            is_record_type = False
            nested_type = field_type

            # If field has array_range, check if the field_type is an array type
            # Array types typically end with _array (with or without backslashes)
            if field.array_range:
                # Check if field_type ends with _array (handling both escaped and unescaped)
                if field_type.endswith("_array\\"):
                    # Extract base type by removing _array\ suffix
                    base_type = field_type[:-7] + "\\"
                elif field_type.endswith("_array"):
                    # Extract base type by removing _array suffix
                    base_type = field_type[:-6]
                else:
                    # Not an array type pattern, treat as regular type
                    base_type = None

                if base_type:
                    # Check if base type is a record
                    if base_type in self.records:
                        is_record_type = True
                        nested_type = base_type
                    elif base_type.startswith("\\"):
                        # Try without backslashes
                        unescaped_base = base_type.strip("\\")
                        if unescaped_base in self.records:
                            is_record_type = True
                            nested_type = unescaped_base
                    else:
                        # Try with backslashes
                        escaped_base = f"\\{base_type}\\"
                        if escaped_base in self.records:
                            is_record_type = True
                            nested_type = escaped_base
            # Check if it's a record type (either with backslashes or without)
            elif field_type.startswith("\\"):
                # Field type already has backslashes - look it up directly
                if field_type in self.records:
                    is_record_type = True
                    nested_type = field_type
                else:
                    # Try without backslashes
                    unescaped_type = field_type.strip("\\")
                    if unescaped_type in self.records:
                        is_record_type = True
                        nested_type = unescaped_type
            else:
                # Check if it's a known record type (without backslashes)
                if field_type in self.records or f"\\{field_type}\\" in self.records:
                    is_record_type = True
                    nested_type = field_type

            if is_record_type:
                if field.array_range:
                    # Array of records - need to handle differently
                    # Extract array range
                    array_match = re.match(
                        r"\((\d+)\s+(to|downto)\s+(\d+)\)", field.array_range
                    )
                    if array_match:
                        start_idx = int(array_match.group(1))
                        end_idx = int(array_match.group(3))
                        direction_word = array_match.group(2)

                        if direction_word == "to":
                            indices = range(start_idx, end_idx + 1)
                        else:  # downto
                            indices = range(start_idx, end_idx - 1, -1)

                        for idx in indices:
                            # Recursively flatten each array element
                            array_prefix = f"{field_path}_{idx}"
                            array_record_path = f"{record_path}({idx})"
                            flattened.extend(
                                self.flatten_record(
                                    nested_type, array_prefix, array_record_path
                                )
                            )
                else:
                    # Single nested record
                    flattened.extend(
                        self.flatten_record(nested_type, field_path, record_path)
                    )
            else:
                # Simple type - add to flattened list
                # Check if record path ends with .value, .next, or .next_q and remove suffix from field_path
                if record_path.endswith(".value"):
                    if field_path.endswith("_value"):
                        field_path = field_path[:-6]
                elif record_path.endswith(".next_q"):
                    if field_path.endswith("_next_q"):
                        field_path = field_path[:-7]
                elif record_path.endswith(".next"):
                    if field_path.endswith("_next"):
                        field_path = field_path[:-5]

                flattened.append((field_path, field.vhdl_type, direction, record_path))

        return flattened

    def get_top_level_records(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Find the top-level input and output record types
        Looks for records ending with _in_t and _out_t that don't have backslashes
        """
        in_record = None
        out_record = None

        for type_name in self.records.keys():
            # Skip nested types (those with backslashes or dots)
            if "\\" in type_name or "." in type_name:
                continue

            if type_name.endswith("_in_t"):
                in_record = type_name
            elif type_name.endswith("_out_t"):
                out_record = type_name

        return in_record, out_record


def parse_vhdl_package(package_path: str) -> VhdlPackageParser:
    """
    Parse a VHDL package file and return a parser object

    Args:
        package_path: Path to the VHDL package file

    Returns:
        VhdlPackageParser object
    """
    with open(package_path, "r", encoding="utf-8") as f:
        content = f.read()

    return VhdlPackageParser(content)
