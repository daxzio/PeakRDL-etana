# PR #15 cherry-pick onto `dk_cdc`

Tracking integration of [PR #15](https://github.com/daxzio/PeakRDL-etana/pull/15) (Stefanos, `cdc-pr2`).

## Merged on `dk_cdc`

| PR commit | SHA (upstream) | Topic |
|-----------|----------------|--------|
| 1–5 | `2607474` … `293fbfc` | Defect fixes + `test_cdc_trigger`, `test_cdc_rw_rtrig` |
| 7 | `c521a20` | Write groups from bus-side shadows; trigger read crosses |
| 8 | `a731ab1` | Array handshake one element wide |
| 9 | `5c63b3f` | Wishbone `has_cdc_regs` + `test_wishbone_stream` |
| 10 | `c6cf512` | No async reset when field has no RDL reset value |
| 11 | `36017f9` | Dead code removal, `cdc.rst` net names |
| 12 | `99f2c97` | `cpuif_reset` stuck-bus recovery + firmware note |

## Replaced (not cherry-picked as-is)

| PR commit | SHA | Topic |
|-----------|-----|--------|
| 6 | `2576143` | Domain reset only through synchronizer — replaced on `dk_cdc` by a polarity-following path (`dst_rst` / `dst_rst_n` from synchronizer `q`; no `cdc_<clk>_arst`; ``--sync-cell`` gains `RESET_VAL` and reset port per ``--default-reset``). |

## Follow-up (not in this batch)

- ``--test-mode <pin>`` scan bypass for synchronizers — opt-in, deferred (Stefanos PR #15 reply).

## Verification

- `pytest tests/test_cdc_validate.py` in `venv-3.12.3` after each merge batch.
- Cocotb CDC suites: CI (Cocotb 2.x).
