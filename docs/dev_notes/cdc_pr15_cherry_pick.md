# PR #15 cherry-pick onto `dk_cdc`

Tracking integration of [PR #15](https://github.com/daxzio/PeakRDL-etana/pull/15) (Stefanos, `cdc-pr2`).

## Merged on `dk_cdc`

| PR commit | SHA (upstream) | Topic |
|-----------|----------------|--------|
| 1–5 | `2607474` … `293fbfc` | Defect fixes + `test_cdc_trigger`, `test_cdc_rw_rtrig` |
| 8 | `a731ab1` | Array handshake one element wide |
| 9 | `5c63b3f` | Wishbone `has_cdc_regs` + `test_wishbone_stream` |
| 11 | `36017f9` | Dead code removal, `cdc.rst` net names |
| — | — | `99f2c97` **not** merged (`cpuif_reset`) |

## Held for individual review

Cherry-picks are **not** on `dk_cdc` yet. Full stack (including these) is on branch `dk_cdc_pr15_full_backup` for comparison.

| PR commit | SHA | Topic |
|-----------|-----|--------|
| 6 | `2576143` | Domain reset only through synchronizer (`cdc_<clk>_arst`, no OR on `dst_rst`) |
| 7 | `c521a20` | Write groups load members from bus-side shadows (trigger read crosses) |
| 10 | `c6cf512` | CDC fields without reset value omit async reset (Etana vs pr14 semantics) |

When you take one of these, cherry-pick `-x` from `origin/pr15` (or from `dk_cdc_pr15_full_backup`) onto current `dk_cdc` and re-run `pytest tests/test_cdc_validate.py`.

## Verification (current `dk_cdc`)

- `pytest tests/test_cdc_validate.py`: 89 passed, 1 skipped (venv 3.12.3)
- Cocotb: CI uses Cocotb 2.x; local venv 1.9.2 lacks `SimTimeoutError` in `cdc_tb.py`

## Draft comment for PR #15 (not posted)

Tier A fixes, commits 8/9/11, and docs are on `dk_cdc`. Commits 6, 7, and 10 are held for separate review; commit 12 (`cpuif_reset`) still out of scope.
