# CDC and `cpuif_reset`: firmware checklist

Use this when the address map declares a `cpuif_reset` signal and the block has
`cdc_clk` registers. RTL behaviour and signal timing are specified in
`docs/udps/cdc.rst` (section *CPU interface reset*). This note is a bring-up
checklist for software and system architects.

## When you need it

- A domain clock can **stop or run very slowly** while the bus still attempts
  CDC reads, crossing writes, or **write-group trigger** writes.
- Without `cpuif_reset`, those transactions **stall the bus indefinitely** (no
  timeout in the generator).
- Asserting `cpuif_reset` clears handshake ownership so the CPU interface can
  accept a new transaction. It does **not** reset CDC field storage, snapshots,
  or write-member shadows.

## Timing (async `cpuif_reset`)

| Requirement | Detail |
|-------------|--------|
| Minimum pulse | Hold asserted for at least **`cdc_nstages + 2`** bus (`clk`) cycles. |
| Which `cdc_nstages` | Of the **first CDC domain** (lowest-address `cdc_clk` register in the block). |
| Synchronizer | Async `cpuif_reset` is synchronized to `clk`; clear is a **one-cycle pulse** on `cdc_cpurst_clr`. |
| Sync `cpuif_reset` | No extra synchronizer; clear is level-sensitive to the (possibly inverted) port. |

## What hardware does on assert

| Access state | Typical outcome |
|--------------|-----------------|
| **Pending** slot only (e.g. plain posted write waiting) | Dropped; never executes in the domain. |
| **Issued** in flight (read, trigger write, or pending read) | May still complete when the domain clock runs; **ack to the bus is suppressed** if ownership was cleared. |
| Late `rd_ack` / `wr_ack` after clear | **Ignored** (no spurious completion of a new transaction). |

**Race:** If `cpuif_reset` asserts while an access is still issuing, that access can
still complete in the domain (write may take effect; ack may not match what
software expected from the aborted bus cycle). To avoid that, stop the domain
clock at least **`cdc_nstages + 1`** bus cycles **before** asserting async
`cpuif_reset`, and keep it stopped until release.

## Firmware sequence after recovery

1. Do **not** start a normal register access while `cpuif_reset` is asserted.
2. Deassert `cpuif_reset` only after the minimum hold time (async case).
3. The **first** transaction to each affected CDC domain after recovery must be a
   **crossing** access (plain CDC register read/write, read trigger, or write
   trigger—not a write-group **member** only).
4. Wait for that crossing access to **complete** before touching **group members**
   (write shadows or read snapshots can still interact with a half-dead access).
5. For an aborted **write-group trigger** stall: read the trigger after recovery
   to see whether the atomic load happened.

## What does not reset

- Destination config/status flops, read snapshots, and bus-side write shadows keep
  their values.
- Only CPU-interface / handshake “ownership” state is cleared.

## Related tests

- `tests/test_cdc_cpuif_reset/` — cocotb (stuck APB, stopped domain clock).
- `tests/test_cdc_validate.py` — `test_cdc_cpuif_reset_*` export rules.

## PR origin

Cherry-picked from PR #15 commit `99f2c97` on `dk_cdc`. The async `cpuif_reset`
synchronizer uses the **block bus reset** and `always_ff` event (same as the bus
side of the CDC handshake), not per-domain `cdc_<clk>_arst` (PR #15 commit 6).
If commit 6 is merged later, consider aligning this synchronizer with
`cdc_<clk>_arst` and re-run `test_lint_cpuif_reset`.
