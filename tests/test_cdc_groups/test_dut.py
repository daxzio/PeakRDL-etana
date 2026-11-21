import random
import re
import sys
from pathlib import Path

test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))

from cocotb import start_soon, test
from cocotb.triggers import ClockCycles

from cdc_tb import CdcTB, ChangeRecord, DstAccCount, MovingInputs, rtl_text, seed

SYNC = "sync_clk"
SYNC_B = "sync_clk_b"
SYNC_C = "sync_clk_c"
CLOCKS = {SYNC: 12000, SYNC_B: 7000, SYNC_C: 9000}
# The second domain starts late, so its edges never coincide with the first domain's.
PHASES = {SYNC_B: 250}

THR_LO, THR_HI, STS_A, STS_B, STS_CAP, PLAIN_STS = 0x00, 0x04, 0x08, 0x0C, 0x10, 0x14
C_TRG, C_MEM, C_STS, C_CAP = 0x34, 0x38, 0x3C, 0x40
G2_TRG, G2_MEM, SOLO, GB_TRG, GB_MEM, BUS, PLAIN_CFG = (
    0x18,
    0x1C,
    0x20,
    0x24,
    0x28,
    0x2C,
    0x30,
)

LO = "hwif_out_thr_lo_v"
HI = "hwif_out_thr_hi_v"
OUTS = {
    LO: SYNC,
    HI: SYNC,
    "hwif_out_g2_trg_v": SYNC,
    "hwif_out_g2_mem_v": SYNC,
    "hwif_out_solo_v": SYNC,
    "hwif_out_plain_cfg_v": SYNC,
    "hwif_out_gb_trg_v": SYNC_B,
    "hwif_out_gb_mem_v": SYNC_B,
    "hwif_out_bus_cfg_v": "clk",
}


async def start(dut, phases=None) -> CdcTB:
    tb = CdcTB(dut, CLOCKS, phases)
    dut.hwif_in_soft_rst.value = 0
    await tb.clk.wait_clkn(120)
    return tb


async def expect_read(tb: CdcTB, addr: int, expected: int, mask: int = 0xFFFF) -> None:
    data, _ = await tb.read(addr, timeout_cycles=400)
    assert data & mask == expected, f"read {addr:#x}: {data:#x}, expected {expected:#x}"


def out(dut, name: str) -> int:
    return int(getattr(dut, name).value)


def changes_of(rec: ChangeRecord) -> list[tuple[str, int]]:
    return [(name, value) for _, name, value in rec.take()]


@test()
async def test_cdc_write_group(dut):
    tb = await start(dut)

    assert dut.hwif_out_thr_lo_v.value == 0x100
    await tb.write(THR_LO, 0x200)
    await tb.write(THR_HI, 0x321)
    await tb.settle(SYNC)
    assert dut.hwif_out_thr_lo_v.value == 0x200
    assert dut.hwif_out_thr_hi_v.value == 0x321

    await expect_read(tb, THR_LO, 0x200, 0xFFF)


@test()
async def test_cdc_read_group(dut):
    tb = await start(dut)

    await expect_read(tb, STS_A, 0, 0xFF)

    dut.hwif_in_sts_a_a.value = 0x12
    dut.hwif_in_sts_b_b.value = 0x34
    await tb.settle(SYNC)
    await tb.read(STS_CAP, timeout_cycles=400)
    await tb.settle(SYNC)
    await expect_read(tb, STS_A, 0x12, 0xFF)
    await expect_read(tb, STS_B, 0x34, 0xFF)


async def snapshot_consistent(dut):
    tb = await start(dut)

    moving = MovingInputs(
        dut,
        SYNC,
        {
            "hwif_in_sts_a_a": (3, 5, 8),
            "hwif_in_sts_b_b": (5, 11, 8),
            "hwif_in_sts_cap_cap": (7, 1, 8),
        },
    )
    moving.start()
    for _ in range(3):
        cap, _ = await tb.read(STS_CAP, timeout_cycles=400)
        a, _ = await tb.read(STS_A, timeout_cycles=400)
        b, _ = await tb.read(STS_B, timeout_cycles=400)
        counts = {
            moving.decode("hwif_in_sts_cap_cap", cap & 0xFF),
            moving.decode("hwif_in_sts_a_a", a & 0xFF),
            moving.decode("hwif_in_sts_b_b", b & 0xFF),
        }
        assert len(counts) == 1, f"snapshot not consistent: {counts}"


async def only_trigger_captures(dut):
    tb = await start(dut)

    dut.hwif_in_sts_a_a.value = 0x12
    dut.hwif_in_sts_b_b.value = 0x34
    await tb.settle(SYNC)

    await tb.read(THR_LO, timeout_cycles=400)
    await tb.read(PLAIN_STS, timeout_cycles=400)
    await tb.write(THR_LO, 0x123)
    a, _ = await tb.read(STS_A, timeout_cycles=400)
    b, _ = await tb.read(STS_B, timeout_cycles=400)
    assert (a & 0xFF, b & 0xFF) == (0, 0)

    await tb.read(STS_CAP, timeout_cycles=400)
    await tb.read(THR_LO, timeout_cycles=400)
    await tb.read(PLAIN_STS, timeout_cycles=400)
    dut.hwif_in_sts_a_a.value = 0x56
    dut.hwif_in_sts_b_b.value = 0x78
    await tb.settle(SYNC)
    a, _ = await tb.read(STS_A, timeout_cycles=400)
    b, _ = await tb.read(STS_B, timeout_cycles=400)
    assert (a & 0xFF, b & 0xFF) == (0x12, 0x34)


@test()
async def test_d1_read_trigger_data(dut):
    tb = await start(dut)

    dut.hwif_in_sts_cap_cap.value = 0xA5
    await ClockCycles(dut.sync_clk, 10)
    data, _ = await tb.read(0x10)
    assert data & 0xFF == 0xA5


@test()
async def test_d2_write_trigger_read(dut):
    tb = await start(dut)

    data, _ = await tb.read(0x04, timeout_cycles=200)
    assert data & 0xFFF == 0xF00


@test()
async def test_d4_snapshot_consistent(dut):
    await snapshot_consistent(dut)


@test()
async def test_d4_snapshot_clock(dut):
    text = re.sub(r"//.*", "", rtl_text())
    blocks = re.split(r"(?=\balways_(?:ff|comb|latch)\b)", text)
    snap_blocks = [
        b
        for b in blocks
        if b.startswith("always_ff") and re.search(r"cdc_snap_\w+\s*<=", b)
    ]
    assert snap_blocks, "no always_ff block assigns cdc_snap_"
    for block in snap_blocks:
        event = block.split("begin", 1)[0]
        assert "posedge sync_clk" in event, f"not on sync_clk: {event.strip()}"


@test()
async def test_d5_only_trigger_captures(dut):
    await only_trigger_captures(dut)


@test()
async def test_loads_on_one_edge(dut):
    tb = await start(dut)
    _, wov = await tb.calibrate(BUS)

    rec = ChangeRecord(dut, OUTS)
    rec.start()
    cycles = await tb.write(THR_LO, 0x200)
    if tb.has_latency:
        assert cycles - wov == 1, f"member write took {cycles - wov} bus cycles"
    await tb.settle(SYNC)
    assert changes_of(rec) == []

    await tb.write(THR_HI, 0x321)
    await tb.settle(SYNC)
    changes = rec.take()
    assert sorted((name, value) for _, name, value in changes) == [
        (HI, 0x321),
        (LO, 0x200),
    ]
    assert len({time for time, _, _ in changes}) == 1, f"not one edge: {changes}"


@test()
async def test_member_read_returns_written(dut):
    tb = await start(dut)
    rov, _ = await tb.calibrate(BUS)

    acc = DstAccCount(dut, "cdc_sync_clk")
    rec = ChangeRecord(dut, OUTS)
    rec.start()
    await tb.write(THR_LO, 0x234)
    data, cycles = await tb.read(THR_LO, timeout_cycles=400)
    assert data & 0xFFF == 0x234
    if tb.has_latency:
        assert cycles - rov == 1, f"member read took {cycles - rov} bus cycles"
    await tb.settle(SYNC)
    assert out(dut, LO) == 0x100
    assert changes_of(rec) == []
    assert acc.take() == 0


@test()
async def test_trigger_write_not_posted(dut):
    tb = await start(dut)
    _, wov = await tb.calibrate(BUS)

    await tb.write(THR_LO, 0x111)
    cycles = await tb.write(THR_HI, 0x222)
    tb.check_latency(SYNC, cycles, wov, "trigger write")
    if not tb.fast_mode:
        # The ack comes after the load, so the outputs hold the new values at once.
        assert out(dut, HI) == 0x222
        assert out(dut, LO) == 0x111


@test()
async def test_member_write_behind_trigger(dut):
    tb = await start(dut)

    rec = ChangeRecord(dut, OUTS)
    rec.start()
    await tb.write(THR_LO, 0x111)
    trigger = start_soon(tb.write(THR_HI, 0x222))
    await ClockCycles(dut.clk, 2)
    await tb.write(THR_LO, 0x333)
    await trigger
    await tb.settle(SYNC)
    assert sorted(changes_of(rec)) == [(HI, 0x222), (LO, 0x111)]
    assert out(dut, LO) == 0x111
    await expect_read(tb, THR_LO, 0x333, 0xFFF)

    await tb.write(THR_HI, 0x444)
    await tb.settle(SYNC)
    assert sorted(changes_of(rec)) == [(HI, 0x444), (LO, 0x333)]


@test()
async def test_unwritten_member_keeps_value(dut):
    tb = await start(dut)

    rec = ChangeRecord(dut, OUTS)
    rec.start()
    await tb.write(THR_LO, 0x222)
    await tb.write(THR_HI, 0xF00)
    await tb.settle(SYNC)
    assert changes_of(rec) == [(LO, 0x222)]
    await tb.write(THR_HI, 0x111)
    await tb.settle(SYNC)
    assert changes_of(rec) == [(HI, 0x111)]
    assert out(dut, LO) == 0x222


@test()
async def test_partial_member_write(dut):
    tb = await start(dut)
    if not tb.has_strb:
        return

    await tb.write(THR_LO, 0xFFAB, strb=0b01)
    await expect_read(tb, THR_LO, 0x1AB, 0xFFF)
    await tb.write(THR_LO, 0xFC00, strb=0b10)
    await expect_read(tb, THR_LO, 0xCAB, 0xFFF)
    await tb.settle(SYNC)
    assert out(dut, LO) == 0x100
    await tb.write(THR_HI, 0x5A5)
    await tb.settle(SYNC)
    assert out(dut, LO) == 0xCAB
    assert out(dut, HI) == 0x5A5


@test()
async def test_trigger_behind_posted_write(dut):
    tb = await start(dut)

    rec = ChangeRecord(dut, OUTS)
    rec.start()
    await tb.write(THR_LO, 0x2C3)
    await tb.write(PLAIN_CFG, 0x1234)
    await tb.write(THR_HI, 0x3D4)
    await tb.settle(SYNC)
    changes = rec.take()
    assert next((name, value) for _, name, value in changes) == (
        "hwif_out_plain_cfg_v",
        0x1234,
    )
    assert sorted((name, value) for _, name, value in changes[1:]) == [
        (HI, 0x3D4),
        (LO, 0x2C3),
    ]
    assert changes[0][0] < changes[1][0] == changes[2][0]


@test()
async def test_only_the_trigger_loads(dut):
    tb = await start(dut)

    rec = ChangeRecord(dut, OUTS)
    rec.start()
    await tb.write(THR_LO, 0x222)
    await tb.write(PLAIN_CFG, 0x4321)
    await tb.write(BUS, 0xABCD)
    for addr in (PLAIN_STS, PLAIN_CFG, THR_HI, THR_LO, STS_CAP, STS_A, STS_B, BUS):
        await tb.read(addr, timeout_cycles=400)
    for addr in (PLAIN_STS, STS_CAP, STS_A, STS_B):
        await tb.write(addr, 0xFFFF, timeout_cycles=400)
    await tb.settle(SYNC)
    assert sorted(changes_of(rec)) == [
        ("hwif_out_bus_cfg_v", 0xABCD),
        ("hwif_out_plain_cfg_v", 0x4321),
    ]
    assert out(dut, LO) == 0x100
    assert out(dut, HI) == 0xF00

    await tb.write(THR_HI, 0x555)
    await tb.settle(SYNC)
    assert sorted(changes_of(rec)) == [(HI, 0x555), (LO, 0x222)]


@test()
async def test_two_groups(dut):
    tb = await start(dut)

    rec = ChangeRecord(dut, OUTS)
    rec.start()
    await tb.write(THR_LO, 0x222)
    await tb.write(G2_MEM, 0x77)
    await tb.write(G2_TRG, 0x88)
    await tb.settle(SYNC)
    changes = rec.take()
    assert sorted((name, value) for _, name, value in changes) == [
        ("hwif_out_g2_mem_v", 0x77),
        ("hwif_out_g2_trg_v", 0x88),
    ]
    assert len({time for time, _, _ in changes}) == 1
    assert out(dut, LO) == 0x100

    await tb.write(THR_HI, 0x333)
    await tb.settle(SYNC)
    assert sorted(changes_of(rec)) == [(HI, 0x333), (LO, 0x222)]
    assert out(dut, "hwif_out_g2_mem_v") == 0x77


@test()
async def test_group_of_one(dut):
    tb = await start(dut)
    _, wov = await tb.calibrate(BUS)

    rec = ChangeRecord(dut, OUTS)
    rec.start()
    cycles = await tb.write(SOLO, 0xC0DE)
    tb.check_latency(SYNC, cycles, wov, "group of one write")
    if not tb.fast_mode:
        assert out(dut, "hwif_out_solo_v") == 0xC0DE
    await tb.settle(SYNC)
    assert changes_of(rec) == [("hwif_out_solo_v", 0xC0DE)]
    await expect_read(tb, SOLO, 0xC0DE)


@test()
async def test_group_in_second_domain(dut):
    tb = await start(dut, PHASES)
    _, wov = await tb.calibrate(BUS)

    rec = ChangeRecord(dut, OUTS)
    rec.start()
    await tb.write(GB_MEM, 0xAAA)
    await tb.settle(SYNC, SYNC_B)
    assert changes_of(rec) == []
    cycles = await tb.write(GB_TRG, 0xBBB)
    tb.check_latency(SYNC_B, cycles, wov, "second domain trigger write")
    await tb.settle(SYNC, SYNC_B)
    changes = rec.take()
    assert sorted((name, value) for _, name, value in changes) == [
        ("hwif_out_gb_mem_v", 0xAAA),
        ("hwif_out_gb_trg_v", 0xBBB),
    ]
    assert len({time for time, _, _ in changes}) == 1


@test()
async def test_snapshot_reset(dut):
    tb = await start(dut)

    dut.hwif_in_sts_a_a.value = 0x9A
    dut.hwif_in_sts_b_b.value = 0xB4
    dut.hwif_in_sts_cap_cap.value = 0xC6
    await tb.settle(SYNC)
    await expect_read(tb, STS_A, 0, 0xFF)
    await expect_read(tb, STS_B, 0, 0xFF)


@test()
async def test_one_edge(dut):
    await snapshot_consistent(dut)


@test()
async def test_snapshot_holds(dut):
    tb = await start(dut)

    moving = MovingInputs(
        dut,
        SYNC,
        {
            "hwif_in_sts_a_a": (3, 5, 8),
            "hwif_in_sts_b_b": (5, 11, 8),
            "hwif_in_sts_cap_cap": (7, 1, 8),
        },
    )
    moving.start()
    previous = None
    for _ in range(3):
        await tb.read(STS_CAP, timeout_cycles=400)
        first = None
        for _ in range(4):
            a, _ = await tb.read(STS_A, timeout_cycles=400)
            b, _ = await tb.read(STS_B, timeout_cycles=400)
            first = first or (a, b)
            assert (a, b) == first, "snapshot changed without a trigger read"
        assert first != previous
        previous = first


@test()
async def test_only_the_trigger_captures(dut):
    await only_trigger_captures(dut)


@test()
async def test_member_read_without_handshake(dut):
    tb = await start(dut)
    rov, _ = await tb.calibrate(BUS)

    dut.hwif_in_sts_a_a.value = 0x21
    await tb.settle(SYNC)
    await tb.read(STS_CAP, timeout_cycles=400)
    acc = DstAccCount(dut, "cdc_sync_clk")
    for addr, expected in ((STS_A, 0x21), (STS_B, 0)):
        data, cycles = await tb.read(addr, timeout_cycles=400)
        assert data & 0xFF == expected
        if tb.has_latency:
            assert cycles - rov == 1, f"member read took {cycles - rov} bus cycles"
    await tb.settle(SYNC)
    assert acc.take() == 0


@test()
async def test_ungrouped_unchanged(dut):
    tb = await start(dut)
    rov, wov = await tb.calibrate(BUS)

    acc = DstAccCount(dut, "cdc_sync_clk")
    dut.hwif_in_plain_sts_v.value = 0x5D
    await tb.settle(SYNC)
    data, cycles = await tb.read(PLAIN_STS, timeout_cycles=400)
    assert data & 0xFF == 0x5D
    tb.check_latency(SYNC, cycles, rov, "plain status read")
    await tb.settle(SYNC)
    assert acc.take() == 1

    rec = ChangeRecord(dut, OUTS)
    rec.start()
    cycles = await tb.write(PLAIN_CFG, 0x1357)
    if tb.has_latency:
        assert cycles - wov == 1
    await expect_read(tb, PLAIN_CFG, 0x1357)
    await tb.settle(SYNC)
    assert changes_of(rec) == [("hwif_out_plain_cfg_v", 0x1357)]
    assert acc.take() == 2


@test()
async def test_bus_domain_register(dut):
    tb = await start(dut)
    rov, wov = await tb.calibrate(BUS)

    acc = DstAccCount(dut, "cdc_sync_clk")
    rec = ChangeRecord(dut, OUTS)
    rec.start()
    await tb.write(BUS, 0x1234)
    await tb.clk.wait_clkn(3)
    assert changes_of(rec) == [("hwif_out_bus_cfg_v", 0x1234)]
    await expect_read(tb, BUS, 0x1234)
    await tb.settle(SYNC)
    assert acc.take() == 0
    await tb.write(THR_HI, 0x100)
    assert await tb.calibrate(BUS) == (rov, wov)


@test()
async def test_focus_no_writable_field(dut):
    tb = await start(dut)

    dut.hwif_in_sts_a_a.value = 0x3C
    dut.hwif_in_plain_sts_v.value = 0x4B
    await tb.settle(SYNC)
    rec = ChangeRecord(dut, OUTS)
    rec.start()
    for addr in (STS_CAP, STS_A, STS_B, PLAIN_STS):
        await tb.write(addr, 0xFFFF, timeout_cycles=400)
    await tb.settle(SYNC)
    assert changes_of(rec) == []
    await expect_read(tb, PLAIN_STS, 0x4B, 0xFF)
    await expect_read(tb, STS_A, 0, 0xFF)
    await tb.read(STS_CAP, timeout_cycles=400)
    await expect_read(tb, STS_A, 0x3C, 0xFF)


# name: (address, domain clock, field width, group trigger address or None)
CFG = {
    "lo": (THR_LO, SYNC, 12, THR_HI),
    "hi": (THR_HI, SYNC, 12, THR_HI),
    "g2m": (G2_MEM, SYNC, 8, G2_TRG),
    "g2t": (G2_TRG, SYNC, 8, G2_TRG),
    "solo": (SOLO, SYNC, 16, SOLO),
    "gbm": (GB_MEM, SYNC_B, 12, GB_TRG),
    "gbt": (GB_TRG, SYNC_B, 12, GB_TRG),
    "plain": (PLAIN_CFG, SYNC, 16, None),
    "bus": (BUS, "clk", 16, None),
}
OUT_NAME = {
    "lo": LO,
    "hi": HI,
    "g2m": "hwif_out_g2_mem_v",
    "g2t": "hwif_out_g2_trg_v",
    "solo": "hwif_out_solo_v",
    "gbm": "hwif_out_gb_mem_v",
    "gbt": "hwif_out_gb_trg_v",
    "plain": "hwif_out_plain_cfg_v",
    "bus": "hwif_out_bus_cfg_v",
}
RESET = {
    "lo": 0x100,
    "hi": 0xF00,
    "g2m": 0x22,
    "g2t": 0x11,
    "solo": 0x3333,
    "gbm": 0x555,
    "gbt": 0x444,
    "plain": 0x7777,
    "bus": 0xBEEF,
}
MEMBERS = {"lo": "hi", "g2m": "g2t", "gbm": "gbt"}
STATUS_IN = {
    "a": ("hwif_in_sts_a_a", STS_A),
    "b": ("hwif_in_sts_b_b", STS_B),
    "cap": ("hwif_in_sts_cap_cap", STS_CAP),
    "plain": ("hwif_in_plain_sts_v", PLAIN_STS),
}


@test()
async def test_random(dut):
    seed()
    tb = await start(dut, PHASES)
    dom = dict(RESET)
    shadow = {name: RESET[name] for name in MEMBERS}
    snap = {"a": 0, "b": 0}
    inputs = {name: 0 for name in STATUS_IN}
    by_addr = {addr: name for name, (addr, _, _, _) in CFG.items()}
    sts_by_addr = {addr: name for name, (_, addr) in STATUS_IN.items()}

    def merge(old: int, data: int, strb: int, width: int) -> int:
        mask = ((1 << width) - 1) & (
            (0xFF if strb & 1 else 0) | (0xFF00 if strb & 2 else 0)
        )
        return (old & ~mask) | (data & mask)

    def check_outputs() -> None:
        for name, value in dom.items():
            assert (
                out(dut, OUT_NAME[name]) == value
            ), f"{name}: {out(dut, OUT_NAME[name]):#x}"

    addrs = list(by_addr) + list(sts_by_addr)
    for step in range(300):
        addr = random.choice(addrs)
        action = random.choice(["write", "read", "read", "input"])
        if action == "input":
            if addr in sts_by_addr:
                key = sts_by_addr[addr]
                inputs[key] = random.getrandbits(8)
                getattr(dut, STATUS_IN[key][0]).value = inputs[key]
                await tb.settle(SYNC)
        elif action == "write":
            data = random.getrandbits(16)
            strb = random.randrange(1, 4) if tb.has_strb else 3
            await tb.write(
                addr, data, strb=strb if tb.has_strb else -1, timeout_cycles=400
            )
            if addr in by_addr:
                name = by_addr[addr]
                width = CFG[name][2]
                if name in MEMBERS:
                    shadow[name] = merge(shadow[name], data, strb, width)
                else:
                    dom[name] = merge(dom[name], data, strb, width)
                    for member, trigger in MEMBERS.items():
                        if trigger == name:
                            dom[member] = shadow[member]
        else:
            data, _ = await tb.read(addr, timeout_cycles=400)
            if addr in by_addr:
                name = by_addr[addr]
                expected = shadow[name] if name in MEMBERS else dom[name]
            else:
                key = sts_by_addr[addr]
                if key == "cap":
                    snap["a"], snap["b"] = inputs["a"], inputs["b"]
                    expected = inputs["cap"]
                elif key in snap:
                    expected = snap[key]
                else:
                    expected = inputs[key]
            assert (
                data == expected
            ), f"step {step}: read {addr:#x}: {data:#x} != {expected:#x}"
        if step % 10 == 9:
            await tb.settle(SYNC, SYNC_B)
            check_outputs()
    await tb.settle(SYNC, SYNC_B)
    check_outputs()


@test()
async def test_field_resetsignal(dut):
    tb = await start(dut)
    count = DstAccCount(dut, "cdc_sync_clk_c")

    await tb.write(PLAIN_CFG, 0x1234, timeout_cycles=400)
    await tb.write(C_MEM, 0x555, timeout_cycles=400)
    await tb.write(C_TRG, 0x666, timeout_cycles=400)
    await tb.settle(SYNC, SYNC_C)
    dut.hwif_in_c_sts_a.value = 0x5A
    dut.hwif_in_c_cap_cap.value = 0xA5
    await tb.settle(SYNC_C)
    await expect_read(tb, C_CAP, 0xA5, 0xFF)
    await tb.settle(SYNC_C)
    await expect_read(tb, C_STS, 0x5A, 0xFF)
    await tb.write(C_MEM, 0x777, timeout_cycles=400)
    assert out(dut, "hwif_out_c_trg_v") == 0x666
    assert out(dut, "hwif_out_c_mem_v") == 0x555
    await expect_read(tb, C_MEM, 0x777, 0xFFF)
    assert out(dut, "hwif_out_plain_cfg_v") == 0x1234
    count.take()

    # The field reset alone, with the bus reset inactive.
    dut.hwif_in_soft_rst.value = 1
    await ClockCycles(dut.clk, 6)
    dut.hwif_in_soft_rst.value = 0
    await tb.settle(SYNC_C)

    assert out(dut, "hwif_out_c_trg_v") == 0x0C1
    assert out(dut, "hwif_out_c_mem_v") == 0x0C2
    assert out(dut, "hwif_out_plain_cfg_v") == 0x1234
    await expect_read(tb, C_MEM, 0x0C2, 0xFFF)
    await expect_read(tb, C_TRG, 0x0C1, 0xFFF)
    assert count.take() == 1
    await expect_read(tb, C_STS, 0, 0xFF)
    await expect_read(tb, C_CAP, 0xA5, 0xFF)
    await tb.settle(SYNC_C)
    await expect_read(tb, C_STS, 0x5A, 0xFF)

    count.take()
    await tb.write(C_MEM, 0x321, timeout_cycles=400)
    await tb.write(C_TRG, 0x654, timeout_cycles=400)
    await tb.settle(SYNC_C)
    assert out(dut, "hwif_out_c_mem_v") == 0x321
    assert out(dut, "hwif_out_c_trg_v") == 0x654
    assert count.take() == 1
