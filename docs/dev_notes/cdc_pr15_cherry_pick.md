# PR #15 cherry-pick onto `dk_cdc`

Tracking integration of [PR #15](https://github.com/daxzio/PeakRDL-etana/pull/15) (Stefanos, `cdc-pr2`).

## Status

| Tier | Commits | Action |
|------|---------|--------|
| A Fixes | `2607474` … `293fbfc` | Cherry-picked with `-x` |
| B Improvements | `a731ab1`, `5c63b3f`, `36017f9` | Cherry-picked |
| C Improvements | `2576143`, `c521a20`, `c6cf512` | Cherry-picked per plan |
| D `cpuif_reset` | `99f2c97` | **Not merged** — separate review |

Full plan: see Cursor plan `pr15_cherry-pick_review` / issue #13 thread.

## Held

- **Commit 12** (`99f2c97`): `cpuif_reset` recovery when a domain clock stops. RTL only changes when `cpuif_reset` is present; adds handshake ownership flags and software rules documented in `cdc.rst`.

## Verification

- `pytest tests/test_cdc_validate.py` after each tier
- Cocotb CDC dirs on Icarus `apb4-flat`; Wishbone on `wishbone-flat`
- Final: `tests/test_all.sh` subset before merge to `dk_cdc`
