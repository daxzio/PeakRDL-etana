from typing import TYPE_CHECKING, Union, Optional, List

from systemrdl.node import FieldNode, RegNode
from systemrdl.walker import WalkerAction
from systemrdl.walker import RDLWalker

from .utils import (
    IndexedPath,
    is_inside_external_block,
    external_policy,
    has_sw_readable_descendants,
    has_sw_writable_descendants,
)
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
    ) -> IndexedPath:
        """
        Returns the IndexedPath that represents the register/field's access strobe.
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
                    subword_suffix = f"[{sidx_lo}]"
                else:
                    subword_suffix = f"[{sidx_hi}:{sidx_lo}]"

                # For arrayed registers, append array indices before subword index
                # This ensures correct order: path[array_idx][subword_idx]
                p.path += p.index_str + subword_suffix
                # Clear index_str since we've already appended it
                p.index = []

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

    def get_external_block_access_strobe(self, node: "AddressableNode") -> IndexedPath:
        assert node.external
        assert not isinstance(node, RegNode)
        p = IndexedPath(self.top_node, node)
        p.path = f"decoded_reg_strb_{p.path}"
        return p


class DecodeStrbGenerator(RDLForLoopGenerator):
    def __init__(self, addr_decode: AddressDecode) -> None:
        self.addr_decode = addr_decode
        super().__init__()
        self._logic_stack: List[object] = []
        self.printed = False
        self.policy = external_policy(self.addr_decode.exp.ds)

    def get_logic(self, node: "Node") -> Optional[str]:

        walker = RDLWalker()
        walker.walk(node, self, skip_top=True)

        return self.finish()

    def build_logic(self, node: "RegNode", active=1) -> None:
        p = self.addr_decode.get_access_strobe(node)
        # Use IndexedPath to get ALL nested array dimensions
        full_path = IndexedPath(self.addr_decode.top_node, node)
        array_dimensions = full_path.array_dimensions

        if array_dimensions is None:
            s = f"logic [{active-1}:0] {p.path};"
        else:
            # Format array dimensions as [dim1][dim2][dim3] for SystemVerilog
            array_suffix = "".join(f"[{dim}]" for dim in array_dimensions)
            s = f"logic [{active-1}:0] {p.path} {array_suffix};"

        self._logic_stack.append(s)

    def enter_AddressableComponent(self, node: "AddressableNode") -> None:
        super().enter_AddressableComponent(node)

    def enter_Regfile(self, node: "RegfileNode") -> Optional[WalkerAction]:
        if self.policy.is_external(node):
            # Declare strobe signal for external regfile
            p = self.addr_decode.get_external_block_access_strobe(node)
            s = f"logic {p.path};"
            self._logic_stack.append(s)
            return WalkerAction.SkipDescendants
        return WalkerAction.Continue

    def enter_Addrmap(self, node: "AddrmapNode") -> Optional[WalkerAction]:
        # Skip top-level
        if node == self.addr_decode.top_node:
            return WalkerAction.Continue

        if self.policy.is_external(node):
            # Declare strobe signal for external addrmap
            p = self.addr_decode.get_external_block_access_strobe(node)
            s = f"logic {p.path};"
            self._logic_stack.append(s)
            return WalkerAction.SkipDescendants
        return WalkerAction.Continue

    def enter_Mem(self, node: "MemNode") -> None:
        if not node.external:
            raise
        # Declare strobe signal for external mem
        p = self.addr_decode.get_external_block_access_strobe(node)
        s = f"logic {p.path};"
        self._logic_stack.append(s)

    def enter_Reg(self, node: "RegNode") -> Optional[WalkerAction]:
        # Skip registers inside external blocks
        if is_inside_external_block(
            node, self.addr_decode.top_node, self.addr_decode.exp.ds
        ):
            return WalkerAction.SkipDescendants

        n_subwords = node.get_property("regwidth") // node.get_property("accesswidth")

        self.build_logic(node, n_subwords)
        self.printed = False
        return WalkerAction.Continue

    def finish(self) -> Optional[str]:
        s = self._logic_stack
        return "\n".join(str(item) for item in s)


class DecodeLogicGenerator(RDLForLoopGenerator):
    def __init__(self, addr_decode: AddressDecode) -> None:
        self.addr_decode = addr_decode
        super().__init__()

        # List of address strides for each dimension
        self._array_stride_stack = []  # type: List[int]
        self.policy = external_policy(self.addr_decode.exp.ds)

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
                current_stride *= dim  # type: ignore[operator]
            strides.reverse()
            self._array_stride_stack.extend([s for s in strides if s is not None])

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

    def enter_Regfile(self, node: "RegfileNode") -> Optional[WalkerAction]:
        if self.policy.is_external(node):
            addr_str = self._get_address_str(node)
            strb = self.addr_decode.get_external_block_access_strobe(node)
            rhs = f"cpuif_req_masked & (cpuif_addr >= {addr_str}) & (cpuif_addr <= {addr_str} + {SVInt(node.size - 1, self.addr_decode.exp.ds.addr_width)})"
            self.add_content(f"{strb.path} = {rhs};")

            # Error checking for valid address
            if self.addr_decode.exp.ds.err_if_bad_addr:
                self.add_content(f"is_valid_addr |= {rhs};")

            # Error checking for invalid read/write
            if self.addr_decode.exp.ds.err_if_bad_rw:
                readable = has_sw_readable_descendants(node)
                writable = has_sw_writable_descendants(node)
                if readable and not writable:
                    self.add_content(f"is_invalid_rw |= {rhs} & cpuif_req_is_wr;")
                elif writable and not readable:
                    self.add_content(f"is_invalid_rw |= {rhs} & !cpuif_req_is_wr;")
                else:
                    self.add_content("is_invalid_rw |= '0;")

            self.add_content(f"is_external |= {rhs};")
            return WalkerAction.SkipDescendants
        return WalkerAction.Continue

    def enter_Addrmap(self, node: "AddrmapNode") -> Optional[WalkerAction]:
        # Skip top-level addrmap
        if node == self.addr_decode.top_node:
            return WalkerAction.Continue

        if self.policy.is_external(node):
            addr_str = self._get_address_str(node)
            strb = self.addr_decode.get_external_block_access_strobe(node)
            rhs = f"cpuif_req_masked & (cpuif_addr >= {addr_str}) & (cpuif_addr <= {addr_str} + {SVInt(node.size - 1, self.addr_decode.exp.ds.addr_width)})"
            self.add_content(f"{strb.path} = {rhs};")

            # Error checking for valid address
            if self.addr_decode.exp.ds.err_if_bad_addr:
                self.add_content(f"is_valid_addr |= {rhs};")

            # Error checking for invalid read/write
            if self.addr_decode.exp.ds.err_if_bad_rw:
                readable = has_sw_readable_descendants(node)
                writable = has_sw_writable_descendants(node)
                if readable and not writable:
                    self.add_content(f"is_invalid_rw |= {rhs} & cpuif_req_is_wr;")
                elif writable and not readable:
                    self.add_content(f"is_invalid_rw |= {rhs} & !cpuif_req_is_wr;")
                else:
                    self.add_content("is_invalid_rw |= '0;")

            self.add_content(f"is_external |= {rhs};")
            return WalkerAction.SkipDescendants
        return WalkerAction.Continue

    def enter_Mem(self, node: MemNode) -> None:
        if not node.external:
            raise
        if node.external:
            addr_str = self._get_address_str(node)
            strb = self.addr_decode.get_external_block_access_strobe(node)
            addr_match = f"cpuif_req_masked & (cpuif_addr >= {addr_str}) & (cpuif_addr <= {addr_str} + {SVInt(node.size - 1, self.addr_decode.exp.ds.addr_width)})"

            # Determine strobe condition based on read/write access
            readable = node.is_sw_readable
            writable = node.is_sw_writable
            if readable and writable:
                rhs = addr_match
                rhs_invalid_rw = "'0"
            elif readable and not writable:
                # Read-only: strobe only for reads
                rhs = f"{addr_match} & !cpuif_req_is_wr"
                rhs_invalid_rw = f"{addr_match} & cpuif_req_is_wr"
            elif writable and not readable:
                # Write-only: strobe only for writes
                rhs = f"{addr_match} & cpuif_req_is_wr"
                rhs_invalid_rw = f"{addr_match} & !cpuif_req_is_wr"
            else:
                raise RuntimeError("External memory must be readable and/or writable")

            self.add_content(f"{strb.path} = {rhs};")
            self.add_content(f"is_external |= {rhs};")

            # Error checking for valid address
            if self.addr_decode.exp.ds.err_if_bad_addr:
                self.add_content(f"is_valid_addr |= {addr_match};")

            # Error checking for invalid read/write
            if self.addr_decode.exp.ds.err_if_bad_rw:
                self.add_content(f"is_invalid_rw |= {rhs_invalid_rw};")
        # return WalkerAction.SkipDescendants

    def enter_Reg(self, node: RegNode) -> Optional[WalkerAction]:
        # Skip registers inside external blocks
        if is_inside_external_block(
            node, self.addr_decode.top_node, self.addr_decode.exp.ds
        ):
            return WalkerAction.SkipDescendants

        regwidth = node.get_property("regwidth")
        accesswidth = node.get_property("accesswidth")

        if regwidth == accesswidth:
            p = self.addr_decode.get_access_strobe(node)
            if len(self._array_stride_stack):
                self.add_content(f"next_cpuif_addr = {self._get_address_str(node)};")
                addr_match = f"cpuif_req_masked & (cpuif_addr == next_cpuif_addr[{self.addr_decode.exp.ds.addr_width-1}:0])"
            else:
                addr_match = (
                    f"cpuif_req_masked & (cpuif_addr == {self._get_address_str(node)})"
                )

            # Determine strobe condition based on read/write access
            readable = node.has_sw_readable
            writable = node.has_sw_writable
            if readable and writable:
                rhs = addr_match
                rhs_invalid_rw = "'0"
            elif readable and not writable:
                # Read-only: strobe only for reads
                rhs = f"{addr_match} & !cpuif_req_is_wr"
                rhs_invalid_rw = f"{addr_match} & cpuif_req_is_wr"
            elif writable and not readable:
                # Write-only: strobe only for writes
                rhs = f"{addr_match} & cpuif_req_is_wr"
                rhs_invalid_rw = f"{addr_match} & !cpuif_req_is_wr"
            else:
                raise RuntimeError("Register must be readable and/or writable")

            if len(self._array_stride_stack):
                s = f"{p.path}{p.index_str} = {rhs};"
            else:
                s = f"{p.path} = {rhs};"
            self.add_content(s)

            # Error checking for valid address
            if self.addr_decode.exp.ds.err_if_bad_addr:
                self.add_content(f"is_valid_addr |= {addr_match};")

            # Error checking for invalid read/write
            if self.addr_decode.exp.ds.err_if_bad_rw:
                self.add_content(f"is_invalid_rw |= {rhs_invalid_rw};")

            # For external registers, mark as external
            if self.policy.is_external(node):
                self.add_content(f"is_external |= {rhs};")
        else:
            # Register is wide. Create a substrobe for each subword
            n_subwords = regwidth // accesswidth
            subword_stride = accesswidth // 8
            for i in range(n_subwords):
                p = self.addr_decode.get_access_strobe(node)
                if len(self._array_stride_stack):
                    self.add_content(
                        f"next_cpuif_addr = {self._get_address_str(node, subword_offset=(i*subword_stride))};"
                    )
                    rhs = f"cpuif_req_masked & (cpuif_addr == next_cpuif_addr[{self.addr_decode.exp.ds.addr_width-1}:0])"
                else:
                    rhs = f"cpuif_req_masked & (cpuif_addr == {self._get_address_str(node, subword_offset=(i*subword_stride))})"
                if 0 == len(p.index):
                    s = f"{p.path}[{i}] = {rhs};"
                else:
                    s = f"{p.path}{p.index_str}[{i}] = {rhs};"
                self.add_content(s)

                # Error checking for valid address (only on first subword)
                if i == 0 and self.addr_decode.exp.ds.err_if_bad_addr:
                    # Use address range for all subwords
                    addr_low = self._get_address_str(node, subword_offset=0)
                    addr_high = self._get_address_str(
                        node, subword_offset=(n_subwords - 1) * subword_stride
                    )
                    rhs_range = f"cpuif_req_masked & (cpuif_addr >= {addr_low}) & (cpuif_addr <= {addr_high})"
                    self.add_content(f"is_valid_addr |= {rhs_range};")

                # Error checking for invalid read/write (only on first subword)
                if i == 0 and self.addr_decode.exp.ds.err_if_bad_rw:
                    readable = node.has_sw_readable
                    writable = node.has_sw_writable
                    addr_low = self._get_address_str(node, subword_offset=0)
                    addr_high = self._get_address_str(
                        node, subword_offset=(n_subwords - 1) * subword_stride
                    )
                    rhs_range = f"cpuif_req_masked & (cpuif_addr >= {addr_low}) & (cpuif_addr <= {addr_high})"
                    if readable and not writable:
                        # Read-only: error on write
                        self.add_content(
                            f"is_invalid_rw |= {rhs_range} & cpuif_req_is_wr;"
                        )
                    elif writable and not readable:
                        # Write-only: error on read
                        self.add_content(
                            f"is_invalid_rw |= {rhs_range} & !cpuif_req_is_wr;"
                        )
                    else:
                        # Read-write: no error
                        self.add_content("is_invalid_rw |= '0;")

                if self.policy.is_external(node):
                    readable = node.has_sw_readable
                    writable = node.has_sw_writable
                    if readable and writable:
                        self.add_content(f"is_external |= {rhs};")
                    elif readable and not writable:
                        self.add_content(f"is_external |= {rhs} & !cpuif_req_is_wr;")
                    elif not readable and writable:
                        self.add_content(f"is_external |= {rhs} & cpuif_req_is_wr;")
                    else:
                        raise RuntimeError(
                            "External register must be readable or writable"
                        )
        return WalkerAction.Continue

    def exit_AddressableComponent(self, node: "AddressableNode") -> None:
        super().exit_AddressableComponent(node)

        if not node.array_dimensions:
            return

        for _ in node.array_dimensions:
            self._array_stride_stack.pop()
