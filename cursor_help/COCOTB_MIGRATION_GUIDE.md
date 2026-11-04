# Porting PeakRDL-regblock tests into etana

Use this when a new or changed SystemRDL PeakRDL-regblock commit touches `tests/`. The sync decision (what to port, what is etana-only) lives in `UPSTREAM_SYNC_STATUS.md`. This file is how to translate a test once that decision is "port it".

Checked 4 November 2026. Upstream is regblock `ed07496` (`v1.3.1`). Every upstream test that has `regblock.rdl` already has a byte-identical copy under `tests/`, and a Cocotb `test_dut.py`. The only upstream test directory with no Cocotb bench is `test_validation_errors` (pytest, compile-time errors).

## Source and destination

Upstream test, from a clean SystemRDL checkout (`$UPSTREAM_REGBLOCK`):

```
tests/test_<name>/
    regblock.rdl       # specification — copy byte-for-byte
    tb_template.sv     # SystemVerilog stimulus — translate
    testcase.py        # which CPUIF class the original bench used
```

Etana test:

```
tests/test_<name>/
    Makefile           # TEST_NAME plus include ../tests.mak
    regblock.rdl       # unmodified upstream file
    test_dut.py        # Cocotb translation
    tb_base.py         # symlink to ../tb_base.py
    interfaces         # symlink to ../interfaces
```

`tests/tb_base.py` builds the clock, reset, and CPU master, and copies every `hwif_*` port onto the testbench object. `tests/tests.mak` is the build. Defaults: `SIM=icarus`, `CPUIF=apb4-flat`, `REGBLOCK=0`, `COCOTB_REV=2.0.0`.

There is no `tests-regblock/` tree in this repo. Do not look for one. The local regblock checkout's `origin` is often the daxzio fork, and that working tree can be dirty. Read tests from SystemRDL `main`, as `UPSTREAM_SYNC_STATUS.md` describes.

## Leave these alone

An upstream sync does not delete or rewrite etana-only tests. They are listed in `UPSTREAM_SYNC_STATUS.md`. In short: `test_simple`, `test_basic`, `test_addrmap`, `test_wide_external`, `test_full_span_mem`, `test_early_external_read`, `test_early_external_mixed`, `test_array_reset`, `test_index`, `test_loops`, and the AHB tests. Empty directories `test_counter_basics_apb4` and `test_template_report` are leftovers, not tests to restore.

`tests/test_all.sh` skips some directories on purpose. Read `SKIP_TESTS` in that script before treating a skip as a failure. As of 4 November 2026 the always-skipped names are `test_user_cpuif`, `test_pkg_params`, `test_template_report`, `test_ahblite`, `test_loops`, `test_index`, `test_wide_external`, `test_array_reset`, `test_early_external_read`, `test_early_external_mixed`, and `test_ahb5`. `test_ahb_pipeline` runs only with `CPUIF=ahb-flat`. `test_addrmap` is skipped when `REGBLOCK=1`.

## Port a new or changed test

### 1. Copy the RDL

```bash
cp "$UPSTREAM_REGBLOCK/tests/test_<name>/regblock.rdl" \
   tests/test_<name>/regblock.rdl
cmp "$UPSTREAM_REGBLOCK/tests/test_<name>/regblock.rdl" \
    tests/test_<name>/regblock.rdl
```

If the upstream test has several `.rdl` files (`test_validation_errors` does), copy those files unchanged too. Do not edit RDL to make the Cocotb bench easier. The RDL is the shared specification. A local edit makes the next sync lie.

### 2. Read the original bench

```bash
# CPUIF the original used (Passthrough vs APB vs another)
grep -n -E "cpuif|Cpuif" "$UPSTREAM_REGBLOCK/tests/test_<name>/testcase.py"

# Stimulus
less "$UPSTREAM_REGBLOCK/tests/test_<name>/tb_template.sv"
```

Note register accesses, `hwif_in` / `hwif_out` uses, cycle waits, and any external-component timing.

### 3. Create the directory

For a test that does not yet exist:

```bash
mkdir -p tests/test_<name>
cd tests/test_<name>
ln -sfn ../tb_base.py tb_base.py
ln -sfn ../interfaces interfaces
```

Makefile:

```makefile
TEST_NAME := test_<name>
include ../tests.mak
```

Set `CPUIF?=` in that Makefile only when the test is about one protocol. `tests/test_ahb_pipeline/Makefile` sets `CPUIF?=ahb-flat`. Most tests inherit `apb4-flat`.

`test_dut.py`:

```python
import sys
from pathlib import Path

test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))

from cocotb import test
from tb_base import testbench


@test()
async def test_dut_<name>(dut):
    tb = testbench(dut)
    await tb.clk.wait_clkn(200)

    await tb.clk.end_test()
```

The `sys.path` insert matches the existing benches. `tb_base.py` is a sibling symlink, and the import also needs `tests/` on the path for `interfaces`.

### 4. Translate the stimulus

CPU access. `read` takes the expected value when you want it checked. Passing no expected value returns the data, which some masters return as `bytes`.

```python
await tb.intf.write(0x00, 0x22)
await tb.intf.read(0x00, 0x22)

def to_int(data):
    return int.from_bytes(data, "little") if isinstance(data, bytes) else int(data)

count = to_int(await tb.intf.read(0x00)) & 0xFF
```

`error_expected=True` is how `tests/test_cpuif_err_rsp/` asks for a slave error. APB uses `cocotbext-apb`. AXI and AHB go through `tests/interfaces/axi_wrapper.py` and `tests/interfaces/ahb_wrapper.py`, which already take `error_expected`. Wishbone goes through `WishboneMasterWrapper`, which also takes it, and uses `RegblockWishboneMaster` because regblock asserts ACK and ERR together. See `UPSTREAM_SYNC_STATUS.md`, section "Wishbone ACK and ERR".

Hardware ports. Flatten the struct path. Drop the `.next` and `.value` member names. Keep every other member as a suffix.

| Regblock testbench | Etana Cocotb |
|---|---|
| `cb.hwif_in.r1.f.next <= 32` | `tb.hwif_in_r1_f.value = 32` |
| `cb.hwif_in.r1.f.we <= 1` | `tb.hwif_in_r1_f_we.value = 1` |
| `cb.hwif_out.r1.f.value` | `int(tb.hwif_out_r1_f.value)` |
| `cb.hwif_in.r1.f.hwclr` | `tb.hwif_in_r1_f_hwclr` |
| `cb.hwif_out.cnt.overflow` | `tb.hwif_out_cnt_overflow` |

`tests/test_hw_access/test_dut.py` is the worked example: `tb.hwif_in_r1_f.value = 0xAB` and `tb.hwif_in_r1_f_we.value = 1`. There is no `_next` suffix on the hardware value port. `tb.hwif_in_r5_f_next_value` in that same file is a SystemRDL signal named `f_next_value`.

A field with `hw=w` and a field with `hw=rw` use the same value-port rule. The write-enable port is separate when the RDL has `we` or an equivalent property.

Cycle waits:

```python
from cocotb.triggers import RisingEdge

await RisingEdge(tb.clk.clk)   # one clock
await tb.clk.wait_clkn(5)      # five clocks
```

Bit-level write strobes need `CPUIF=passthrough`. APB `pstrb` is byte strobes. The original `testcase.py` naming `Passthrough` is the signal to set that.

```python
await tb.intf.write(0x0, 0x1234, strb=0x0F)
```

### 5. External components

An external register or memory is a Python emulator started with `cocotb.start_soon`, not a SystemVerilog module. Copy the shape in `tests/test_external/` or `tests/test_wide_external/test_dut.py`.

Respond on the same clock. Clear acknowledgements at the edge, then set them if `req` is high. Do not `await ReadOnly()` and then write a response. Do not insert `Timer` or an extra `RisingEdge` before the acknowledgement. Those hang the CPUIF or hit Cocotb's read-only phase.

Port names from `get_external_rd_data()` in `src/peakrdl_etana/hwif/__init__.py`:

- One software-visible field: `hwif_in_<reg>_rd_data` (no field suffix).
- Several software-visible fields: `hwif_in_<reg>_rd_data_<field>`. Treat each field's `rd_data` as right-aligned unless the RDL says otherwise.
- Memories, regfiles, and external addrmaps: `hwif_in_<inst>_rd_data`.

Acknowledgements are `hwif_in_<inst>_rd_ack` and `hwif_in_<inst>_wr_ack`. Requests are `hwif_out_<inst>_req` and `hwif_out_<inst>_req_is_wr`.

### 6. Run it

From `tests/test_<name>/`:

```bash
# Translated bench against regblock RTL. tests.mak forces Verilator
# unless SIM=xezim, so SIM=icarus does not stick on this target.
make clean regblock sim REGBLOCK=1

# Same bench against etana. Default simulator is Icarus.
make clean etana sim
```

`REGBLOCK=1` has to pass before an etana failure means anything. A failure against regblock is a translation bug. A failure only against etana is a generator bug.

Other CPU interfaces, etana generator:

```bash
make clean etana sim CPUIF=axi4-lite-flat
make clean etana sim CPUIF=ahb-flat
make clean etana sim CPUIF=obi-flat
make clean etana sim CPUIF=wishbone-flat
make clean etana sim CPUIF=passthrough
```

Wishbone needs `cocotbext-wishbone`. Selectable names are the flattened ones in `src/peakrdl_etana/__peakrdl__.py`. `ahb5-flat` is not registered. `ahblite-flat` is registered and then removed from the CLI choices.

Whole sweep, from `tests/`:

```bash
bash test_all.sh
bash test_all.sh REGBLOCK=1
bash test_all.sh CPUIF=wishbone-flat
```

`test_all.sh` defaults to `SIM=icarus` and `CPUIF=apb4-flat`. The regblock makefile override still applies inside each test when `REGBLOCK=1`.

## Wrapper generator

`make regblock` builds struct RTL with the installed `peakrdl-regblock`, then `scripts/hwif_wrapper_tool/generate_wrapper.py` flattens that struct so the Cocotb bench can use etana port names.

The script imports `peakrdl_regblock.cpuif.<module>` and registers whatever classes that install provides. It does not import `peakrdl_etana`. There is no static `choices` list. An unknown `--cpuif` fails later with the interfaces that import succeeded. Upstream `v1.3.1` has no AHB classes, so this wrapper will not grow `ahb-flat` by editing an import in etana. AHB tests run on the etana generator.

The wrapper's own default `--cpuif` is `apb3`. The test makefile passes the CPUIF through. If a generated wrapper comes out as APB3, the makefile did not pass `--cpuif`.

## Checks before calling a port done

- `regblock.rdl` matches upstream (`cmp`).
- `test_dut.py` covers the accesses and assertions in `tb_template.sv`.
- `make clean regblock sim REGBLOCK=1` passes.
- `make clean etana sim` passes.
- No struct member access (`hwif_in.reg.field`) was added to etana RTL or to the bench.
- Etana-only tests and CLI flags were left as they were.
- `UPSTREAM_SYNC_STATUS.md` records the upstream commit, the test name, and any adaptation.

## Reference benches

| Need | Look at |
|---|---|
| Short read/write | `tests/test_simple/test_dut.py`, `tests/test_enum/test_dut.py` |
| Hardware ports, `we`, a named `next` signal | `tests/test_hw_access/test_dut.py` |
| Counter field masking | `tests/test_counter_basics/test_dut.py` |
| Error responses and overlapped registers | `tests/test_cpuif_err_rsp/test_dut.py` |
| External registers | `tests/test_external/`, `tests/test_wide_external/test_dut.py` |
| Only external blocks | `tests/test_only_external_blocks/` |
| Wishbone ACK+ERR workaround | `tests/interfaces/wishbone_wrapper.py` |
