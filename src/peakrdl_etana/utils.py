import re
from typing import Match, Union, Optional, List, TYPE_CHECKING

from systemrdl.rdltypes.references import PropertyReference
from systemrdl.node import Node, AddrmapNode, RegNode, FieldNode, RegfileNode

from .identifier_filter import kw_filter as kwf
from .sv_int import SVInt

if TYPE_CHECKING:
    from .exporter import DesignState


class IndexedPath:
    def __init__(self, top_node: Node, target_node: Node) -> None:

        self.top_node = top_node
        self.target_node = target_node
        self.index = []

        # Collect ALL array dimensions from target up to top
        # Walk up the hierarchy and collect array dimensions from all regfiles
        self.array_dimensions: List[int] = []
        current = target_node

        # For FieldNodes, start from the parent (the register)
        if isinstance(target_node, FieldNode):
            current = target_node.parent

        # Walk up the hierarchy collecting array dimensions
        while current is not None and current != top_node:
            if (
                hasattr(current, "array_dimensions")
                and current.array_dimensions is not None
            ):
                # Prepend dimensions (outer dimensions come first)
                self.array_dimensions = (
                    list(current.array_dimensions) + self.array_dimensions
                )

            # Move to parent
            if hasattr(current, "parent"):
                current = current.parent  # type: ignore[assignment]
            else:
                break

        # Convert to None if empty
        if not self.array_dimensions:
            self.array_dimensions = None  # type: ignore[assignment]

        try:
            self.width = self.target_node.width  # type: ignore[attr-defined]
        except AttributeError:
            self.width = None

        self.path = self.target_node.get_rel_path(
            self.top_node, empty_array_suffix="[!]", hier_separator=":"
        )

        def kw_filter_repl(m: Match) -> str:
            return kwf(m.group(0))

        self.path = re.sub(r"\w+", kw_filter_repl, self.path).lower()

        for i, g in enumerate(re.findall(r"\[!\]", self.path)):
            self.index.append(f"i{i}")
        self.path = re.sub(r"\[!\]", "", self.path)

        # When a reg and a field have the same name it is redundant so we only use one
        elem = self.path.split(":")
        try:
            if elem[-1] == elem[-2]:
                self.path = "_".join(elem[:-1])
            else:
                self.path = "_".join(elem)
        except IndexError:
            pass

        self.path = re.sub(r":", "", self.path)

    @property
    def index_str(self) -> str:
        v = ""
        for i in self.index:
            v += f"[{i}]"

        x = []
        mult = 1
        for i, val in enumerate(reversed(self.index)):
            if 0 == i:
                x.append(val)
            else:
                x.append(f"{mult}*{val}")
            mult *= 5

        return v

    @property
    def index_vector(self) -> str:
        v = ""
        if not 0 == len(self.index):
            v += "["
            for i in self.index:
                v += f"({i}*{self.regwidth})+"  # type: ignore[attr-defined]
            v += f":{self.regwidth}]"  # type: ignore[attr-defined]
        return v

    #
    @property
    def array_instances(self) -> str:
        s = ""
        if self.array_dimensions is not None:
            for i in self.array_dimensions:
                s += f"[{i}]"
        return s


def clog2(n: int) -> int:
    return (n - 1).bit_length()


def is_pow2(x: int) -> bool:
    return (x > 0) and ((x & (x - 1)) == 0)


def roundup_pow2(x: int) -> int:
    return 1 << (x - 1).bit_length()


def ref_is_internal(top_node: AddrmapNode, ref: Union[Node, PropertyReference]) -> bool:
    """
    Determine whether the reference is internal to the top node.

    For the sake of this exporter, root signals are treated as internal.
    """
    if isinstance(ref, Node):
        current_node = ref
    elif isinstance(ref, PropertyReference):
        current_node = ref.node
    else:
        raise RuntimeError

    while current_node is not None:
        if current_node == top_node:
            # reached top node without finding any external components
            # is internal!
            return True

        if current_node.external:
            # not internal!
            return False

        current_node = current_node.parent  # type: ignore[assignment]

    # A root signal was referenced, which dodged the top addrmap
    # This is considerd internal for this exporter
    return True


def do_slice(value: Union[SVInt, str], high: int, low: int) -> Union[SVInt, str]:
    if isinstance(value, str):
        # If string, assume this is an identifier. Append bit-slice
        if high == low:
            return f"{value}[{low}]"
        else:
            return f"{value}[{high}:{low}]"
    else:
        # it is an SVInt literal. Slice it down
        mask = (1 << (high + 1)) - 1
        v = (value.value & mask) >> low

        if value.width is not None:
            w = high - low + 1
        else:
            w = None

        return SVInt(v, w)


def do_bitswap(
    value: Union[SVInt, str], width: Optional[int] = None
) -> Union[SVInt, str]:
    if isinstance(value, str):
        # If string, assume this is an identifier
        # Generate explicit bit reversal for Icarus Verilog compatibility
        if width is not None and width > 0:
            # Generate explicit concatenation {value[0], value[1], ..., value[width-1]}
            if width == 1:
                return value

            # Check if value is already a slice like "signal_name[high:low]"
            # If so, we need to expand the individual bit indices
            if "[" in value and ":" in value:
                # Parse out the slice
                # Format: "name[high:low]"
                match = re.match(r"(.+)\[(\d+):(\d+)\]", value)
                if match:
                    base_name = match.group(1)
                    low = int(match.group(3))
                    # Reverse order: generate {base[low], base[low+1], ..., base[high]}
                    bits = [f"{base_name}[{low + i}]" for i in range(width)]
                    return "{" + ", ".join(bits) + "}"

            # Not a slice, just a plain identifier
            bits = [f"{value}[{i}]" for i in range(width)]
            return "{" + ", ".join(bits) + "}"
        else:
            # Fallback to streaming concatenation (won't work in Icarus)
            return "{<<{" + value + "}}"
    else:
        # it is an SVInt literal. bitswap it
        assert value.width is not None  # width must be known!
        v = value.value
        vswap = 0
        for _ in range(value.width):
            vswap = (vswap << 1) + (v & 1)
            v >>= 1
        return SVInt(vswap, value.width)


def is_external_for_codegen(node: Node, ds: "DesignState") -> bool:
    """Single source of truth for whether a node is treated as external
    by the code generator.

    Semantics:
    - Mem nodes: always external
    - Top node: never external
    - When flattening is disabled: honor node.external as-is
    - When flattening is enabled: nested Addrmap/Regfile are NOT external,
      but explicitly external Reg nodes remain external.
    """
    if not hasattr(node, "external") or not node.external:
        return False

    # Memory nodes are always external (SystemRDL spec requirement)
    node_type = type(node).__name__
    if node_type == "MemNode":
        return True

    # Top node is never treated as external
    if node == ds.top_node:
        return False

    # If flattening is disabled, use the external property as-is
    if not ds.flatten_nested_blocks:
        return True

    # When flattening is enabled:
    # - Nested addrmaps/regfiles are NOT external (flatten them)
    # - But respect explicit external register declarations
    if node_type in ["AddrmapNode", "RegfileNode"]:
        return False  # Flatten these

    return True  # RegNode with external property stays external


class ExternalPolicy:
    """Encapsulates external/flattening policy decisions for codegen.

    Prefer using this object over calling helpers directly, so call sites remain
    descriptive and future changes are localized.
    """

    def __init__(self, ds: "DesignState") -> None:
        self.ds = ds

    def is_external(self, node: Node) -> bool:
        return is_external_for_codegen(node, self.ds)

    def is_inside_external(self, node: Node, top_node: Node) -> bool:
        return is_inside_external_block(node, top_node, self.ds)


def external_policy(ds: "DesignState") -> ExternalPolicy:
    return ExternalPolicy(ds)


# Backward compat alias (to be removed after downstream updates)
def should_treat_as_external(node: Node, ds: "DesignState") -> bool:  # noqa: N802
    return is_external_for_codegen(node, ds)


def is_inside_external_block(
    node: Node, top_node: Node, ds: Optional["DesignState"] = None
) -> bool:
    """
    Check if node is inside an external regfile/addrmap.

    This is a common pattern used throughout the codebase to determine
    whether a node is contained within an external block, which requires
    special handling for bus interfaces.

    Args:
        node: The node to check
        top_node: The top-level addrmap node
        ds: Optional DesignState for flatten mode support

    Returns:
        True if node is inside an external block, False otherwise
    """
    parent = node.parent
    while parent is not None and parent != top_node:
        if hasattr(parent, "external") and parent.external:
            # Check if we should actually treat this as external
            if ds is not None and not should_treat_as_external(parent, ds):
                parent = parent.parent if hasattr(parent, "parent") else None
                continue
            return True
        parent = parent.parent if hasattr(parent, "parent") else None
    return False


def has_sw_writable_descendants(node: Union[RegfileNode, AddrmapNode]) -> bool:
    """
    Check if node has any sw-writable descendants.

    For regfiles, checks all registers. For addrmaps, checks all descendants.

    Args:
        node: RegfileNode or AddrmapNode to check

    Returns:
        True if any descendants are sw-writable, False otherwise
    """
    if isinstance(node, RegfileNode):
        return any(reg.has_sw_writable for reg in node.registers())
    elif isinstance(node, AddrmapNode):
        for desc in node.descendants():
            if hasattr(desc, "has_sw_writable") and desc.has_sw_writable:
                return True
    return False


def has_sw_readable_descendants(node: Union[RegfileNode, AddrmapNode]) -> bool:
    """
    Check if node has any sw-readable descendants.

    For regfiles, checks all registers. For addrmaps, checks all descendants.

    Args:
        node: RegfileNode or AddrmapNode to check

    Returns:
        True if any descendants are sw-readable, False otherwise
    """
    if isinstance(node, RegfileNode):
        return any(reg.has_sw_readable for reg in node.registers())
    elif isinstance(node, AddrmapNode):
        for desc in node.descendants():
            if hasattr(desc, "has_sw_readable") and desc.has_sw_readable:
                return True
    return False


def is_wide_single_field_register(reg_node: RegNode) -> bool:
    """
    Check if register is wide with only one field.

    Wide single-field registers use special naming conventions:
    - Use accesswidth instead of regwidth for port declarations
    - Omit field name suffix in signal names

    Args:
        reg_node: Register node to check

    Returns:
        True if register is wide with a single field, False otherwise
    """
    regwidth = reg_node.get_property("regwidth")
    accesswidth = reg_node.get_property("accesswidth")
    n_subwords = regwidth // accesswidth
    return n_subwords > 1 and len(list(reg_node.fields())) == 1
