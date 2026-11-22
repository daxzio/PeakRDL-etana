# CDC alignment with PR #14 (`stfns-s/cdc-pr`)

Branch `dk_cdc` tracks [daxzio/PeakRDL-etana#14](https://github.com/daxzio/PeakRDL-etana/pull/14)
(base `dk_cdc`, head `cdc-pr`). This note records what was brought in from that PR,
what was already merged earlier on `dk_cdc`, and what we deliberately did not take.

## Brought in (gap closure, Nov 2025)

| Area | Change |
|------|--------|
| **Tests** | `tests/test_cdc_sync_cell/` (`--sync-cell`, `cdc_tb_sync.sv`); `tests/test_cdc_example/`; pr14-scale `tests/test_cdc_groups/` (multi-domain RDL, D4 snapshot checks, expanded cocotb); full `tests/test_cdc/` harness (21 cocotb tests, Makefile `CDC_*`); expanded `cdc_reset_tb.py` and four tests per `test_cdc_rst*` / `test_cdc_arst*` dir |
| **Reset suites** | CDC reset Makefiles export `CDC_RESET`, `CDC_NSTAGES3`, `CDC_FAST_PROP`, `CDC_FAST_MODE`, `CDC_T_DST_PS` for all four `--default-reset` styles |
| **Yosys** | `YOSYS_EXTRA_SOURCES` in `tests/tests.mak`; `read_slang` in the yosys recipe; `tests/synthesis.ys` no longer re-reads RTL |
| **test_all.sh** | Skip `test_cdc_sync_cell` and `test_cdc_example` for regblock / GHDL / NVC / XEZIM (etana-only UDPs and sync-cell TB) |
| **Wishbone (F1/F2)** | Single `is_active` capture/stall path for all designs; `tests/test_wishbone_pipeline` uses shared `cdc_tb.CdcTB` |
| **Docs** | Full `docs/udps/cdc.rst` from pr14, including downloadable `test_cdc_example/regblock.rdl` |

## Already on `dk_cdc` before gap closure

Inline handshake and synchronizers (no `--cdc-emit-cells` / `etana_cdc_*.sv`);
runtime `cdc_fast_mode_en` on the clock signal; wide group members; `test_cdc_array`,
`test_cdc_wide`, expanded `test_cdc_fast`; addr_decode write-trigger external gating;
CDC buffer trigger helpers requiring `cdc_clk`; Verilator pytest skips in Icarus CI.

## Intentionally not taken from PR #14

| Id | Topic | Reason |
|----|--------|--------|
| **F3** | AHB `HREADY` high in reset | Deliberate `dk_cdc` / product choice |
| **F4** | Pin Icarus and Yosys versions in CI | User decision: stay on moving toolchains |

OBI grant-reset (F6) and `validate.py` rules already matched pr14 at gap closure.
`verilog_reg_only` remains in `hdl-src/etana_udps.rdl` only (not in
`regblock_udps.rdl` on either side).

## `test_cdc.test_field_without_reset`

pr14 asserted (on Icarus/Verilator) that a field without hw reset leaves the CDC
``hwif_out`` unresolved until the first write. Etana ties destination config
outputs to their reset image, so the net is defined at time zero. The cocotb test
keeps the write/update checks only.

## After merge to `develop`

Close or supersede GitHub PR #14 once `dk_cdc` is merged and CI is green on the
target branch.
