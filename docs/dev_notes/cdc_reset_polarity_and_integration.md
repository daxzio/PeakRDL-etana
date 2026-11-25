# CDC: PR #15 integration, reset polarity rework, and follow-ups (PR #16, PR #17)

Internal record of work on branch `dk_cdc` (Nov 2026): what changed, why commit 6 of
[PR #15](https://github.com/daxzio/PeakRDL-etana/pull/15) was not taken as-is, how we
merged the rest, and how we verified it.

User-facing behaviour is in `docs/udps/cdc.rst`. Cherry-pick tables:
`docs/dev_notes/cdc_pr15_cherry_pick.md`, `docs/dev_notes/cdc_pr14_alignment.md`.
Release notes: `CHANGELOG.md` [Unreleased].

## Background

- **[Issue #13](https://github.com/daxzio/PeakRDL-etana/issues/13)** — CDC register
  support (`cdc_clk`, toggle handshake, groups, fast mode) on `dk_cdc`, aligned with
  community [PR #14](https://github.com/daxzio/PeakRDL-etana/pull/14) where practical.
- **[PR #15](https://github.com/daxzio/PeakRDL-etana/pull/15)** (Stefanos, `cdc-pr2`) —
  twelve commits on top of `dk_cdc`: defect fixes, improvements, and `cpuif_reset`
  recovery.

## Why PR #15 commit 6 was not cherry-picked

Commit `2576143` forced an **active-high-only domain reset** (`cdc_<clk>_dst_rst`)
and a derived `cdc_<clk>_arst` net, with inversions on the synchronizer and bus-side
ack path in `arst_n` / `rst_n` builds.

For ASIC flows we want **one consistent async reset polarity** matching
`--default-reset` (no extra inverters on the reset path, easier CDC/reset lint). Issue
#13 and Stefanos’s reply on PR #15 agreed there is **no functional need** for
active-high-only domain reset; the old single active-high `--sync-cell` was only to
share one cell across all four styles.

**Decision:** keep commit 6’s good properties (domain reset only from the reset
synchronizer; synchronous bus reset registered before crossing domains; no OR of two
resets on the domain net) but make **polarity follow `--default-reset`** everywhere in
the domain and on synchronizers.

Discussed on PR #15 (Dave comment on commit 6, Stefanos reply): ack sync stays on
block reset style; `--sync-cell` gets `RESET_VAL` and `rst` / `rst_n` port; `--test-mode`
scan bypass landed in [PR #17](https://github.com/daxzio/PeakRDL-etana/pull/17).

## What we implemented (replaces commit 6)

Key RTL rules (`src/peakrdl_etana/cdc/generator.py`):

| Style | Domain reset net | Synchronizer reset | Domain flops |
|-------|------------------|--------------------|--------------|
| `arst_n` / `rst_n` | `cdc_<clk>_dst_rst_n = rst_sync_q` | `negedge`, shift `1`, `RESET_VAL` 0 | async `negedge dst_rst_n` |
| `arst` / `rst` | `cdc_<clk>_dst_rst = rst_sync_q` | `posedge`, shift `0`, `RESET_VAL` 1 | async `posedge dst_rst` |
| `rst` / `rst_n` | (as above) | Reset chain uses `cdc_<clk>_bus_rst_q` registered on **bus** `clk` | |

Normally no inverter, OR, or mux on the domain reset assign; per-domain `cdc_<clk>_arst`
is forbidden. With ``--test-mode``, a polarity-preserving mux
`pin ? <block reset> : cdc_<clk>_rst_sync_q` is the only allowed exception (scan test).

**Bus side:** handshake state and **ack synchronizer** use block reset / `always_ff`
event (unchanged intent). Async **`cpuif_reset`** synchronizer uses **block bus reset**,
not a per-domain net (`289c7b2`).

**`--sync-cell`:** parameter `RESET_VAL`; connect `rst` or `rst_n` only. Test cell
`tests/test_cdc_sync_cell/cdc_tb_sync.sv` uses ``CDC_TB_SYNC_RST_N`` from the Makefile
when `CDC_RESET` contains `_n`.

**Commits (etana):** `d6f603f` polarity rework; `d50c1a5` single reset port on
`cdc_tb_sync` (Verilator `PINMISSING`).

## PR #15 merge flow (other commits)

Cherry-picks onto `dk_cdc` with `-x` (Stefanos authorship), documented in
`cdc_pr15_cherry_pick.md`:

1. **Batch 1–5** — CDC defect fixes and new trigger tests.
2. **Held then merged separately** — 7 (write-group shadows), 8 (array handshake),
   9 (Wishbone `has_cdc_regs`), 10 (no reset without RDL reset value), 11 (docs/dead code).
3. **Commit 12** — `cpuif_reset` + `docs/dev_notes/cdc_cpuif_reset_firmware.md`, with
   bus-reset fix for the async cpuif sync.
4. **Commit 6** — not cherry-picked; replaced by polarity path above.

PR comment posted on #15 summarizing replacement of commit 6 (after Stefanos’s reply).

## PR #16 follow-up (merged `7f17835`)

[PR #16](https://github.com/daxzio/PeakRDL-etana/pull/16) — small fixes after
`d50c1a5`:

1. **`DEFINES` for Icarus / Verilator / Yosys** — `CDC_TB_SYNC_RST_N` was only passed
   to xezim in `tests/tests.mak`; sync-cell tests failed for `rst_n` / `arst_n`.
2. **Doc fixes** — `RESET_VAL` meaning, `cdc_u_cpurst_sync` sync vs async, firmware
   pending/issued/race wording.
3. **Ack sync cell with registered bus reset** — for `--sync-cell` in `rst` / `rst_n`,
   ack cell reset pin uses `cdc_<clk>_bus_rst_q` (same registered net as domain reset
   synchronizer); inline and `arst*` styles unchanged.

Note: `rtlflo/cocotb_helper.mak` (other repos) only forwards `DEFINES` for a subset of
simulators; PeakRDL-etana uses `tests/tests.mak` + cocotb upstream makefiles, not
`cocotb_helper.mak`.

## PR #17 follow-up (merged `39e8784`)

[PR #17](https://github.com/daxzio/PeakRDL-etana/pull/17) — ``--test-mode PIN`` scan bypass:

1. **Opt-in port** — active-high input; at 1, block reset drives every generated CDC
   reset (`cdc_<clk>_dst_rst` / `_dst_rst_n`) through muxes outside synchronizers and
   cells. Without the option, RTL is byte-identical to the pre-PR tree.
2. **`rst` / `rst_n`** — net `cdc_<clk>_bus_rst` muxes `cdc_<clk>_bus_rst_q` vs block
   reset; feeds reset and ack synchronizers (inline or ``--sync-cell``). **`arst` /
   `arst_n`** — no `bus_rst` net; only the domain-reset mux.
3. **Tests** — cocotb `tests/test_cdc_test_mode`; pytest mux and collision rules in
   `test_cdc_validate.py`; Verilator `-Wall` on the CDC section with test mode
   (`test_lint_test_mode`).

User guide: ``docs/udps/cdc.rst`` “Scan test mode”.

## Verification flow we used

| Step | Command / action |
|------|------------------|
| Elaboration rules | `pytest tests/test_cdc_validate.py` (venv 3.12.3; includes `test_cdc_domain_reset_polarity`, `test_lint`, `test_lint_test_mode`, four-style lint) |
| Generated RTL spot-check | Four `--default-reset` styles; no `\|` / bogus `~` on domain reset assigns |
| Cocotb | `tests/test_cdc_rst*`, `test_cdc_arst*`, `test_cdc_sync_cell`, `test_cdc_test_mode`, full `test_cdc*` — CI (Cocotb 2.x) |
| Push | `origin/dk_cdc`; CI (Icarus/Verilator/Yosys matrix) |
| Non-CDC regression | `~/work/hulk_rdl`: `make INDIR=hulkv2 all` with PeakRDL-etana `main` vs `dk_cdc`; expect byte-identical `*_apb4.sv` (no `cdc_clk` in hulkv2). Local `otp.rdl` with `reg_alias` may require `origin/main` otp for builds against etana `main`; otp block not in `BLOCK_TARGETS` |

## Pointers

| Artifact | Role |
|----------|------|
| `docs/udps/cdc.rst` | User guide: reset, `--sync-cell`, crossings |
| `docs/dev_notes/cdc_cpuif_reset_firmware.md` | Software checklist for `cpuif_reset` |
| `docs/dev_notes/cdc_pr15_cherry_pick.md` | Commit-level merge table |
| `docs/dev_notes/cdc_pr14_alignment.md` | PR #14 gap closure + PR #15 status |
