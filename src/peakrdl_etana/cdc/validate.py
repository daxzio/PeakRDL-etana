from __future__ import annotations

import re

from systemrdl.node import FieldNode, Node, RegNode, SignalNode
from systemrdl.rdltypes import AccessType, PropertyReference
from systemrdl.walker import RDLListener, RDLWalker, WalkerAction

from ..identifier_filter import kw_filter as kwf
from ..utils import external_policy
from .model import CdcRegClass
from .util import cdc_reg_class, cdc_reg_domain_key, get_cdc_clk, is_cdc_reg

CLOCK_FORBIDDEN_PROPS = (
    "cpuif_reset",
    "field_reset",
    "activelow",
    "activehigh",
    "sync",
    "async",
)
CLOCK_ONLY_PROPS = ("cdc_nstages", "cdc_fast_mode_en")
BANNED_FIELD_PROPS = (
    "intr",
    "singlepulse",
    "paritycheck",
    "hwset",
    "hwclr",
    "swacc",
    "swmod",
    "counter",
    "we",
    "wel",
    "swwe",
    "swwel",
    "anded",
    "ored",
    "xored",
    "hwenable",
    "hwmask",
    "sticky",
    "stickybit",
    "rclr",
    "rset",
    "next",
)
TRIGGER_CLASSES = (CdcRegClass.WRITE_TRIGGER, CdcRegClass.READ_TRIGGER)
MEMBER_CLASSES = (CdcRegClass.WRITE_MEMBER, CdcRegClass.READ_MEMBER)


def _in_array(node: Node) -> bool:
    cur: Node | None = node
    while cur is not None:
        if getattr(cur, "is_array", False):
            return True
        cur = cur.parent
    return False


def _port_names(declaration: str) -> list[str]:
    """Port names in a CPU interface port declaration: the last identifier of each entry."""
    names = []
    for entry in declaration.split(","):
        match = re.search(r"(\w+)\s*(?:\[[^\]]*\]\s*)*$", entry.strip())
        if match:
            names.append(match.group(1))
    return names


def _field_kind(node: FieldNode) -> str | None:
    """'config', 'status', or None for an unsupported sw/hw combination."""
    sw = node.get_property("sw")
    hw = node.get_property("hw")
    if sw in (AccessType.rw, AccessType.w) and hw in (AccessType.r, AccessType.na):
        return "config"
    if sw == AccessType.r and hw == AccessType.w:
        return "status"
    return None


class CdcDesignValidator(RDLListener):
    def __init__(self, exp) -> None:
        self.exp = exp
        self.msg = exp.ds.top_node.env.msg

    @property
    def top_node(self):
        return self.exp.ds.top_node

    def walk(self) -> None:
        RDLWalker().walk(self.top_node, self)

    def _cdc_reg(self, node: RegNode):
        return self.exp.ds.cdc_domains[cdc_reg_domain_key(node)].reg(node)

    def enter_Component(self, node: Node) -> None:
        if not self.exp.ds.has_cdc_regs:
            return
        for prop in node.list_properties():
            target = node.get_property(prop)
            if isinstance(target, PropertyReference):
                target = target.node
            if not isinstance(target, Node):
                continue
            src_ref = node.inst.property_src_ref.get(prop, node.inst.inst_src_ref)
            self._check_reference(node, prop, target, src_ref)

    def _check_reference(self, node: Node, prop: str, target: Node, src_ref) -> None:
        if (
            isinstance(target, SignalNode)
            and target.get_path() in self.exp.ds.cdc_clock_signals
            and prop != "cdc_clk"
        ):
            self.msg.error(
                f"cdc_clk signal cannot be referenced by '{prop}' "
                f"(signal '{target.inst_name}')",
                src_ref,
            )
        if isinstance(target, FieldNode) and is_cdc_reg(target.parent):
            owner = node.parent if isinstance(node, FieldNode) else node
            if owner != target.parent:
                self.msg.error(
                    f"Property '{prop}' cannot reference a field of a CDC register "
                    f"('{target.get_path()}') from outside that register",
                    src_ref,
                )

    def enter_Signal(self, node: SignalNode) -> None:
        for prop in CLOCK_ONLY_PROPS:
            if prop in node.list_properties() and (
                node.get_path() not in self.exp.ds.cdc_clock_signals
            ):
                self.msg.error(
                    f"Signal '{node.inst_name}' sets {prop} but is not used as cdc_clk "
                    "by any register",
                    node.inst.property_src_ref.get(prop, node.inst.inst_src_ref),
                )

    def enter_Reg(self, node: RegNode) -> WalkerAction | None:
        if not is_cdc_reg(node):
            return WalkerAction.Continue

        policy = external_policy(self.exp.ds)
        if policy.is_external(node) or node.external:
            self.msg.error(
                "cdc_clk cannot be used on an external register",
                node.inst.inst_src_ref,
            )

        regwidth = node.get_property("regwidth")
        accesswidth = node.get_property("accesswidth")
        if regwidth > accesswidth and cdc_reg_class(node) not in MEMBER_CLASSES:
            self.msg.error(
                f"CDC register '{node.inst_name}' is wider than accesswidth "
                f"(regwidth {regwidth}, accesswidth {accesswidth})",
                node.inst.inst_src_ref,
            )

        if node.get_property("buffer_writes") and node.get_property("buffer_reads"):
            self.msg.error(
                "CDC register cannot enable both buffer_writes and buffer_reads",
                node.inst.inst_src_ref,
            )

        if self.exp.ds.retime_external_reg:
            self.msg.error(
                "cdc_clk cannot be combined with --rt-external reg",
                node.inst.inst_src_ref,
            )

        for kind, buf, trig in (
            ("write", "buffer_writes", "wbuffer_trigger"),
            ("read", "buffer_reads", "rbuffer_trigger"),
        ):
            if node.get_property(buf, default=False):
                self._check_trigger(node, kind, buf, node.get_property(trig))

        if self._cdc_reg(node).cls in TRIGGER_CLASSES and _in_array(node):
            self.msg.error(
                "CDC trigger cannot be an array element or inside an arrayed regfile",
                node.inst.inst_src_ref,
            )

        return WalkerAction.Continue

    def _check_trigger(self, node: RegNode, kind: str, buf: str, trigger) -> None:
        if not isinstance(trigger, RegNode):
            self.msg.error(
                f"CDC {kind}-buffer trigger must be a register "
                f"(register '{node.inst_name}' names a field, signal or property reference)",
                node.inst.property_src_ref.get(
                    f"{kind[0]}buffer_trigger", node.inst.inst_src_ref
                ),
            )
            return
        if not is_cdc_reg(trigger) or get_cdc_clk(trigger) != get_cdc_clk(node):
            self.msg.error(
                f"CDC {kind}-buffer trigger must be a CDC register in the same domain",
                node.inst.inst_src_ref,
            )
        elif not trigger.get_property(buf, default=False):
            self.msg.error(
                f"CDC {kind}-buffer trigger must set {buf} "
                f"(trigger '{trigger.inst_name}' of '{node.inst_name}')",
                node.inst.inst_src_ref,
            )
        elif cdc_reg_class(trigger) not in TRIGGER_CLASSES:
            self.msg.error(
                f"CDC {kind}-buffer trigger must be its own trigger "
                f"(trigger '{trigger.inst_name}' of '{node.inst_name}' is a group member)",
                node.inst.inst_src_ref,
            )

    def enter_Field(self, node: FieldNode) -> None:
        if not is_cdc_reg(node.parent):
            return

        parent = node.parent
        if (
            parent.get_property("regwidth") > parent.get_property("accesswidth")
            and node.msb < node.lsb
        ):
            self.msg.error(
                f"msb0 field '{node.inst_name}' is not supported in a CDC register "
                "wider than accesswidth",
                node.inst.inst_src_ref,
            )

        kind = _field_kind(node)
        if kind is None:
            self.msg.error(
                f"unsupported access for a CDC field '{node.inst_name}' "
                f"(sw={node.get_property('sw').name}, hw={node.get_property('hw').name}); "
                "allowed: config (sw=rw|w, hw=r|na) and status (sw=r, hw=w)",
                node.inst.inst_src_ref,
            )
        else:
            cls = self._cdc_reg(node.parent).cls
            if cls == CdcRegClass.WRITE_MEMBER and kind == "status":
                self.msg.error(
                    f"CDC write-group member cannot have status field '{node.inst_name}'",
                    node.inst.inst_src_ref,
                )
            if cls == CdcRegClass.READ_MEMBER and kind == "config":
                self.msg.error(
                    f"CDC read-group member cannot have config field '{node.inst_name}'",
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
        for prop in BANNED_FIELD_PROPS:
            if node.get_property(prop, default=False):
                self.msg.error(
                    f"Property '{prop}' is not supported on CDC fields",
                    node.inst.inst_src_ref,
                )
        reset = node.get_property("reset")
        if reset is not None and not isinstance(reset, int):
            self.msg.error(
                f"reset of CDC field '{node.inst_name}' must be a constant",
                node.inst.property_src_ref.get("reset", node.inst.inst_src_ref),
            )

        if node.get_property("resetsignal") is not None:
            self.msg.error(
                f"resetsignal is not supported on CDC field '{node.inst_name}'",
                node.inst.property_src_ref.get("resetsignal", node.inst.inst_src_ref),
            )

    def exit_Addrmap(self, node) -> None:
        if node != self.top_node:
            return
        for clk in self.exp.ds.cdc_clock_signals.values():
            self._check_clock(clk)
        self._check_collisions()

    def _check_clock(self, clk: SignalNode) -> None:
        src_ref = clk.inst.inst_src_ref
        if (clk.width or 1) > 1:
            self.msg.error(
                f"cdc_clk signal must be a single bit (signal '{clk.inst_name}')",
                src_ref,
            )
        if _in_array(clk):
            self.msg.error(
                f"cdc_clk signal cannot be declared inside an arrayed component "
                f"(signal '{clk.get_path()}')",
                src_ref,
            )
        assigned = clk.list_properties()
        for prop in CLOCK_FORBIDDEN_PROPS:
            if prop in assigned:
                self.msg.error(
                    f"cdc_clk signal cannot set '{prop}' (signal '{clk.inst_name}')",
                    clk.inst.property_src_ref.get(prop, src_ref),
                )

    def _check_collisions(self) -> None:
        """Reject clock ports that repeat a port name, and ports that equal a generated port
        or begin a generated prefix."""
        ds = self.exp.ds
        ports: dict[str, str] = {
            "clk": "the bus clock",
            self.exp.dereferencer.default_resetsignal_name: "the bus reset",
        }
        for name in _port_names(self.exp.cpuif.port_declaration):
            ports.setdefault(name, "a CPU interface port")
        for sig in ds.out_of_hier_signals.values():
            ports[kwf(sig.inst_name)] = f"signal '{sig.inst_name}'"

        # Domains are keyed by signal path but named by instance name
        clocks: dict[str, list[SignalNode]] = {}
        for domain in ds.cdc_domains.values():
            clocks.setdefault(domain.inst_name, []).append(domain.clk_signal)
        for name, signals in clocks.items():
            src_ref = signals[0].inst.inst_src_ref
            if len(signals) > 1:
                paths = ", ".join(f"'{sig.get_path()}'" for sig in signals)
                self.msg.error(
                    f"cdc_clk signals {paths} have the same port name '{name}'", src_ref
                )
            if name in ports:
                self.msg.error(
                    f"cdc_clk port '{name}' collides with {ports[name]}", src_ref
                )
        for domain in ds.cdc_domains.values():
            ports[domain.inst_name] = f"signal '{domain.clk_signal.inst_name}'"

        for domain in ds.cdc_domains.values():
            reserved = f"{domain.inst_name}_fast_mode_en"
            prefix = f"cdc_{domain.inst_name}_"
            for name, what in ports.items():
                if (domain.fast_mode_en and name == reserved) or name.startswith(
                    prefix
                ):
                    self.msg.error(
                        f"Port '{name}' ({what}) collides with a name generated for "
                        f"the domain of '{domain.clk_signal.inst_name}'",
                        domain.clk_signal.inst.inst_src_ref,
                    )
