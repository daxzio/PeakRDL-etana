from typing import TYPE_CHECKING, Union, Optional

from systemrdl.node import FieldNode, RegNode
from systemrdl.walker import WalkerAction
from systemrdl.walker import RDLWalker

from .utils import IndexedPath
from .forloop_generator import RDLForLoopGenerator
from .sv_int import SVInt

if TYPE_CHECKING:
    from .exporter import RegblockExporter
    from systemrdl.node import AddrmapNode, AddressableNode
    from systemrdl.node import Node, RegfileNode, MemNode
else:
    from systemrdl.node import RegfileNode, MemNode


class AddressDecode:
    def __init__(self, exp: "RegblockExporter") -> None:
        self.exp = exp

    @property
    def top_node(self) -> "AddrmapNode":
        return self.exp.ds.top_node

    def get_strobe_logic(self) -> str:
        logic_gen = DecodeStrbGenerator(self)
        s = logic_gen.get_logic(self.top_node)
        assert s is not None  # guaranteed to have at least one reg
        return s

    def get_implementation(self) -> str:
        gen = DecodeLogicGenerator(self)
        s = gen.get_content(self.top_node)
        assert s is not None
        return s

    def get_access_strobe(
        self, node: Union[RegNode, FieldNode], reduce_substrobes: bool = True
    ) -> str:
        """
        Returns the Verilog string that represents the register/field's access strobe.
        """
        if isinstance(node, FieldNode):
            field = node
            p = IndexedPath(self.top_node, node.parent)

            regwidth = node.parent.get_property("regwidth")
            accesswidth = node.parent.get_property("accesswidth")
            if regwidth > accesswidth:
                # Is wide register.
                # Determine the substrobe(s) relevant to this field
                sidx_hi = field.msb // accesswidth
                sidx_lo = field.lsb // accesswidth
                if sidx_hi == sidx_lo:
                    suffix = f"[{sidx_lo}]"
                else:
                    suffix = f"[{sidx_hi}:{sidx_lo}]"
                p.path += suffix

                if sidx_hi != sidx_lo and reduce_substrobes:
                    p.path = "|decoded_reg_strb_" + p.path
                    return p

        elif isinstance(node.parent, RegfileNode):
            p = IndexedPath(self.top_node, node)
        elif isinstance(node.parent, MemNode):
            pass
        else:
            p = IndexedPath(self.top_node, node)

        p.path = f"decoded_reg_strb_{p.path}"
        return p

    def get_external_block_access_strobe(self, node: "AddressableNode") -> str:
        assert node.external
        assert not isinstance(node, RegNode)
        p = IndexedPath(self.top_node, node)
        p.path = f"decoded_reg_strb_{p.path}"
        return p


class DecodeStrbGenerator(RDLForLoopGenerator):
    def __init__(self, addr_decode: AddressDecode) -> None:
        self.addr_decode = addr_decode
        super().__init__()
        self._logic_stack = []  # type: List[_StructBase]
        self.printed = False

    def get_logic(self, node: "Node") -> Optional[str]:

        walker = RDLWalker()
        walker.walk(node, self, skip_top=True)

        return self.finish()

    def build_logic(self, node: "RegNode", active=1) -> None:
        p = self.addr_decode.get_access_strobe(node)
        if isinstance(node.parent, RegfileNode):
            array_dimensions = node.parent.array_dimensions
        else:
            array_dimensions = node.array_dimensions

        if array_dimensions is None:
            s = f"logic [{active-1}:0] {p.path};"
        else:
            s = f"logic [{active-1}:0] {p.path} {array_dimensions};"

        self._logic_stack.append(s)

    def enter_AddressableComponent(self, node: "AddressableNode") -> None:
        super().enter_AddressableComponent(node)

    def enter_Mem(self, node: "MemNode") -> None:
        if not node.external:
            raise
        self.build_logic(node)

    def enter_Reg(self, node: "RegNode") -> None:
        n_subwords = node.get_property("regwidth") // node.get_property("accesswidth")

        self.build_logic(node, n_subwords)
        self.printed = False

    def finish(self) -> Optional[str]:
        s = self._logic_stack
        return str("\n".join(s))


class DecodeLogicGenerator(RDLForLoopGenerator):
    def __init__(self, addr_decode: AddressDecode) -> None:
        self.addr_decode = addr_decode
        super().__init__()

        # List of address strides for each dimension
        self._array_stride_stack = []  # type: List[int]

    def enter_AddressableComponent(
        self, node: "AddressableNode"
    ) -> Optional[WalkerAction]:
        super().enter_AddressableComponent(node)

        if node.array_dimensions:
            # Collect strides for each array dimension
            current_stride = node.array_stride
            strides = []
            for dim in reversed(node.array_dimensions):
                strides.append(current_stride)
                current_stride *= dim
            strides.reverse()
            self._array_stride_stack.extend(strides)

        return WalkerAction.Continue

    def _get_address_str(self, node: "AddressableNode", subword_offset: int = 0) -> str:
        if len(self._array_stride_stack):
            a = str(
                SVInt(
                    node.raw_absolute_address
                    - self.addr_decode.top_node.raw_absolute_address
                    + subword_offset,
                    32,
                )
            )
            for i, stride in enumerate(self._array_stride_stack):
                a += f" + i{i}*{SVInt(stride, self.addr_decode.exp.ds.addr_width)}"
        else:
            a = str(
                SVInt(
                    node.raw_absolute_address
                    - self.addr_decode.top_node.raw_absolute_address
                    + subword_offset,
                    self.addr_decode.exp.ds.addr_width,
                )
            )
        return a

    #     def _get_address_str(self, node: 'AddressableNode', subword_offset: int=0) -> str:
    #         expr_width = self.addr_decode.exp.ds.addr_width
    #         a = str(SVInt(
    #             node.raw_absolute_address - self.addr_decode.top_node.raw_absolute_address + subword_offset,
    #             expr_width
    #         ))
    #         for i, stride in enumerate(self._array_stride_stack):
    #             a += f" + ({expr_width})'(i{i}) * {SVInt(stride, expr_width)}"
    #         return a

    def enter_Mem(self, node: MemNode) -> None:
        if node.external:
            addr_str = self._get_address_str(node)
            strb = self.addr_decode.get_external_block_access_strobe(node)
            rhs = f"cpuif_req_masked & (cpuif_addr >= {addr_str}) & (cpuif_addr <= {addr_str} + {SVInt(node.size - 1, self.addr_decode.exp.ds.addr_width)})"
            self.add_content(f"{strb.path} = {rhs};")
            self.add_content(f"is_external |= {rhs};")
            return WalkerAction.SkipDescendants

    def enter_Reg(self, node: RegNode) -> None:
        regwidth = node.get_property("regwidth")
        accesswidth = node.get_property("accesswidth")

        if regwidth == accesswidth:
            p = self.addr_decode.get_access_strobe(node)
            if len(self._array_stride_stack):
                self.add_content(f"next_cpuif_addr = {self._get_address_str(node)};")
                rhs = f"cpuif_req_masked & (cpuif_addr == next_cpuif_addr[{self.addr_decode.exp.ds.addr_width-1}:0])"
                s = f"{p.path}{p.index_str} = {rhs};"
            else:
                rhs = (
                    f"cpuif_req_masked & (cpuif_addr == {self._get_address_str(node)})"
                )
                s = f"{p.path} = {rhs};"
            self.add_content(s)
            if node.external:
                readable = node.has_sw_readable
                writable = node.has_sw_writable
                if readable and writable:
                    self.add_content(f"is_external |= {rhs};")
                elif readable and not writable:
                    self.add_content(f"is_external |= {rhs} & !cpuif_req_is_wr;")
                elif not readable and writable:
                    self.add_content(f"is_external |= {rhs} & cpuif_req_is_wr;")
                else:
                    raise RuntimeError
        else:
            # Register is wide. Create a substrobe for each subword
            n_subwords = regwidth // accesswidth
            subword_stride = accesswidth // 8
            for i in range(n_subwords):
                p = self.addr_decode.get_access_strobe(node)
                rhs = f"cpuif_req_masked & (cpuif_addr == {self._get_address_str(node, subword_offset=(i*subword_stride))})"
                if 0 == len(p.index):
                    s = f"{p.path}[{i}] = {rhs};"
                else:
                    for y in p.index:
                        print(y)
                    # x = f"({n_subwords}*{p.index[0]})"
                    s = f"{p.path}{p.index_str}[{i}] = {rhs};"
                self.add_content(s)
                if node.external:
                    readable = node.has_sw_readable
                    writable = node.has_sw_writable
                    if readable and writable:
                        self.add_content(f"is_external |= {rhs};")
                    elif readable and not writable:
                        self.add_content(f"is_external |= {rhs} & !cpuif_req_is_wr;")
                    elif not readable and writable:
                        self.add_content(f"is_external |= {rhs} & cpuif_req_is_wr;")
                    else:
                        raise RuntimeError

    def exit_AddressableComponent(self, node: "AddressableNode") -> None:
        super().exit_AddressableComponent(node)

        if not node.array_dimensions:
            return

        for _ in node.array_dimensions:
            self._array_stride_stack.pop()
