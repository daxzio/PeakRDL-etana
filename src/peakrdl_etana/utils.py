import re
from typing import Match, Union, Optional

from systemrdl.rdltypes.references import PropertyReference
from systemrdl.node import Node, AddrmapNode, RegNode, FieldNode

from .identifier_filter import kw_filter as kwf
from .sv_int import SVInt


class IndexedPath:
    def __init__(self, top_node: Node, target_node: Node) -> None:
        from systemrdl.node import RegfileNode

        self.top_node = top_node
        self.target_node = target_node
        self.index = []

        # Collect ALL array dimensions from target up to top
        # Walk up the hierarchy and collect array dimensions from all regfiles
        self.array_dimensions = []
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
                current = current.parent
            else:
                break

        # Convert to None if empty
        if not self.array_dimensions:
            self.array_dimensions = None

        try:
            self.width = self.target_node.width
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

        #         if not 0 == len(self.index):
        #             print("+".join(reversed(x)))

        return v

    @property
    def index_vector(self) -> str:
        v = ""
        if not 0 == len(self.index):
            v += "["
            for i in self.index:
                v += f"({i}*{self.regwidth})+"
            v += f":{self.regwidth}]"
        return v

    #
    @property
    def array_instances(self) -> str:
        s = ""
        if not self.array_dimensions is None:
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

        current_node = current_node.parent

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
                    high = int(match.group(2))
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
