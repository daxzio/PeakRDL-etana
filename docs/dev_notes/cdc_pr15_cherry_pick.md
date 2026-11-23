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

## Held

| PR commit | SHA | Topic |
|-----------|-----|--------|
| 6 | `2576143` | Domain reset only through synchronizer |
| 12 | `99f2c97` | `cpuif_reset` stuck-bus recovery |

Reference stack with commit 6: branch `dk_cdc_pr15_full_backup`.

## Verification

- `pytest tests/test_cdc_validate.py` in `venv-3.12.3` after each merge batch.
- Cocotb CDC suites: CI (Cocotb 2.x).
