from typing import TYPE_CHECKING, Union, Optional, List

from systemrdl.node import FieldNode, RegNode
from systemrdl.walker import WalkerAction
from systemrdl.walker import RDLWalker

from .utils import (
    IndexedPath,
    is_inside_external_block,
    external_policy,
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

    def get_cpuif_index_logic(self) -> Optional[str]:
        gen = CpuifIndexGenerator(self)
        s = gen.get_content(self.top_node)
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
        """
        Generate address string expression for direct comparison with cpuif_addr.

        Args:
            node: Addressable node
            subword_offset: Subword offset in bytes
        """
        addr_width = self.addr_decode.exp.ds.addr_width
        if len(self._array_stride_stack):
            # Use address width consistently for all parts of the expression
            # Cast loop variables to address width to avoid width expansion warnings
            base_addr = str(
                SVInt(
                    node.raw_absolute_address
                    - self.addr_decode.top_node.raw_absolute_address
                    + subword_offset,
                    addr_width,
                )
            )
            # Build expression with proper casting to avoid width expansion
            expr_parts = [base_addr]
            for i, stride in enumerate(self._array_stride_stack):
                expr_parts.append(f"({addr_width})'(i{i})*{SVInt(stride, addr_width)}")
            # Cast the entire expression to address width for direct comparison
            a = f"({addr_width})'({'+'.join(expr_parts)})"
        else:
            a = str(
                SVInt(
                    node.raw_absolute_address
                    - self.addr_decode.top_node.raw_absolute_address
                    + subword_offset,
                    addr_width,
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

            # Also assign is_valid_addr when err_if_bad_rw is set so that it can be used to catch
            # invalid RW accesses on existing registers only.
            if (
                self.addr_decode.exp.ds.err_if_bad_addr
                or self.addr_decode.exp.ds.err_if_bad_rw
            ):
                self.add_content(f"is_valid_addr |= {rhs};")
            # For external register blocks, all accesses are valid RW
            if self.addr_decode.exp.ds.err_if_bad_rw:
                self.add_content(f"is_valid_rw |= {rhs};")

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

            # Also assign is_valid_addr when err_if_bad_rw is set so that it can be used to catch
            # invalid RW accesses on existing registers only.
            if (
                self.addr_decode.exp.ds.err_if_bad_addr
                or self.addr_decode.exp.ds.err_if_bad_rw
            ):
                self.add_content(f"is_valid_addr |= {rhs};")
            # For external register blocks, all accesses are valid RW
            if self.addr_decode.exp.ds.err_if_bad_rw:
                self.add_content(f"is_valid_rw |= {rhs};")

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
            elif readable and not writable:
                # Read-only: strobe only for reads
                rhs = f"{addr_match} & !cpuif_req_is_wr"
            elif writable and not readable:
                # Write-only: strobe only for writes
                rhs = f"{addr_match} & cpuif_req_is_wr"
            else:
                raise RuntimeError("External memory must be readable and/or writable")

            self.add_content(f"{strb.path} = {rhs};")
            self.add_content(f"is_external |= {rhs};")

            # Also assign is_valid_addr when err_if_bad_rw is set so that it can be used to catch
            # invalid RW accesses on existing registers only.
            if (
                self.addr_decode.exp.ds.err_if_bad_addr
                or self.addr_decode.exp.ds.err_if_bad_rw
            ):
                self.add_content(f"is_valid_addr |= {addr_match};")
            if self.addr_decode.exp.ds.err_if_bad_rw:
                self.add_content(f"is_valid_rw |= {rhs};")
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
            # Use direct comparison with properly cast expression
            addr_match = (
                f"cpuif_req_masked & (cpuif_addr == {self._get_address_str(node)})"
            )

            # Determine strobe condition based on read/write access
            readable = node.has_sw_readable
            writable = node.has_sw_writable
            if readable and writable:
                rhs = addr_match
            elif readable and not writable:
                # Read-only: strobe only for reads
                rhs = f"{addr_match} & !cpuif_req_is_wr"
            elif writable and not readable:
                # Write-only: strobe only for writes
                rhs = f"{addr_match} & cpuif_req_is_wr"
            else:
                raise RuntimeError("Register must be readable and/or writable")

            if len(self._array_stride_stack):
                s = f"{p.path}{p.index_str} = {rhs};"
            else:
                s = f"{p.path} = {rhs};"
            self.add_content(s)

            # Also assign is_valid_addr when err_if_bad_rw is set so that it can be used to catch
            # invalid RW accesses on existing registers only.
            if (
                self.addr_decode.exp.ds.err_if_bad_addr
                or self.addr_decode.exp.ds.err_if_bad_rw
            ):
                self.add_content(f"is_valid_addr |= {addr_match};")
            if self.addr_decode.exp.ds.err_if_bad_rw:
                self.add_content(f"is_valid_rw |= {rhs};")

            # For external registers, mark as external
            if self.policy.is_external(node):
                self.add_content(f"is_external |= {rhs};")
        else:
            # Register is wide. Create a substrobe for each subword
            n_subwords = regwidth // accesswidth
            subword_stride = accesswidth // 8
            for i in range(n_subwords):
                p = self.addr_decode.get_access_strobe(node)
                # Use direct comparison with properly cast expression
                rhs = f"cpuif_req_masked & (cpuif_addr == {self._get_address_str(node, subword_offset=(i*subword_stride))})"
                if 0 == len(p.index):
                    s = f"{p.path}[{i}] = {rhs};"
                else:
                    s = f"{p.path}{p.index_str}[{i}] = {rhs};"
                self.add_content(s)

                # Also assign is_valid_addr when err_if_bad_rw is set so that it can be used to catch
                # invalid RW accesses on existing registers only.
                if i == 0 and (
                    self.addr_decode.exp.ds.err_if_bad_addr
                    or self.addr_decode.exp.ds.err_if_bad_rw
                ):
                    # Use address range for all subwords
                    addr_low = self._get_address_str(node, subword_offset=0)
                    addr_high = self._get_address_str(
                        node, subword_offset=(n_subwords - 1) * subword_stride
                    )
                    rhs_range = f"cpuif_req_masked & (cpuif_addr >= {addr_low}) & (cpuif_addr <= {addr_high})"
                    self.add_content(f"is_valid_addr |= {rhs_range};")

                # Error checking for valid read/write (only on first subword)
                if i == 0 and self.addr_decode.exp.ds.err_if_bad_rw:
                    readable = node.has_sw_readable
                    writable = node.has_sw_writable
                    addr_low = self._get_address_str(node, subword_offset=0)
                    addr_high = self._get_address_str(
                        node, subword_offset=(n_subwords - 1) * subword_stride
                    )
                    rhs_range = f"cpuif_req_masked & (cpuif_addr >= {addr_low}) & (cpuif_addr <= {addr_high})"
                    if readable and writable:
                        # Read-write: all accesses in range are valid
                        rhs = rhs_range
                    elif readable and not writable:
                        # Read-only: only reads are valid
                        rhs = f"{rhs_range} & !cpuif_req_is_wr"
                    elif writable and not readable:
                        # Write-only: only writes are valid
                        rhs = f"{rhs_range} & cpuif_req_is_wr"
                    else:
                        raise RuntimeError("Register must be readable or writable")
                    self.add_content(f"is_valid_rw |= {rhs};")

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


class CpuifIndexGenerator(RDLForLoopGenerator):
    """
    Generates cpuif_index calculation logic that maps each valid address
    to a sequential index (0, 1, 2, ...) regardless of address gaps.

    For arrays, generates: for(int i0=0; i0<dim; i0++) { if (addr == base + i0*stride) cpuif_index = base_idx + i0; }
    For single registers: if (addr == base) cpuif_index = idx;
    """

    def __init__(self, addr_decode: AddressDecode) -> None:
        self.addr_decode = addr_decode
        super().__init__()

        # Track sequential index for each valid address
        self.current_index = 0

        # List of address strides for each dimension (same as DecodeLogicGenerator)
        self._array_stride_stack: List[int] = []
        self.policy = external_policy(self.addr_decode.exp.ds)

        # Track base index when entering an array (for calculating offset)
        self._base_index_stack: List[int] = []
        # Track index stride for each array dimension (number of indices per instance)
        # This is calculated in pop_loop(), similar to readback generator
        self._index_stride_stack: List[tuple] = []
        # Track start index for each loop level (similar to readback generator's start_offset_stack)
        self._start_index_stack: List[int] = []
        # Track dimensions for each loop level
        self._dim_stack: List[int] = []

    def _get_address_str(self, node: "AddressableNode", subword_offset: int = 0) -> str:
        """Generate address string, handling array dimensions."""
        base_addr = (
            node.raw_absolute_address
            - self.addr_decode.top_node.raw_absolute_address
            + subword_offset
        )
        addr_width = self.addr_decode.exp.ds.addr_width

        if len(self._array_stride_stack):
            # For arrays, generate: base + i0*stride0 + i1*stride1 + ...
            # Use address width consistently for all parts of the expression
            # Cast loop variables to address width to avoid width expansion warnings
            base_addr_str = str(SVInt(base_addr, addr_width))
            # Build expression with proper casting to avoid width expansion
            expr_parts = [base_addr_str]
            for i, stride in enumerate(self._array_stride_stack):
                expr_parts.append(f"({addr_width})'(i{i})*{SVInt(stride, addr_width)}")
            # Cast the entire expression to ensure consistent width
            a = f"({addr_width})'({'+'.join(expr_parts)})"
        else:
            # Single element
            a = str(SVInt(base_addr, addr_width))
        return a

    def push_loop(self, dim: int) -> None:
        """Override to track start index for stride calculation."""
        super().push_loop(dim)
        self._start_index_stack.append(self.current_index)
        self._dim_stack.append(dim)

    def pop_loop(self) -> None:
        """Override to calculate stride when exiting loop."""
        start_index = self._start_index_stack.pop()
        dim = self._dim_stack.pop()

        # Number of indices used by registers enclosed in this loop
        # This is calculated BEFORE advancing current_index
        n_indices = self.current_index - start_index

        # Store stride for this loop level (for replacing placeholder tokens)
        # loop_idx is the index of the loop variable (0 for i0, 1 for i1, etc.)
        # _loop_level is the nesting level (1 when inside first loop, 2 when inside second, etc.)
        # So loop_idx = _loop_level - 1
        # Calculate loop_idx BEFORE calling super().pop_loop() which decrements _loop_level
        loop_idx = self._loop_level - 1

        # Store stride in the loop body before popping, so it can be replaced when stringifying
        # The loop body is accessed via current_loop, which is the loop we're about to pop
        # We need to store n_regs in the loop body like ReadbackLoopBody does
        # But we're using standard LoopBody, so we'll store it in the loop body's label
        # and replace it when stringifying. Actually, we need a custom LoopBody class.
        # For now, let's store stride with a unique placeholder per loop instance
        # by using the loop's label, or we can use a dictionary keyed by loop instance.

        # Actually, the issue is that ReadbackLoopBody stores n_regs in the loop body itself,
        # and replaces it when __str__() is called. But we're storing strides globally.
        # The solution is to replace placeholders when we stringify each loop body,
        # not globally in finish(). But we can't easily do that without a custom LoopBody class.

        # For now, let's use a different approach: store stride in the loop body's pre_loop
        # attribute, which is preserved when stringifying. But that won't work because
        # we need to replace placeholders in the loop body's children.

        # Actually, I think the solution is to store stride per-loop-body instance.
        # Each loop body should have its own stride. When we pop_loop(), we store the stride
        # in the loop body that's being popped, then when that loop body is stringified,
        # it replaces its own placeholder.

        # Call super().pop_loop() which pops the loop body from the stack
        # After this, we can access the popped loop body to store stride
        loop_body = self.current_loop
        super().pop_loop()

        # Store stride in the loop body using a custom attribute
        # We'll need to replace placeholders when stringifying, but for now
        # let's store it and replace globally, but using loop-specific placeholders
        # Actually, let's use the loop's label to create a unique placeholder
        placeholder = f"$i{loop_idx}sz_{loop_body.label}"
        self._index_stride_stack.append((placeholder, n_indices))

        # Replace placeholder in loop body's children now (before it's popped)
        # Actually, we need to replace it after stringifying. Let's use a different approach.
        # We'll replace the placeholder in the loop body's string representation

        # Actually, the simplest fix is to replace placeholders immediately when popping,
        # in the loop body's children that we've already generated
        # But those are stored as strings, not loop bodies, so we can't easily do that.

        # For now, let's just use a unique placeholder per loop instance
        # We can use the loop's label to make it unique
        # But we need to use it in the generated code too, not just when storing

        # Actually wait - the issue is that we're using "$i0sz" in the generated code,
        # which is the same for all loops at level 0. But each loop should have its own stride!
        # The solution is to use the loop's label in the placeholder when generating code.

        # Let me check what the loop's label is - it's generated in LoopBody.__init__()
        # as f"gen_loop_{LoopBody._label_counter}", which is unique per loop instance.

        # So we can use the loop's label to create a unique placeholder!
        # But we need to use it when generating the code too, not just when storing.

        # Actually, I think the simpler solution is to replace placeholders when stringifying
        # each loop body, but we'd need a custom LoopBody class for that.

        # For now, let's try a different approach: don't use placeholders in the generated code
        # for outer loops. Instead, calculate the stride inline. But that requires knowing the
        # stride when generating, which we don't know yet.

        # Actually, the readback generator solves this by storing stride per-loop-body
        # in ReadbackLoopBody.n_regs, and replacing when __str__() is called.
        # We should do the same - use a custom LoopBody class that stores stride and
        # replaces placeholders when stringifying.

        # But for now, let's use a workaround: replace placeholders immediately in the
        # loop body's children before popping. We can iterate through loop_body.children
        # and replace placeholders in string children.
        for i, child in enumerate(loop_body.children):
            if isinstance(child, str):
                loop_body.children[i] = child.replace(f"$i{loop_idx}sz", str(n_indices))

        # Advance current_index to account for loop's contents (all instances)
        # Similar to readback generator: current_offset = start_offset + n_regs * dim
        # This happens AFTER we've calculated n_indices and stored/replaced the stride
        self.current_index = start_index + n_indices * dim

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
            # Store base index when entering array (for reference, but stride is calculated in pop_loop)
            self._base_index_stack.append(self.current_index)

        return WalkerAction.Continue

    def exit_AddressableComponent(self, node: "AddressableNode") -> None:
        super().exit_AddressableComponent(node)

        if not node.array_dimensions:
            return

        for _ in node.array_dimensions:
            self._array_stride_stack.pop()
            if self._base_index_stack:
                # Just pop - stride was already calculated in pop_loop()
                self._base_index_stack.pop()

    def start(self) -> None:
        """Initialize the generator with cpuif_index declaration."""
        super().start()
        self.push_top("integer cpuif_index;")
        self.push_top("")
        self.push_top("always @(*) begin")
        self.push_top("    cpuif_index = 0;")

    def finish(self) -> Optional[str]:
        """Close the always block and replace placeholder tokens."""
        self.add_content("end")
        result = super().finish()
        if result is None:
            return None
        # Replace placeholder tokens like $i0sz with actual stride values
        # Process in reverse order to handle nested loops correctly
        for placeholder, stride in reversed(self._index_stride_stack):
            result = result.replace(placeholder, str(stride))
        return result

    def _process_external_block(self, node: "AddressableNode") -> None:
        """
        Generate cpuif_index assignment for external blocks (regfile, addrmap, mem).
        All addresses within the block map to the same index since external blocks
        use a single shared rd_data signal.
        """
        addr_str = self._get_address_str(node)
        addr_width = self.addr_decode.exp.ds.addr_width
        block_size = node.size
        base_index = self.current_index

        # Generate address range check: all addresses in block map to same index
        addr_low = addr_str
        addr_high = f"{addr_str} + {SVInt(block_size - 1, addr_width)}"
        self.add_content(
            f"    if ((cpuif_addr >= {addr_low}) && (cpuif_addr <= {addr_high})) begin"
        )
        self.add_content(f"        cpuif_index = {base_index};")
        self.add_content("    end")
        # Increment index once for the single shared readback slot
        self.current_index += 1

    def enter_Regfile(self, node: "RegfileNode") -> Optional[WalkerAction]:
        if not self.policy.is_external(node):
            return WalkerAction.Continue

        self._process_external_block(node)
        return WalkerAction.SkipDescendants

    def enter_Addrmap(self, node: "AddrmapNode") -> Optional[WalkerAction]:
        if node == self.addr_decode.top_node:
            return WalkerAction.Continue

        if not self.policy.is_external(node):
            return WalkerAction.Continue

        self._process_external_block(node)
        return WalkerAction.SkipDescendants

    def enter_Mem(self, node: "MemNode") -> None:
        if not node.external:
            return

        # External memory: all entries map to the same index
        # External memory uses a single rd_data signal, so all entries
        # share the same readback array slot
        addr_str = self._get_address_str(node)
        addr_width = self.addr_decode.exp.ds.addr_width
        memwidth = node.get_property("memwidth")
        mementries = node.get_property("mementries")

        # Calculate address stride (bytes per entry)
        entry_stride = memwidth // 8

        base_index = self.current_index

        if len(self._array_stride_stack):
            # Arrayed memory - handled by loop structure
            # The loop will be generated by the parent, we just need to generate
            # the inner loop for memory entries
            pass
        else:
            # Single memory - generate for loop for each entry
            # All entries map to the same base_index (not base_index + loop_var)
            # because external memory uses a single rd_data signal
            # Use loop variable based on current nesting level to avoid shadowing
            loop_var = f"i{self._loop_level}"
            self.add_content(
                f"    for(int {loop_var}=0; {loop_var}<{mementries}; {loop_var}++) begin"
            )
            # Cast the entire expression to ensure consistent width
            entry_addr = f"({addr_width})'({addr_str} + ({addr_width})'({loop_var})*{SVInt(entry_stride, addr_width)})"
            self.add_content(f"        if (cpuif_addr == {entry_addr}) begin")
            self.add_content(f"            cpuif_index = {base_index};")
            self.add_content("        end")
            self.add_content("    end")
            # Only increment once for the single shared readback slot
            self.current_index += 1

    def enter_Reg(self, node: RegNode) -> Optional[WalkerAction]:
        # Skip registers inside external blocks (handled by parent)
        # But process standalone external registers (they still need indices)
        if is_inside_external_block(
            node, self.addr_decode.top_node, self.addr_decode.exp.ds
        ):
            return WalkerAction.SkipDescendants

        regwidth = node.get_property("regwidth")
        accesswidth = node.get_property("accesswidth")

        # Only generate index for readable or writable registers
        if not (node.has_sw_readable or node.has_sw_writable):
            return WalkerAction.SkipDescendants

        # External registers are handled the same way as normal registers for index calculation

        base_index = self.current_index

        # Use register's own array_dimensions, not parent array dimensions
        # IndexedPath includes parent array dimensions, but for cpuif_index we only
        # care about the register's own array dimensions
        array_dims = node.array_dimensions if node.array_dimensions else []

        # Check if we're already inside a loop created by enter_AddressableComponent for this register
        # If the register has array dimensions, enter_AddressableComponent creates a loop,
        # so we shouldn't generate another loop in enter_Reg
        already_in_register_loop = (
            array_dims and self._loop_level > 0 and self._loop_level <= len(array_dims)
        )

        # If we're inside an arrayed component (parent arrayed component, not this register's own loop),
        # we need to account for the outer loop variable
        # The index should be: base_index + i0*stride + register_offset
        # where stride is the number of indices used by each instance of the arrayed component
        # We use placeholders like $i0sz similar to readback generator, which are replaced later
        index_offset_str = ""
        if self._base_index_stack and not already_in_register_loop:
            # We're inside a parent arrayed component - need to add outer loop variable * stride
            # Use placeholder that will be replaced when we know the stride
            # loop_idx should match the loop variable index (0 for i0, 1 for i1, etc.)
            # _loop_level is the nesting level, so loop_idx = _loop_level - 1
            # But if we're inside this register's loop, _loop_level includes that loop, so we need to subtract it
            loop_idx = self._loop_level - 1 if self._loop_level > 0 else 0
            if already_in_register_loop:
                # We're inside the register's own loop, so parent loops are at lower indices
                loop_idx = self._loop_level - 2 if self._loop_level > 1 else 0
            index_offset_str = f" + i{loop_idx}*$i{loop_idx}sz"

        # Get base address (relative to top)
        base_addr = (
            node.raw_absolute_address - self.addr_decode.top_node.raw_absolute_address
        )
        addr_width = self.addr_decode.exp.ds.addr_width

        # Calculate address stride (bytes per register)
        # For register arrays, stride depends on whether the register is wide:
        # - Normal register: stride = accesswidth/8 (typically 4 bytes for 32-bit)
        # - Wide register: stride = regwidth/8 (typically 8 bytes for 64-bit accessed as 32-bit)
        # The array_stride_stack is for nested array dimensions, not register stride
        # For arrayed registers, we need the stride between array elements, which is the register width
        addr_stride = regwidth // 8  # Use regwidth for array stride, not accesswidth

        if regwidth == accesswidth:
            # Normal register (not wide)
            if array_dims and not already_in_register_loop:
                # Arrayed register - generate for loop for first dimension
                # For now, handle single dimension (most common case)
                dim = array_dims[0] if len(array_dims) > 0 else 1
                # Use loop variable based on current nesting level to avoid shadowing
                loop_var = f"i{self._loop_level}"
                # For arrayed registers, calculate the base address of the first register
                # by subtracting the array offset from the current register's address
                # The array offset is embedded in the node's address, so we need to extract it
                # For now, calculate first register base by getting address without array indexing
                # We need to get the address of the first register in the array
                reg_base_addr = (
                    node.raw_absolute_address
                    - self.addr_decode.top_node.raw_absolute_address
                )
                # If we're inside outer loops (arrayed components), _get_address_str includes those loop variables
                # So we need to construct the base address similarly but without the register array offset
                # Only include outer loop variables if we're actually inside an arrayed component (base_index_stack not empty)
                if self._base_index_stack:
                    # Include outer loop variables from parent arrayed components
                    # Use address width consistently and cast loop variables
                    base_addr_str = str(SVInt(reg_base_addr, addr_width))
                    expr_parts = [base_addr_str]
                    for i, stride in enumerate(self._array_stride_stack):
                        expr_parts.append(
                            f"({addr_width})'(i{i})*{SVInt(stride, addr_width)}"
                        )
                    # Cast the entire expression to ensure consistent width
                    first_reg_base_str = f"({addr_width})'({'+'.join(expr_parts)})"
                else:
                    first_reg_base_str = str(SVInt(reg_base_addr, addr_width))
                self.add_content(
                    f"    for(int {loop_var}=0; {loop_var}<{dim}; {loop_var}++) begin"
                )
                # Add register array offset to first register base
                # Cast the entire expression to ensure consistent width
                addr_expr = f"({addr_width})'({first_reg_base_str} + ({addr_width})'({loop_var})*{SVInt(addr_stride, addr_width)})"
                self.add_content(f"        if (cpuif_addr == {addr_expr}) begin")
                self.add_content(
                    f"            cpuif_index = {base_index} + {loop_var}{index_offset_str};"
                )
                self.add_content("        end")
                self.add_content("    end")
                # Advance index by array size
                total_size = 1
                for d in array_dims:
                    total_size *= d
                self.current_index += total_size
            elif array_dims and already_in_register_loop:
                # Arrayed register, but we're already inside a loop created by enter_AddressableComponent
                # The parent class already created the loop, so we just generate the address checks inside it
                # Use the current loop variable (from enter_AddressableComponent)
                dim = array_dims[0] if len(array_dims) > 0 else 1
                # The current loop variable is i{_loop_level - 1} because we're inside the loop
                loop_var = f"i{self._loop_level - 1}"
                # For arrayed registers, calculate the base address including outer loop variables
                reg_base_addr = (
                    node.raw_absolute_address
                    - self.addr_decode.top_node.raw_absolute_address
                )
                # When we're inside the register's own loop, we don't include outer loop variables
                # because the loop IS for this register's array dimensions
                # Cast the entire expression to ensure consistent width
                addr_expr = f"({addr_width})'({SVInt(reg_base_addr, addr_width)} + ({addr_width})'({loop_var})*{SVInt(addr_stride, addr_width)})"
                self.add_content(f"    if (cpuif_addr == {addr_expr}) begin")
                # When inside the register's own loop, index is just base + loop_var (no offset_str)
                self.add_content(f"        cpuif_index = {base_index} + {loop_var};")
                self.add_content("    end")
                # Don't advance current_index here - pop_loop() will advance it correctly
                # based on how many indices were used (n_indices * dim)
                # We only increment by 1 here to track that we processed this register
                self.current_index += 1
            else:
                # Single register - use _get_address_str to include outer loop variables
                addr_expr = self._get_address_str(node, 0)
                self.add_content(f"    if (cpuif_addr == {addr_expr}) begin")
                self.add_content(
                    f"        cpuif_index = {base_index}{index_offset_str};"
                )
                self.add_content("    end")
                self.current_index += 1
        else:
            # Wide register - generate index for each subword
            n_subwords = regwidth // accesswidth
            subword_stride = accesswidth // 8

            if array_dims and not already_in_register_loop:
                # Arrayed wide register - generate nested loops
                # Outer loop for array, inner for subwords
                dim = array_dims[0] if len(array_dims) > 0 else 1
                # Use loop variable based on current nesting level to avoid shadowing
                loop_var = f"i{self._loop_level}"
                for subword_idx in range(n_subwords):
                    # Use _get_address_str to include outer loop variables, then add subword and register array offsets
                    # For arrayed registers, calculate the base address including outer loops but not register array offset
                    if self._base_index_stack:
                        # Include outer loop variables from parent arrayed components
                        base_addr_str = self._get_address_str(
                            node, subword_idx * subword_stride
                        )
                        # Remove register array offset from base_addr_str since we'll add it with loop_var
                        # Actually, _get_address_str already includes everything, so we need to construct it differently
                        reg_base_addr = (
                            node.raw_absolute_address
                            - self.addr_decode.top_node.raw_absolute_address
                            + subword_idx * subword_stride
                        )
                        # Use address width consistently and cast loop variables
                        base_addr_str = str(SVInt(reg_base_addr, addr_width))
                        expr_parts = [base_addr_str]
                        for i, stride in enumerate(self._array_stride_stack):
                            expr_parts.append(
                                f"({addr_width})'(i{i})*{SVInt(stride, addr_width)}"
                            )
                        # Cast the entire expression to ensure consistent width
                        base_addr_str = f"({addr_width})'({'+'.join(expr_parts)})"
                    else:
                        base_addr_str = self._get_address_str(
                            node, subword_idx * subword_stride
                        )
                    self.add_content(
                        f"    for(int {loop_var}=0; {loop_var}<{dim}; {loop_var}++) begin"
                    )
                    addr_expr = (
                        f"{base_addr_str} + {loop_var}*{SVInt(addr_stride, addr_width)}"
                    )
                    self.add_content(f"        if (cpuif_addr == {addr_expr}) begin")
                    # Index = base + (array_index * n_subwords) + subword_index
                    self.add_content(
                        f"            cpuif_index = {base_index} + {loop_var}*{n_subwords} + {subword_idx}{index_offset_str};"
                    )
                    self.add_content("        end")
                    self.add_content("    end")
                # Advance index by array_size * n_subwords
                total_size = 1
                for d in array_dims:
                    total_size *= d
                self.current_index += total_size * n_subwords
            elif array_dims and already_in_register_loop:
                # Arrayed wide register, but we're already inside a loop created by enter_AddressableComponent
                # The parent class already created the loop, so we just generate the address checks inside it
                dim = array_dims[0] if len(array_dims) > 0 else 1
                # The current loop variable is i{_loop_level - 1} because we're inside the loop
                loop_var = f"i{self._loop_level - 1}"
                for subword_idx in range(n_subwords):
                    # For arrayed wide registers, calculate the base address
                    reg_base_addr = (
                        node.raw_absolute_address
                        - self.addr_decode.top_node.raw_absolute_address
                        + subword_idx * subword_stride
                    )
                    # When we're inside the register's own loop, we don't include outer loop variables
                    # Cast the entire expression to ensure consistent width
                    addr_expr = f"({addr_width})'({SVInt(reg_base_addr, addr_width)} + ({addr_width})'({loop_var})*{SVInt(addr_stride, addr_width)})"
                    self.add_content(f"    if (cpuif_addr == {addr_expr}) begin")
                    # When inside the register's own loop, index is base + loop_var*n_subwords + subword_idx
                    self.add_content(
                        f"        cpuif_index = {base_index} + {loop_var}*{n_subwords} + {subword_idx};"
                    )
                    self.add_content("    end")
                # Don't advance current_index here - pop_loop() will advance it correctly
                # based on how many indices were used (n_indices * dim)
                # We only increment by n_subwords here to track that we processed this register
                self.current_index += n_subwords
            else:
                # Single wide register - generate for each subword
                for subword_idx in range(n_subwords):
                    # Use _get_address_str to include outer loop variables, then add subword offset
                    addr_expr = self._get_address_str(
                        node, subword_idx * subword_stride
                    )
                    self.add_content(f"    if (cpuif_addr == {addr_expr}) begin")
                    self.add_content(
                        f"        cpuif_index = {base_index + subword_idx}{index_offset_str};"
                    )
                    self.add_content("    end")
                self.current_index += n_subwords

        return WalkerAction.SkipDescendants
