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
| **Pending** slot only (a read or write waiting behind an issued access) | Dropped; never executes in the domain (same as a failed bus access from firmware’s point of view). |
| **Issued** in flight (read, plain write or trigger write) | Still executes once the domain clock runs; **ack to the bus is suppressed** if ownership was cleared. |
| Late `rd_ack` / `wr_ack` after clear | **Ignored** (no spurious completion of a new transaction). |

**Race:** The access in the **pending** slot is dropped, but an **issued** access
still runs to completion in the domain when the clock runs—even if
`cpuif_reset` asserts during the bus cycle that issued it and the reset pulse
reaches the handshake before that access would normally finish on the bus.
The pending access is still issued, and executes, if the issued access completes
before the reset reaches the handshake. The reset reaches the handshake at the
latest on the first `clk` edge with a synchronous `cpuif_reset` asserted, and
within `cdc_nstages + 1` `clk` cycles after an asynchronous one asserts. To
avoid surprising domain side effects, stop the domain clock at least
**`cdc_nstages + 1`** bus cycles **before** asserting `cpuif_reset`, and keep it
stopped until release.

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
side of the CDC handshake), not a per-domain reset net. PR #15 commit 6 was
replaced by a polarity-following domain reset path on `dk_cdc`; behaviour of
`cpuif_reset` is unchanged.
