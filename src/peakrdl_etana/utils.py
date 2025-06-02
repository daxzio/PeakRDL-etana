import re
from typing import Match, Union

from systemrdl.rdltypes.references import PropertyReference
from systemrdl.node import Node, AddrmapNode, RegNode, RegfileNode, FieldNode

from .identifier_filter import kw_filter as kwf
from .sv_int import SVInt

class IndexedPath:
    def __init__(self, top_node: Node, target_node: Node):
        self.top_node = top_node
        self.target_node = target_node
        self.index = []
#         if isinstance(self.target_node, RegNode):
#             self.array_dimensions = self.target_node.parent.array_dimensions
#         elif isinstance(self.target_node, FieldNode):
#             self.array_dimensions = self.target_node.parent.array_dimensions
#             print(True, self.array_dimensions)
        self.array_dimensions = self.target_node.parent.array_dimensions
        
        try:
            self.width = self.target_node.width
        except AttributeError:
            self.width = None
            
        self.inst_names = []
        self.regwidth = []
        self.rd_elem = []
        self.wr_elem = []
        self.pn = []
        last_lsb_rd = 0
        last_lsb_wr = 0
        tnodes = [self.target_node]
        n_subwords=1
        if isinstance(self.target_node, RegNode):
            n_subwords = self.target_node.get_property("regwidth") // self.target_node.get_property("accesswidth")
        if isinstance(self.target_node, AddrmapNode):
           for c in self.target_node.children():
               #print(c)        
               tnodes = [c]

#                self.target_node = c
#         if isinstance(self.target_node, FieldNode):
#             print('tnodes', tnodes)
#             for tnode in tnodes:
#                 print(tnode)
        if isinstance(self.target_node, RegfileNode):
#            print(target_node.inst_name)
           tnodes = []
           for c in self.target_node.children():
               tnodes.append(c)
               self.pn.append(c.inst_name)

        for tnode in tnodes:
            for c in tnode.children():
#                 print(tnode, c.width)
                if 1 == n_subwords:
                    width = c.width
                else:
                    width = self.target_node.get_property("accesswidth")
                self.inst_names.append(c.inst_name)
                self.regwidth.append(width)
                if c.is_sw_readable:
                    if c.lsb > last_lsb_rd:
                        d = c.lsb-last_lsb_rd
#                         print(True, d, f"{d}'b0")
                        self.rd_elem.append([None, d, f"{d}'b0"])
#                     print(c.inst_name, c.is_sw_readable, c.width, f"[{c.msb}:{c.lsb}]")
                    self.rd_elem.append([c.inst_name, c.width, f"[{c.msb}:{c.lsb}]"])
                    last_lsb_rd = c.msb+1
                if c.is_sw_writable:
                    if 1 == n_subwords:
                        if c.lsb > last_lsb_wr:
                            d = c.lsb-last_lsb_wr
#                             print(True, d, f"{d}'b0")
                            self.wr_elem.append([None, d, f"{d}'b0"])
#                         print(c.inst_name, c.is_sw_readable, c.width, f"[{c.msb}:{c.lsb}]")
                        self.wr_elem.append([c.inst_name, width, f"[{c.msb}:{c.lsb}]"])
                        last_lsb_wr = c.msb+1
                    else:
                        self.wr_elem.append([c.inst_name, width, f"[{width-1}:{0}]"])
     
        
        self.path = self.target_node.get_rel_path(self.top_node, empty_array_suffix="[!]", hier_separator="_")
        def kw_filter_repl(m: Match) -> str:
            return kwf(m.group(0))
        self.path = re.sub(r'\w+', kw_filter_repl, self.path).lower()
        
        
        for i, g in enumerate(re.findall(r'\[!\]', self.path)):
            self.index.append(f'i{i}')
        self.path = re.sub(r'\[!\]', "", self.path)
#         if isinstance(self.target_node, FieldNode):
#             print('z', self.path)
    
    @property
    def index_str(self) -> str:
        v = ""
        for i in self.index:
            v += f"[{i}]"
        return v
    
#     @property
#     def index_vector(self) -> str:
#         v = ""
#         if not 0 == len(self.index): 
#             v += "["
#             for i in self.index:
#                 v += f"({i}*{self.regwidth})+"
#             v += f":{self.regwidth}]"
#         return v
#     
    @property
    def array_instances(self) -> str:
        s = ""
        if not self.array_dimensions is None:
            for i in self.array_dimensions:
                s += f"[{i}]"
        return s


def get_indexed_path(top_node: Node, target_node: Node, index=True) -> str:
    """
    TODO: Add words about indexing and why i'm doing this. Copy from logbook
    """
    p = IndexedPath(top_node, target_node)
    raise
    path = target_node.get_rel_path(top_node, empty_array_suffix="[!]")


    # replace unknown indexes with incrementing iterators i0, i1, ...
    class ReplaceUnknown:
        def __init__(self) -> None:
            self.i = 0
        def __call__(self) -> str:
            s = f'i{self.i}'
            self.i += 1
            return s
    
    r = ReplaceUnknown()
    index = ""
    if g := re.search(r'!', path):
        index = f"[{r.__call__()}]"
        path = re.sub(r'\[!\]', "", path)
        
    # Sanitize any SV keywords
    def kw_filter_repl(m: Match) -> str:
        return kwf(m.group(0))
    path = re.sub(r'\w+', kw_filter_repl, path)

    path = re.sub(r'\.', '_', path).lower()
#     print(path)
    
    path += index

    return path

def clog2(n: int) -> int:
    return (n-1).bit_length()

def is_pow2(x: int) -> bool:
    return (x > 0) and ((x & (x - 1)) == 0)

def roundup_pow2(x: int) -> int:
    return 1<<(x-1).bit_length()

def ref_is_internal(top_node: AddrmapNode, ref: Union[Node, PropertyReference]) -> bool:
    """
    Determine whether the reference is internal to the top node.

    For the sake of this exporter, root signals are treated as internal.
    """
    if isinstance(ref, Node):
        current_node = ref
    elif isinstance(ref, PropertyReference):
        current_node = ref.node

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

def do_bitswap(value: Union[SVInt, str]) -> Union[SVInt, str]:
    if isinstance(value, str):
        # If string, assume this is an identifier. Wrap in a streaming operator
        return "{<<{" + value + "}}"
    else:
        # it is an SVInt literal. bitswap it
        assert value.width is not None # width must be known!
        v = value.value
        vswap = 0
        for _ in range(value.width):
            vswap = (vswap << 1) + (v & 1)
            v >>= 1
        return SVInt(vswap, value.width)
