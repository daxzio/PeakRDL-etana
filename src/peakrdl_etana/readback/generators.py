from typing import TYPE_CHECKING, List

from systemrdl.node import RegNode, MemNode, AddressableNode
from systemrdl.walker import WalkerAction

from ..forloop_generator import RDLForLoopGenerator, LoopBody

from ..utils import (
    do_bitswap,
    do_slice,
    is_inside_external_block,
    external_policy,
    has_sw_readable_descendants,
)

if TYPE_CHECKING:
    from systemrdl.node import RegfileNode, AddrmapNode
    from ..exporter import RegblockExporter


class ReadbackLoopBody(LoopBody):
    def __init__(self, dim: int, iterator: str, i_type: str) -> None:
        super().__init__(dim, iterator, i_type)
        self.n_regs = 0

    def __str__(self) -> str:
        # replace $i#sz token when stringifying
        s = super().__str__()
        token = f"${self.iterator}sz"
        s = s.replace(token, str(self.n_regs))
        return s


class ReadbackAssignmentGenerator(RDLForLoopGenerator):
    i_type = "genvar"
    loop_body_cls = ReadbackLoopBody  # type: ignore[assignment]

    def __init__(self, exp: "RegblockExporter") -> None:
        super().__init__()
        self.exp = exp
        self.policy = external_policy(self.exp.ds)

        # The readback array collects all possible readback values into a flat
        # array. The array width is equal to the CPUIF bus width. Each entry in
        # the array represents an aligned read access.
        self.current_offset = 0
        self.start_offset_stack: List[int] = []
        self.dim_stack: List[int] = []

    @property
    def current_offset_str(self) -> str:
        """
        Derive a string that represents the current offset being assigned.
        This consists of:
        - The current integer offset
        - multiplied index of any enclosing loop

        The integer offset from "current_offset" is static and is monotonically
        incremented as more register assignments are processed.

        The component of the offset from loops is added by multiplying the current
        loop index by the loop size.
        Since the loop's size is not known at this time, it is emitted as a
        placeholder token like: $i0sz, $i1sz, $i2sz, etc
        These tokens can be replaced once the loop body has been completed and the
        size of its contents is known.
        """
        offset_parts = []
        for i in range(self._loop_level):
            offset_parts.append(f"i{i}*$i{i}sz")
        offset_parts.append(str(self.current_offset))
        return " + ".join(offset_parts)

    def push_loop(self, dim: int) -> None:
        super().push_loop(dim)
        self.start_offset_stack.append(self.current_offset)
        self.dim_stack.append(dim)

    def pop_loop(self) -> None:
        start_offset = self.start_offset_stack.pop()
        dim = self.dim_stack.pop()

        # Number of registers enclosed in this loop
        n_regs = self.current_offset - start_offset
        self.current_loop.n_regs = n_regs  # type: ignore

        super().pop_loop()

        # Advance current scope's offset to account for loop's contents
        self.current_offset = start_offset + n_regs * dim

    def enter_AddressableComponent(self, node: "AddressableNode") -> WalkerAction:
        super().enter_AddressableComponent(node)
        self.strb = self.exp.hwif.get_external_rd_ack(node, True)
        return WalkerAction.Continue

    def enter_Mem(self, node: "MemNode") -> WalkerAction:
        if node.external:
            # Only generate readback for sw-readable memories (skip write-only)
            if node.is_sw_readable:
                strb = self.exp.hwif.get_external_rd_ack(node, True)
                data = self.exp.hwif.get_external_rd_data(node, True)
                self.add_content(
                    f"assign readback_array[{self.current_offset_str}] = {strb} ? {data} : '0;"
                )
                self.current_offset += 1
            return WalkerAction.SkipDescendants
        return WalkerAction.Continue

    def enter_Regfile(self, node: "RegfileNode") -> WalkerAction:
        # For external regfiles, use bus interface readback
        self.policy = external_policy(self.exp.ds)
        if self.policy.is_external(node):
            # Only generate readback for sw-readable regfiles (skip write-only)
            if has_sw_readable_descendants(node):
                self.process_external_block(node)
            return WalkerAction.SkipDescendants
        return WalkerAction.Continue

    def enter_Addrmap(self, node: "AddrmapNode") -> WalkerAction:
        # Skip top-level
        if node == self.exp.ds.top_node:
            return WalkerAction.Continue

        # For external addrmaps, use bus interface readback
        if self.policy.is_external(node):
            # Only generate readback for sw-readable addrmaps (skip write-only)
            if has_sw_readable_descendants(node):
                self.process_external_block(node)
            return WalkerAction.SkipDescendants
        return WalkerAction.Continue

    def enter_Reg(self, node: RegNode) -> WalkerAction:
        if not node.has_sw_readable:
            return WalkerAction.SkipDescendants

        # Skip external registers - they use external rd_data protocol
        # External modules handle their own buffering
        if node.external:
            # External registers always generate ONE readback entry (not per-subword)
            # For wide external registers, the external module handles subword access
            # and returns the appropriate data via rd_ack/rd_data
            self.process_reg(node)
            return WalkerAction.SkipDescendants

        # Check if this register is inside an external regfile/addrmap
        # If so, skip it - the parent external block handles the readback
        if is_inside_external_block(node, self.exp.ds.top_node, self.exp.ds):
            return WalkerAction.SkipDescendants

        accesswidth = node.get_property("accesswidth")
        regwidth = node.get_property("regwidth")
        rbuf = node.get_property("buffer_reads", default=False)
        if rbuf:
            trigger = node.get_property("rbuffer_trigger")
            is_own_trigger = isinstance(trigger, RegNode) and trigger == node
            if is_own_trigger:
                if accesswidth < regwidth:
                    self.process_buffered_reg_with_bypass(node, regwidth, accesswidth)
                else:
                    # bypass cancels out. Behaves like a normal reg
                    self.process_reg(node)
            else:
                self.process_buffered_reg(node, regwidth, accesswidth)
        elif accesswidth < regwidth:
            self.process_wide_reg(node, accesswidth)
        else:
            self.process_reg(node)

        return WalkerAction.SkipDescendants

    def process_external_block(self, node: "AddressableNode") -> None:
        """Handle readback for external regfile, addrmap, or mem blocks."""
        # Use the bus interface rd_data and rd_ack signals
        rd_data = self.exp.hwif.get_external_rd_data(node, True)
        rd_ack = self.exp.hwif.get_external_rd_ack(node, True)

        # External block rd_data might be wider than accesswidth if it contains
        # registers wider than the bus. Slice to accesswidth.
        bus_width = self.exp.cpuif.data_width
        # For external blocks, the rd_data width is typically cpuif.data_width,
        # but could be wider if internal registers are wider
        # Slice to match readback_array entry width
        if bus_width < 32:  # If we have a narrow bus
            rd_data_sliced = f"{rd_data}[{bus_width-1}:0]"
        else:
            rd_data_sliced = rd_data

        self.add_content(
            f"assign readback_array[{self.current_offset_str}] = {rd_ack} ? {rd_data_sliced} : '0;"
        )
        self.current_offset += 1

    def process_external_reg(self, node: RegNode) -> None:
        regwidth = node.get_property("regwidth")
        if regwidth < self.exp.cpuif.data_width:
            raise

    def process_reg(self, node: RegNode) -> None:
        # Note: regwidth can be less than cpuif.data_width for narrow registers
        # The readback logic below handles padding automatically

        # Special handling for single-field external registers (wide or not)
        # For these, the rd_data signal is register-level (not field-level)
        if self.policy.is_external(node):
            # Check if this is a single-field register
            n_sw_readable_fields = sum(1 for f in node.fields() if f.is_sw_readable)
            if n_sw_readable_fields == 1:
                # Single-field external register
                # The rd_data signal is register-level, assign the full signal
                regwidth = node.get_property("regwidth")
                rd_data = self.exp.hwif.get_external_rd_data(node, True)
                rd_ack = self.exp.hwif.get_external_rd_ack(node, True)

                if regwidth < self.exp.cpuif.data_width:
                    self.add_content(
                        f"assign readback_array[{self.current_offset_str}][{regwidth-1}:0] = {rd_ack} ? {rd_data} : '0;"
                    )
                    self.add_content(
                        f"assign readback_array[{self.current_offset_str}][{self.exp.cpuif.data_width-1}:{regwidth}] = '0;"
                    )
                else:
                    self.add_content(
                        f"assign readback_array[{self.current_offset_str}] = {rd_ack} ? {rd_data} : '0;"
                    )
                self.current_offset += 1
                return

        current_bit = 0
        p = self.exp.dereferencer.get_access_strobe(node)
        if self.policy.is_external(node):
            rd_strb = self.exp.hwif.get_external_rd_ack(node, True)
        else:
            rd_strb = f"({p.path}{p.index_str} && !decoded_req_is_wr)"
        # Fields are sorted by ascending low bit
        for field in node.fields():
            if not field.is_sw_readable:
                continue

            # insert reserved assignment before this field if needed
            if field.low != current_bit:
                self.add_content(
                    f"assign readback_array[{self.current_offset_str}][{field.low-1}:{current_bit}] = '0;"
                )

            if self.policy.is_external(node):
                value = self.exp.hwif.get_external_rd_data(field, True)
            else:
                value = self.exp.dereferencer.get_value(field)  # type: ignore[assignment]
            if field.msb < field.lsb:
                # Field gets bitswapped since it is in [low:high] orientation
                value = do_bitswap(value, field.width)  # type: ignore[assignment]

            self.add_content(
                f"assign readback_array[{self.current_offset_str}][{field.high}:{field.low}] = {rd_strb} ? {value} : '0;"
            )

            current_bit = field.high + 1

        # Insert final reserved assignment if needed
        bus_width = self.exp.cpuif.data_width
        if current_bit < bus_width:
            self.add_content(
                f"assign readback_array[{self.current_offset_str}][{bus_width-1}:{current_bit}] = '0;"
            )

        self.current_offset += 1

    def process_buffered_reg(
        self, node: RegNode, regwidth: int, accesswidth: int
    ) -> None:
        rbuf = self.exp.read_buffering.get_rbuf_data(node)

        if accesswidth < regwidth:
            # Is wide reg
            n_subwords = regwidth // accesswidth
            astrb = self.exp.dereferencer.get_access_strobe(
                node, reduce_substrobes=False
            )
            for i in range(n_subwords):
                rd_strb = f"({astrb.path}[{i}] && !decoded_req_is_wr)"
                bslice = f"[{(i + 1) * accesswidth - 1}:{i*accesswidth}]"
                self.add_content(
                    f"assign readback_array[{self.current_offset_str}] = {rd_strb} ? {rbuf}{bslice} : '0;"
                )
                self.current_offset += 1

        else:
            # Is regular reg
            p = self.exp.dereferencer.get_access_strobe(node)
            rd_strb = f"({p.path} && !decoded_req_is_wr)"
            self.add_content(
                f"assign readback_array[{self.current_offset_str}][{regwidth-1}:0] = {rd_strb} ? {rbuf} : '0;"
            )

            bus_width = self.exp.cpuif.data_width
            if regwidth < bus_width:
                self.add_content(
                    f"assign readback_array[{self.current_offset_str}][{bus_width-1}:{regwidth}] = '0;"
                )

            self.current_offset += 1

    def process_buffered_reg_with_bypass(
        self, node: RegNode, regwidth: int, accesswidth: int
    ) -> None:
        """
        Special case for a buffered register when the register is its own trigger.
        First sub-word shall bypass the read buffer and assign directly.
        Subsequent subwords assign from the buffer.
        Caller guarantees this is a wide reg
        """
        astrb = self.exp.dereferencer.get_access_strobe(node, reduce_substrobes=False)

        # Generate assignments for first sub-word
        bidx = 0
        rd_strb = f"({astrb.path}[0] && !decoded_req_is_wr)"
        for field in node.fields():
            if not field.is_sw_readable:
                continue

            if field.low >= accesswidth:
                # field is not in this subword.
                break

            if bidx < field.low:
                # insert padding before
                self.add_content(
                    f"assign readback_array[{self.current_offset_str}][{field.low - 1}:{bidx}] = '0;"
                )

            if field.high >= accesswidth:
                # field gets truncated
                r_low = field.low
                r_high = accesswidth - 1
                f_low = 0
                f_high = accesswidth - 1 - field.low

                if field.msb < field.lsb:
                    # Field gets bitswapped since it is in [low:high] orientation
                    # Mirror the low/high indexes
                    f_low = field.width - 1 - f_low
                    f_high = field.width - 1 - f_high
                    f_low, f_high = f_high, f_low
                    value = do_bitswap(
                        do_slice(self.exp.dereferencer.get_value(field), f_high, f_low),
                        f_high - f_low + 1,
                    )
                else:
                    value = do_slice(
                        self.exp.dereferencer.get_value(field), f_high, f_low
                    )

                self.add_content(
                    f"assign readback_array[{self.current_offset_str}][{r_high}:{r_low}] = {rd_strb} ? {value} : '0;"
                )
                bidx = accesswidth
            else:
                # field fits in subword
                value = self.exp.dereferencer.get_value(field)
                if field.msb < field.lsb:
                    # Field gets bitswapped since it is in [low:high] orientation
                    value = do_bitswap(value, field.width)
                self.add_content(
                    f"assign readback_array[{self.current_offset_str}][{field.high}:{field.low}] = {rd_strb} ? {value} : '0;"
                )
                bidx = field.high + 1

        # pad up remainder of subword
        if bidx < accesswidth:
            self.add_content(
                f"assign readback_array[{self.current_offset_str}][{accesswidth-1}:{bidx}] = '0;"
            )
        self.current_offset += 1

        # Assign remainder of subwords from read buffer
        n_subwords = regwidth // accesswidth
        rbuf = self.exp.read_buffering.get_rbuf_data(node)
        for i in range(1, n_subwords):
            # Include array indices before subword index
            array_indices = astrb.index_str if astrb.index_str else ""
            rd_strb = f"({astrb.path}{array_indices}[{i}] && !decoded_req_is_wr)"
            bslice = f"[{(i + 1) * accesswidth - 1}:{i*accesswidth}]"
            self.add_content(
                f"assign readback_array[{self.current_offset_str}] = {rd_strb} ? {rbuf}{bslice} : '0;"
            )
            self.current_offset += 1

    def process_wide_reg(self, node: RegNode, accesswidth: int) -> None:
        bus_width = self.exp.cpuif.data_width

        # For external wide registers, use simpler bus interface readback
        if self.policy.is_external(node):
            n_subwords = node.get_property("regwidth") // accesswidth
            rd_data = self.exp.hwif.get_external_rd_data(node, True)
            rd_ack = self.exp.hwif.get_external_rd_ack(node, True)

            # For external registers with buffering enabled, they still don't get
            # buffer logic generated (handled by external module), but we need to handle
            # readback correctly by checking which subword is being accessed
            astrb = self.exp.dereferencer.get_access_strobe(
                node, reduce_substrobes=False
            )

            for subword_idx in range(n_subwords):
                # Each subword gets its own readback entry
                # For external registers, rd_data is accesswidth-sized, not regwidth
                # The external module returns only the accessed subword (32-bit)
                rd_strb = f"({rd_ack} && {astrb.path}{astrb.index_str}[{subword_idx}])"
                # rd_data is accesswidth wide (32-bit), return full signal
                if accesswidth < bus_width:
                    self.add_content(
                        f"assign readback_array[{self.current_offset_str}][{accesswidth-1}:0] = {rd_strb} ? {rd_data} : '0;"
                    )
                else:
                    self.add_content(
                        f"assign readback_array[{self.current_offset_str}] = {rd_strb} ? {rd_data} : '0;"
                    )
                self.current_offset += 1
            return

        subword_idx = 0
        current_bit = 0  # Bit-offset within the wide register
        # Fields are sorted by ascending low bit
        for field in node.fields():
            if not field.is_sw_readable:
                continue

            # insert zero assignment before this field if needed
            if field.low >= accesswidth * (subword_idx + 1):
                # field does not start in this subword
                if current_bit > accesswidth * subword_idx:
                    # current subword had content. Assign remainder
                    low = current_bit % accesswidth
                    high = bus_width - 1
                    self.add_content(
                        f"assign readback_array[{self.current_offset_str}][{high}:{low}] = '0;"
                    )
                    self.current_offset += 1

                # Advance to subword that contains the start of the field
                subword_idx = field.low // accesswidth
                current_bit = accesswidth * subword_idx

            if current_bit != field.low:
                # assign zero up to start of this field
                low = current_bit % accesswidth
                high = (field.low % accesswidth) - 1
                self.add_content(
                    f"assign readback_array[{self.current_offset_str}][{high}:{low}] = '0;"
                )
                current_bit = field.low

            # Assign field
            # loop until the entire field's assignments have been generated
            field_pos = field.low
            while current_bit <= field.high:
                # Assign the field
                # For external registers, use rd_ack; for internal, use access strobe
                if self.policy.is_external(node):
                    rd_strb = self.exp.hwif.get_external_rd_ack(node, True)
                else:
                    # Rebuild strobe path for each subword to include correct subword index
                    current_access_strb = self.exp.dereferencer.get_access_strobe(
                        node, reduce_substrobes=False
                    )
                    array_indices = (
                        current_access_strb.index_str
                        if current_access_strb.index_str
                        else ""
                    )
                    rd_strb = f"({current_access_strb.path}{array_indices}[{subword_idx}] && !decoded_req_is_wr)"
                if (field_pos == field.low) and (
                    field.high < accesswidth * (subword_idx + 1)
                ):
                    # entire field fits into this subword
                    low = field.low - accesswidth * subword_idx
                    high = field.high - accesswidth * subword_idx

                    # For external registers, use external rd_data; for internal, use dereferencer
                    if self.policy.is_external(node):
                        value = self.exp.hwif.get_external_rd_data(field, True)
                    else:
                        value = self.exp.dereferencer.get_value(field)  # type: ignore[assignment]
                    if field.msb < field.lsb:
                        # Field gets bitswapped since it is in [low:high] orientation
                        value = do_bitswap(value, field.width)  # type: ignore[assignment]

                    self.add_content(
                        f"assign readback_array[{self.current_offset_str}][{high}:{low}] = {rd_strb} ? {value} : '0;"
                    )

                    current_bit = field.high + 1

                    if current_bit == accesswidth * (subword_idx + 1):
                        # Field ends at the subword boundary
                        subword_idx += 1
                        self.current_offset += 1
                elif field.high >= accesswidth * (subword_idx + 1):
                    # only a subset of the field can fit into this subword
                    # high end gets truncated

                    # assignment slice
                    r_low = field_pos - accesswidth * subword_idx
                    r_high = accesswidth - 1

                    # field slice
                    f_low = field_pos - field.low
                    f_high = accesswidth * (subword_idx + 1) - 1 - field.low

                    if field.msb < field.lsb:
                        # Field gets bitswapped since it is in [low:high] orientation
                        # Mirror the low/high indexes
                        f_low = field.width - 1 - f_low
                        f_high = field.width - 1 - f_high
                        f_low, f_high = f_high, f_low

                        # For external registers, use external rd_data; for internal, use dereferencer
                        if self.policy.is_external(node):
                            field_value = self.exp.hwif.get_external_rd_data(
                                field, True
                            )
                        else:
                            field_value = self.exp.dereferencer.get_value(field)  # type: ignore[assignment]
                        value = do_bitswap(  # type: ignore[assignment]
                            do_slice(field_value, f_high, f_low),
                            f_high - f_low + 1,
                        )
                    else:
                        # For external registers, use external rd_data; for internal, use dereferencer
                        if self.policy.is_external(node):
                            field_value = self.exp.hwif.get_external_rd_data(
                                field, True
                            )
                        else:
                            field_value = self.exp.dereferencer.get_value(field)  # type: ignore[assignment]
                        value = do_slice(field_value, f_high, f_low)  # type: ignore[assignment]

                    self.add_content(
                        f"assign readback_array[{self.current_offset_str}][{r_high}:{r_low}] = {rd_strb} ? {value} : '0;"
                    )

                    # advance to the next subword
                    subword_idx += 1
                    current_bit = accesswidth * subword_idx
                    field_pos = current_bit
                    self.current_offset += 1
                else:
                    # only a subset of the field can fit into this subword
                    # finish field

                    # assignment slice
                    r_low = field_pos - accesswidth * subword_idx
                    r_high = field.high - accesswidth * subword_idx

                    # field slice
                    f_low = field_pos - field.low
                    f_high = field.high - field.low

                    if field.msb < field.lsb:
                        # Field gets bitswapped since it is in [low:high] orientation
                        # Mirror the low/high indexes
                        f_low = field.width - 1 - f_low
                        f_high = field.width - 1 - f_high
                        f_low, f_high = f_high, f_low

                        # For external registers, use external rd_data; for internal, use dereferencer
                        if self.policy.is_external(node):
                            field_value = self.exp.hwif.get_external_rd_data(
                                field, True
                            )
                        else:
                            field_value = self.exp.dereferencer.get_value(field)  # type: ignore[assignment]
                        value = do_bitswap(  # type: ignore[assignment]
                            do_slice(field_value, f_high, f_low),
                            f_high - f_low + 1,
                        )
                    else:
                        # For external registers, use external rd_data; for internal, use dereferencer
                        if self.policy.is_external(node):
                            field_value = self.exp.hwif.get_external_rd_data(
                                field, True
                            )
                        else:
                            field_value = self.exp.dereferencer.get_value(field)  # type: ignore[assignment]
                        value = do_slice(field_value, f_high, f_low)  # type: ignore[assignment]

                    self.add_content(
                        f"assign readback_array[{self.current_offset_str}][{r_high}:{r_low}] = {rd_strb} ? {value} : '0;"
                    )

                    current_bit = field.high + 1
                    if current_bit == accesswidth * (subword_idx + 1):
                        # Field ends at the subword boundary
                        subword_idx += 1
                        self.current_offset += 1

        # insert zero assignment after the last field if needed
        if current_bit > accesswidth * subword_idx:
            # current subword had content. Assign remainder
            low = current_bit % accesswidth
            high = bus_width - 1
            self.add_content(
                f"assign readback_array[{self.current_offset_str}][{high}:{low}] = '0;"
            )
            self.current_offset += 1

        # Handle any remaining empty subwords
        expected_subwords = node.get_property("regwidth") // accesswidth
        for remaining_subword_idx in range(subword_idx, expected_subwords):
            # Create conditional zero assignment for empty subword using correct strobe
            current_access_strb = self.exp.dereferencer.get_access_strobe(
                node, reduce_substrobes=False
            )
            array_indices = (
                current_access_strb.index_str if current_access_strb.index_str else ""
            )
            rd_strb = f"({current_access_strb.path}{array_indices}[{remaining_subword_idx}] && !decoded_req_is_wr)"

            self.add_content(
                f"assign readback_array[{self.current_offset_str}] = {rd_strb} ? {bus_width}'h0 : '0;"
            )
            self.current_offset += 1
