from __future__ import annotations

from systemrdl.node import FieldNode, RegNode, SignalNode
from systemrdl.rdltypes import AccessType
from systemrdl.walker import RDLListener, WalkerAction

from ..utils import external_policy
from .util import get_cdc_clk, is_cdc_reg


class CdcDesignValidator(RDLListener):
    def __init__(self, exp) -> None:
        self.exp = exp
        self.msg = exp.ds.top_node.env.msg
        self._domain_resets: dict[str, set[SignalNode | None]] = {}

    @property
    def top_node(self):
        return self.exp.ds.top_node

    def walk(self) -> None:
        if not self.exp.ds.has_cdc_regs:
            return
        from systemrdl.walker import RDLWalker

        RDLWalker().walk(self.top_node, self)

    def enter_Reg(self, node: RegNode) -> WalkerAction | None:
        if not is_cdc_reg(node):
            return WalkerAction.Continue

        policy = external_policy(self.exp.ds)
        if policy.is_external(node) or node.external:
            self.msg.error(
                "cdc_clk cannot be used on an external register",
                node.inst.inst_src_ref,
            )

        if node.is_array:
            self.msg.error(
                "Arrayed CDC registers are not supported yet",
                node.inst.inst_src_ref,
            )

        regwidth = node.get_property("regwidth")
        accesswidth = node.get_property("accesswidth")
        if regwidth != accesswidth:
            self.msg.error(
                "CDC registers require regwidth == accesswidth",
                node.inst.inst_src_ref,
            )

        if node.get_property("buffer_writes") and node.get_property("buffer_reads"):
            self.msg.error(
                "CDC register cannot enable both buffer_writes and buffer_reads",
                node.inst.inst_src_ref,
            )

        if self.exp.ds.retime_external_reg and is_cdc_reg(node):
            self.msg.error(
                "cdc_clk cannot be combined with --rt-external reg",
                node.inst.inst_src_ref,
            )

        clk = get_cdc_clk(node)
        assert clk is not None

        if node.get_property("buffer_writes", default=False):
            trigger = node.get_property("wbuffer_trigger")
            if isinstance(trigger, RegNode) and (
                not is_cdc_reg(trigger) or get_cdc_clk(trigger) != clk
            ):
                self.msg.error(
                    "CDC write-buffer trigger must be a CDC register in the same domain",
                    node.inst.inst_src_ref,
                )

        if node.get_property("buffer_reads", default=False):
            trigger = node.get_property("rbuffer_trigger")
            if isinstance(trigger, RegNode) and (
                not is_cdc_reg(trigger) or get_cdc_clk(trigger) != clk
            ):
                self.msg.error(
                    "CDC read-buffer trigger must be a CDC register in the same domain",
                    node.inst.inst_src_ref,
                )

        return WalkerAction.Continue

    def enter_Field(self, node: FieldNode) -> None:
        if not is_cdc_reg(node.parent):
            return

        hw = node.get_property("hw")
        if not (node.is_sw_readable or node.is_sw_writable):
            self.msg.error(
                f"CDC field '{node.inst_name}' has unsupported sw access",
                node.inst.inst_src_ref,
            )
        if hw not in {AccessType.r, AccessType.w, AccessType.na}:
            self.msg.error(
                f"CDC field '{node.inst_name}' has unsupported hw access",
                node.inst.inst_src_ref,
            )

        if (
            node.get_property("onread") is not None
            or node.get_property("onwrite") is not None
        ):
            self.msg.error(
                "onread/onwrite are not supported on CDC fields",
                node.inst.inst_src_ref,
            )
        banned = [
            "intr",
            "singlepulse",
            "paritycheck",
            "hwset",
            "hwclr",
            "swacc",
            "swmod",
        ]
        for prop in banned:
            if node.get_property(prop, default=False):
                self.msg.error(
                    f"Property '{prop}' is not supported on CDC fields",
                    node.inst.inst_src_ref,
                )

        if node.get_property("buffer_writes", default=False) and hw == AccessType.w:
            trig = node.parent.get_property("wbuffer_trigger")
            if isinstance(trig, RegNode) and trig != node.parent:
                self.msg.error(
                    "CDC write-group members cannot contain hw=w fields",
                    node.inst.inst_src_ref,
                )

        clk = get_cdc_clk(node.parent)
        assert clk is not None
        key = clk.get_path()
        rs = node.get_property("resetsignal")
        bucket = self._domain_resets.setdefault(key, set())
        bucket.add(rs)

    def exit_Addrmap(self, node) -> None:
        if node != self.top_node:
            return
        for resets in self._domain_resets.values():
            if len(resets) > 1:
                self.msg.error(
                    "All fields in a CDC domain must share the same resetsignal (or none)",
                    self.top_node.inst.def_src_ref,
                )
