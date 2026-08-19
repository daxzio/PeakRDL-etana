# CPU Interface Readback Indexing – Generator Requirements

This document captures generator-level requirements that apply to both
PeakRDL-Etana and PeakRDL-Regblock backends.  The goal is to describe the
expected behaviour of the *cpu interface readback index* that flattens a
register map (potentially with holes, arrays, externals, or memories) into a
contiguous index used by downstream logic and by verification environments.
The specification is intentionally implementation-agnostic so it can be
implemented inside either backend or factored into a shared helper.

---

## Terminology

| Term | Meaning |
|------|---------|
| **CPUIF** | Generator’s internal representation of the CPU bus interface (APB, AXI-Lite, etc.). |
| **Addressable Element** | Any register, external block, memory, or other item that occupies a unique CPU address range. |
| **Index** | A monotonically increasing integer that uniquely identifies each addressable element regardless of sparse address placement. |
| **Readback Array** | The flattened bus-width-wide vector used by generated RTL to mux read data back onto the CPU bus. |

The names of the actual wires/regs (`cpuif_index`, `readback_array`, etc.)
may differ per backend, but the behaviour described below must hold.

---

## Functional Requirements

### FR-1  (Contiguous Logical Index Space) – Critical

Every addressable element exposed on the CPU interface SHALL be assigned a
unique **logical index**.  Index values MUST start at 0 and increase by 1 for
each subsequent element when traversed in ascending CPU address order.

- Address gaps in the physical map MUST NOT introduce gaps in the index space.
- Arrayed registers SHALL consume a contiguous block of indices equal to the
  total number of elements × (register words per element if stride > 1).
- Externally implemented blocks or memories count the same as internal
  registers when determining index spacing.
- Implementations MAY reserve indices internally (e.g. for feature expansion),
  but such reservations MUST still produce a gap-free public index stream.

### FR-2  (Deterministic Ordering) – Critical

The ordering algorithm SHALL be deterministic and solely a function of the
RDL construct order, address offsets, and array dimensions.  For two
generators consuming the same RDL input, the index mapping MUST be identical.

### FR-3  (Consistent Width) – Critical

The readback array SHALL allocate exactly `NUM_INDICES * DATA_WIDTH` bits,
where `NUM_INDICES` is the final index count determined by FR-1.  Generators
MUST derive `NUM_INDICES` from the address map and MUST NOT rely on fixed
constants.

### FR-4  (Indexed Readback Selection) – Critical

Read data returned to the CPU bus SHALL be chosen by selecting the slice
corresponding to the current logical index:

```
readback_data = readback_array[cpuif_index*DATA_WIDTH +: DATA_WIDTH];
```

Backends MAY re-time or pipeline this selection, but the functional behaviour
has to match a single indexed pick.

### FR-5  (Conditional Population) – High

Each slice of the readback array SHALL only drive non-zero data when:

1. The decoded address for that element is active, and
2. The access is a read (not a write), and
3. For external blocks, the downstream “ack” signal is asserted.

When these conditions are not met, the slice MUST drive zeros.  This keeps
the OR reduction of inactive slices from leaking stale data and minimizes
logic replication.

### FR-6  (External Addressable Blocks) – Critical

For external register banks or memories that return read data asynchronously
(e.g. via ack/data handshake), the generator SHALL:

1. Assign a dedicated range of logical indices to the external block.
2. Place the returned data into the readback array slice that corresponds to
   the outstanding index.
3. Gate the slice with the external ack so that only valid data propagates.

**Implementation Notes:**
- External regfiles, addrmaps, and memories use a single shared `rd_data` signal
  for all addresses within the block. Therefore, all addresses in an external
  block map to the same logical index (not one per address).
- External wide registers (regwidth > accesswidth) require special handling:
  - Each subword gets its own logical index (matching cpuif_index behavior)
  - Each subword gets its own readback_array entry
  - The `rd_data` signal is shared, but `cpuif_index` selects the correct
    readback_array entry based on the accessed address
  - Use `rd_ack` only (without `hwif_out_req`) to avoid timing mismatches when
    retime is disabled

### FR-7  (Multiple Backends) – High

PeakRDL-Regblock and PeakRDL-Etana SHALL share the same observable mapping:
given the same RDL input, both backends emit HDL where:

- `NUM_INDICES`, `cpuif_index`, and readback selection are equivalent.
- Any behavioural test written against one backend’s output will pass on the
  other backend without modification.

This requirement ensures regression tests (e.g. cocotb benches) remain backend
agnostic.

### FR-8  (Tooling API) – Medium

Both generators SHOULD expose the computed mapping in a machine-readable form
to downstream tooling (e.g. meta data in JSON/YAML, Python object on the API,
or comments).  This enables:

- Testbench auto-generation
- Firmware documentation
- Comparison utilities between generator outputs

The exact format is left to implementation, but it MUST include:

| Field | Description |
|-------|-------------|
| Symbol path | Hierarchical path of the register/field/memory |
| Base address | Byte address of the element |
| Length | Number of indices consumed |
| Starting index | First logical index assigned |

---

## Implementation Guidance

The following guidance illustrates one compliant approach but does not
restrict alternative implementations:

1. **Index Builder** – During address-map traversal, maintain a running
   counter.  For each register/array/memory:
   - Record the current counter value as the starting index.
   - Increment the counter by the number of addressable words contributed.
   - **Critical**: The index counter MUST be incremented in the same order as
     the readback_array entries are created to ensure synchronization.

2. **Decoder** – After address decode determines which element is active,
   translate the decoded element into its pre-computed index range.  This can
   be done via:
   - Nested loops (current approach in Etana), or
   - A lookup table / LUT, or
   - Compile-time generated case statements.

3. **Readback Array** – Emit a packed vector sized by `NUM_INDICES`.  Populate
   each slice with conditional assignments of the decoded storage values or
   external data.
   - **Critical**: The order of readback_array assignments MUST match the order
     of cpuif_index assignments exactly. Both generators should traverse the
     RDL tree in the same order (typically via RDLWalker).

4. **External Blocks** – For external regfiles, addrmaps, and memories:
   - All addresses within the block map to the same logical index (single
     shared `rd_data` signal)
   - Generate address range check: `if ((cpuif_addr >= base) && (cpuif_addr <= base + size - 1))`
   - Increment index counter once per external block (not per address)

5. **External Wide Registers** – For external registers with regwidth > accesswidth:
   - Each subword gets its own logical index and readback_array entry
   - Use `rd_ack` only (not `hwif_out_req && rd_ack`) to avoid timing issues
   - The shared `rd_data` signal contains data for the requested subword
   - `cpuif_index` selects the correct readback_array entry based on address

6. **Verification Hooks** – Provide an optional debug signal or package that
   exposes `cpuif_index` so cocotb/uvm benches can assert ordering properties.

---

## Validation Criteria

| ID | Description | Method |
|----|-------------|--------|
| VC-1 | No gaps in index stream from 0 to `NUM_INDICES-1`. | Static analysis in generator unit tests. |
| VC-2 | Backends match index mapping for shared test suites. | Run identical RDL through both backends and diff emitted mappings. |
| VC-3 | External memories honour per-entry indices. | Directed simulation where each entry is accessed and verified. |
| VC-4 | Readback mux selects correct slice. | Cocotb/UVVM test that writes/reads random data to every address. |

---

## Example (Informative Only)

An RDL snippet with sparse addresses might assign:

| Element | Address Range | Count | Indices |
|---------|---------------|-------|---------|
| `a[31]` | 0x000–0x078 | 31 | 0–30 |
| `b[26]` | 0x07C–0x0E0 | 26 | 31–56 |
| `c`     | 0x0F0        | 1  | 57 |
| `d[8]`  | 0x0F8–0x114 | 8  | 58–65 |
| `e[8]`  | 0x20C–0x22C | 8  | 66–73 |
| `mm[13]`| 0x300–0x330 | 13 | 74–86 |

Any generator adhering to this specification would emit 87 indices even though
the address map contains large gaps.  The exact numbers above are *examples*
only; other designs follow the same rules.

---

## Implementation Checklist for New Backends

When implementing cpuif_index support in a new backend, ensure:

- [ ] **Synchronization**: Index counter (`current_index`) increments in the
  same order as readback_array entries (`current_offset`)
- [ ] **External Blocks**: All addresses in external regfile/addrmap/mem map
  to the same index (single shared rd_data)
- [ ] **External Wide Registers**: Each subword gets its own index and
  readback_array entry
- [ ] **Write-Only Registers**: Assign indices and create readback_array
  entries (returning '0) to match cpuif_index
- [ ] **Empty Subwords**: Wide registers with gaps between fields still need
  readback_array entries for all subwords
- [ ] **Address Ranges**: External blocks use range checks, not individual
  address matches
- [ ] **Timing**: External wide register readback uses `rd_ack` only (not
  `hwif_out_req && rd_ack`) to avoid timing mismatches

## Open Topics / Future Work

- **Shared Library**: Consider factoring index computation into a shared
  helper module usable by both backends to eliminate duplication.
- **Diagnostics**: Emit warnings when user-authored HDL touches reserved or
  skipped addresses to prevent mismatches between documented indices and
  actual behaviour.
- **Multi-Port CPUIF**: Extend this spec to cover designs with multiple CPU
  interfaces sharing readback infrastructure.
- **Validation**: Add automated checks to verify cpuif_index and readback_array
  synchronization (e.g., assert that final index count matches array size)

---

## References

- PeakRDL-Etana generator architecture docs
- PeakRDL-Regblock backend documentation
- Cocotb test suites (`tests/test_index`, `tests/test_external`, …)
- Discussion in issue tracker (link TBD) regarding readback index mismatches
