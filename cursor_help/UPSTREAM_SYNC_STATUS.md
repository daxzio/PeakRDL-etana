# PeakRDL-etana upstream sync

Port changes from [PeakRDL-regblock](https://github.com/SystemRDL/PeakRDL-regblock) into this fork. Etana-only work stays in etana. This process does not push etana changes back to regblock.

Checked 4 November 2026 against SystemRDL `main`.

## Alignment

| | |
|---|---|
| Upstream | `https://github.com/SystemRDL/PeakRDL-regblock` `main` |
| Upstream commit | `ed07496` — tag `v1.3.1` (27 March 2026). `git ls-remote` on 4 November 2026 still returns this commit for `refs/heads/main` and `refs/tags/v1.3.1`. |
| Fork point | regblock `v0.22.0` (December 2024) |
| Etana | version `0.8.0`, branch `develop`, commit `3dcdaf3` (4 November 2026) |
| Logic sync | Applicable regblock changes through `ed07496` are in this tree |
| Shared RDL | All 31 upstream tests that ship `regblock.rdl` are byte-identical in `tests/` |
| Next action | When SystemRDL `main` moves past `ed07496`, port that range. There is nothing new to port today |

`git log v0.22.0..ed07496` on a clean SystemRDL checkout is the set already triaged. The next sync starts at `ed07496..origin/main`.

## What counts as upstream

Upstream is SystemRDL `main`. A local regblock checkout is a working copy, and it is easy to sync against the wrong one.

The checkout at `/home/gomez/projects/PeakRDL-regblock` (4 November 2026):

- `origin` is `git@github.com:daxzio/PeakRDL-regblock.git`, not SystemRDL.
- Branch `array_index_reset` points at `ed07496`, so the commit matches upstream.
- The working tree is dirty. Uncommitted edits add a struct `field_reset` in `field_logic/generators.py`, `field_logic/__init__.py`, `field_logic/templates/field_storage.sv`, `module_tmpl.sv`, and `utils.py` (`get_concrete_path`, `resolve_inst_int`).
- Etana already has the flattened form of that reset logic (`field_reset_<path>_value` in `src/peakrdl_etana/field_logic/`) and `tests/test_array_reset/`. Do not port the dirty diff back into etana, and do not diff etana against that dirty tree.
- Ignored leftovers on that checkout are not upstream files: `src/peakrdl_regblock/cpuif/ahb/` (pycache only), `tests/test_simple_fanin/`, and an empty `tests/test_index/`. Upstream `v1.3.1` has no `cpuif/ahb/` and does not track those test directories.

Confirm the remote before trusting "no new commits":

```bash
export UPSTREAM_URL=https://github.com/SystemRDL/PeakRDL-regblock.git
git ls-remote "$UPSTREAM_URL" refs/heads/main 'refs/tags/v*'

# Only if this clone's origin is SystemRDL/PeakRDL-regblock:
cd "$UPSTREAM_REGBLOCK"
git remote -v
git fetch origin
git log --oneline ed07496..origin/main
```

If `origin` is a fork, use `git ls-remote` against `$UPSTREAM_URL`. Fetching the fork reports a quiet `main` while SystemRDL has moved.

## Architectural rule

Regblock's hardware interface is a SystemVerilog struct. Etana's is one port per signal.

```systemverilog
// regblock
input  hwif_in_t  hwif_in,
output hwif_out_t hwif_out,
assign my_signal = hwif_in.my_reg.my_field.next;

// etana
input  wire  [7:0] hwif_in_my_reg_my_field,
output logic [7:0] hwif_out_my_reg_my_field,
assign my_signal = hwif_in_my_reg_my_field;
```

The struct member `.next` is the flattened value port. The struct member `.value` is the flattened output port. Other members keep a suffix (`_we`, `_hwclr`, `_incr`, `_overflow`). A SystemRDL `signal` keeps its own name: `signal {} f_next_value` becomes `hwif_in_r5_f_next_value`, which is the signal name, not a `_next` suffix rule.

When reading a regblock commit:

- Field, reset, counter, address, and decode logic ports across. Apply it.
- Struct packing, struct field order, and `is_interface` attributes stay in regblock.
- CPU-interface changes port onto the flattened template. Etana registers only flattened CPUIF classes.
- Testbenches are translated to Cocotb. RDL files are copied unchanged. See `COCOTB_MIGRATION_GUIDE.md`.

## How to port the next upstream range

Set `UPSTREAM_REGBLOCK` to a clean checkout of SystemRDL `main` (or to a detached `ed07496` plus a fetch from `$UPSTREAM_URL`). Set `ETANA_TESTS` to this repo's `tests/` directory.

### 1. List new commits

```bash
cd "$UPSTREAM_REGBLOCK"
git fetch "$UPSTREAM_URL" main
git log --oneline ed07496..FETCH_HEAD
git log --oneline ed07496..FETCH_HEAD -- tests/ src/
```

### 2. Classify each commit

| Change | Action |
|---|---|
| Generator logic, templates, UDPs, dependencies | Port into the matching file under `src/peakrdl_etana/`. Rewrite struct member access as flat ports. |
| Struct-only (packing, interface typedefs, `is_interface`) | Leave it. Note it in this file under "Left in regblock". |
| `tests/**/regblock.rdl` or a new `tests/test_*` | Copy RDL byte-for-byte. Translate `tb_template.sv` with `COCOTB_MIGRATION_GUIDE.md`. |
| Docs under `docs/` | Port the behavior description. Keep etana's flattened CPUIF names. |

### 3. Diff every shared RDL file

`git log --since` from an old date re-lists RDL that is already copied. Diff the new range, then diff the files.

```bash
cd "$UPSTREAM_REGBLOCK"
git diff --name-only ed07496..FETCH_HEAD -- 'tests/*/regblock.rdl'

cd "$ETANA_TESTS/.."
while IFS= read -r rdl; do
    test_name=$(basename "$(dirname "$rdl")")
    if [ -f "$ETANA_TESTS/$test_name/regblock.rdl" ]; then
        if ! cmp -s "$UPSTREAM_REGBLOCK/$rdl" "$ETANA_TESTS/$test_name/regblock.rdl"; then
            echo "DIFF $test_name"
        fi
    else
        echo "NEW  $test_name"
    fi
done < <(git -C "$UPSTREAM_REGBLOCK" diff --name-only ed07496..FETCH_HEAD -- 'tests/*/regblock.rdl')
```

Copy a differing or new RDL from upstream. Do not edit it.

```bash
cp "$UPSTREAM_REGBLOCK/tests/test_<name>/regblock.rdl" \
   "$ETANA_TESTS/test_<name>/regblock.rdl"
```

Find upstream tests that have no etana directory. Use `git ls-tree` so empty untracked directories in a local regblock checkout do not show up:

```bash
comm -13 \
  <(find "$ETANA_TESTS" -maxdepth 1 -type d -name 'test_*' -printf '%f\n' | sort) \
  <(git -C "$UPSTREAM_REGBLOCK" ls-tree --name-only FETCH_HEAD:tests | grep '^test_' | sort)
```

### 4. Map files

| Regblock | Etana | Adaptation |
|---|---|---|
| `src/peakrdl_regblock/cpuif/<name>/` | `src/peakrdl_etana/cpuif/<name>/` | Flatten ports. Register a `*-flat` name only. |
| `src/peakrdl_regblock/field_logic/` | `src/peakrdl_etana/field_logic/` | Flat storage and reset identifiers |
| `src/peakrdl_regblock/hwif/` | `src/peakrdl_etana/hwif/` | Flat port names |
| `src/peakrdl_regblock/readback/` | `src/peakrdl_etana/readback/` | Already mux-based and flattened |
| `src/peakrdl_regblock/exporter.py` | `src/peakrdl_etana/exporter.py` | Keep etana-only exporter options |
| `src/peakrdl_regblock/scan_design.py` | `src/peakrdl_etana/scan_design.py` | Direct |
| `src/peakrdl_regblock/module_tmpl.sv` | `src/peakrdl_etana/module_tmpl.sv` | Flat ports. Etana does not call `get_module_port_list()` |
| `tests/test_<name>/` | `tests/test_<name>/` | Copy `.rdl`. Translate the SV testbench to `test_dut.py` |

### 5. Test

```bash
make -C tests/test_<name> clean etana sim
make -C tests/test_<name> clean regblock sim REGBLOCK=1
cd tests && bash test_all.sh
```

`tests/tests.mak` forces Verilator when `REGBLOCK=1`, unless `SIM=xezim`. An `SIM=icarus` setting on a regblock reference run does not stick. Etana runs (`REGBLOCK=0`) use Icarus unless `SIM` is set.

### 6. Update this file

Record the new upstream commit, what was ported, what was left because it is struct-only, any etana adaptation, and the test result. Advance the `ed07496` marker in the commands above to that commit.

## CPU interfaces

Regblock `v1.3.1` registers struct and flat variants: `passthrough`, `apb3`, `apb3-flat`, `apb4`, `apb4-flat`, `axi4-lite`, `axi4-lite-flat`, `avalon-mm`, `avalon-mm-flat`, `wishbone`, `wishbone-flat`, `obi`, `obi-flat`. Default `--cpuif` is `apb3`.

Etana registers flattened classes only. Default `--cpuif` is `apb4-flat`.

| Etana `--cpuif` | In the CLI | Notes |
|---|---|---|
| `passthrough`, `apb3-flat`, `apb4-flat`, `axi4-lite-flat`, `avalon-mm-flat`, `obi-flat`, `wishbone-flat` | yes | Ported from regblock flat variants |
| `ahb-flat` | yes | Etana-only. `tests/test_ahb_pipeline` selects it |
| `ahblite-flat` | registered, then removed from choices | Class exists. `test_all.sh` skips `test_ahblite` |
| `ahb5-flat` | no | `cpuif/ahb5/` exists. `tests/test_ahb5` asks for `ahb5-flat`. `__peakrdl__.py` does not import it. `test_all.sh` skips `test_ahb5` |
| `cpuif/ahbpipeline/` | no | Directory contains only `__pycache__` |

AHB is etana work. Upstream `v1.3.1` has no `cpuif/ahb/`. A future regblock AHB would be a new port, adapted to flat ports. Do not delete etana's AHB to match upstream.

## Etana-only behavior

These exist in etana and are absent from regblock `v1.3.1`. Leave them in place during a sync. Do not treat their absence upstream as a regression, and do not send them upstream as part of this process.

CLI flags in `src/peakrdl_etana/__peakrdl__.py`:

- `--in-str`, `--out-str` — prefixes for flat port names (`hwif_in`, `hwif_out`)
- `--allow-wide-field-subwords`
- `--flatten-nested-blocks`
- `--generate-template`

Shared flags that must keep working after a port: `--cpuif`, `--module-name`, `--package-name`, `--type-style`, `--hwif-report`, `--addr-width`, `--rt-read-fanin`, `--rt-read-response`, `--rt-external`, `--default-reset`, `--err-if-bad-addr`, `--err-if-bad-rw`.

Generator behavior already in etana beyond the `v1.3.1` tree:

- Flattened field reset nets, used by `tests/test_array_reset/`. The uncommitted regblock patch is the struct version of this.
- Extra per-register guards that skip read/write buffering inside external blocks, on top of the upstream `SkipDescendants` walk.
- Icarus constraints in the readback port: no `automatic` locals, no streaming concatenation.

Etana test directories that are not in upstream `v1.3.1`. Do not delete them because `git ls-tree` of regblock does not list them:

| Directory | Role |
|---|---|
| `test_simple`, `test_basic`, `test_addrmap` | Etana bring-up designs |
| `test_wide_external` | Wide external register |
| `test_full_span_mem` | External memory that fills the CPU address width |
| `test_early_external_read`, `test_early_external_mixed` | Early external read |
| `test_array_reset` | Per-element reset values. Skipped by `test_all.sh` |
| `test_index` | CPUIF readback index. Requirements in `CPUIF_INDEX_REQUIREMENTS.md`. Skipped by `test_all.sh` |
| `test_loops` | Generated loop RTL, no Makefile, so `test_all.sh` never runs it |
| `test_ahb_pipeline`, `test_ahblite`, `test_ahb5`, `test_ahb_loop` | Etana AHB. See the CPUIF table for what actually runs |
| `test_counter_basics_apb4`, `test_template_report` | Empty leftovers (no `test_dut.py`). Ignore |

`scripts/hwif_wrapper_tool/` is etana test infrastructure. It imports `peakrdl_regblock`, generates struct RTL, and flattens the struct onto the same port names Cocotb uses. It is how `REGBLOCK=1` runs. It is not an upstream file to refresh by copying.

## Already in tree through `ed07496`

Triage of `v0.22.0..ed07496` is done. Notable ports, with the etana adaptation that a later edit of the same files needs to keep:

- Error responses `--err-if-bad-addr` / `--err-if-bad-rw`, including overlapped read-only and write-only registers (`tests/test_cpuif_err_rsp/`).
- Readback mux (`src/peakrdl_etana/readback/`). External multi-field readback is assembled from per-field `rd_data` ports.
- External components do not get read/write buffer logic (`enter_AddressableComponent` plus the older per-register check in `scan_design.py`).
- Enum `encode` collection happens in `enter_Field` (`scan_design.py`, upstream `dc9ab37`).
- Wishbone flattened CPUIF (upstream `deadbf7`). RTL matches regblock: `ack` and `err` are assigned independently. See below.
- OBI address truncation for the 1-byte data width (`cpuif/obi/obi_tmpl.sv`).
- Counter overflow width and AXI4-Lite response buffering were already present when those upstream commits landed.
- `systemrdl-compiler` dependency `~= 1.31`, and UDP checks use public node APIs.

Left in regblock on purpose: simulation-time width assertions that read `is_interface`, struct bit-order packing, and the xsim fixed-point test's struct syntax.

Still open, and not a reason to call the sync behind:

- Regblock builds the module port list in Python (`RegblockExporter.get_module_port_list()`, upstream commits around `#125` / `529c4df`). Etana still builds it in `module_tmpl.sv`. Porting it changes template structure only. Do it when `module_tmpl.sv`'s port header is being edited anyway.
- `tests/test_validation_errors/` is upstream pytest for compile-time errors. It has no Cocotb bench. Port it only if etana's exporter diagnostics need the same cases.
- `tests/test_pkg_params/` RDL matches upstream. `test_all.sh` skips it. The test README records that `REGBLOCK=1` fails on a string package parameter in regblock, and that Cocotb cannot read the generated package constants. Leave the skip until that reference run is meaningful.
- `tests/test_user_cpuif/` is a plugin-framework smoke test. `test_all.sh` skips it. The Cocotb bench does a single read and write on the default flat CPUIF.

## Wishbone ACK and ERR

`src/peakrdl_etana/cpuif/wishbone/wishbone_tmpl.sv` matches regblock `deadbf7`:

```systemverilog
wb_ack = cpuif_rd_ack | cpuif_wr_ack;
wb_err = cpuif_rd_err | cpuif_wr_err;
```

On a slave error both strobes assert. Wishbone B4 requires ACK and ERR to be mutually exclusive. `cocotbext-wishbone` reports that. `RegblockWishboneMaster` in `tests/interfaces/wishbone_wrapper.py` accepts both so the suite can run. The RTL stays matched to regblock until upstream changes it. A regblock fix would suppress `ack` when `err` is set (or drive `err` alone); port that fix onto the flat template and then drop the testbench workaround.

## Test sweep skips

`tests/test_all.sh` is the list of what the default sweep runs. As of 4 November 2026 it always skips:

`test_user_cpuif`, `test_pkg_params`, `test_template_report`, `test_ahblite`, `test_loops`, `test_index`, `test_wide_external`, `test_array_reset`, `test_early_external_read`, `test_early_external_mixed`, `test_ahb5`.

It also skips `test_ahb_pipeline` unless `CPUIF=ahb-flat`, and skips `test_addrmap` when `REGBLOCK=1`. A skip here is an etana choice. A missing upstream test after the `comm` command above is a porting task.

The May 2026 note of "32 passed, 4 skipped" described the suite at that sync. The tree now has more etana-only tests, and the skip list above is the one to use.
