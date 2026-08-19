# AHB Interface Specification Requirements

This document defines the requirements for connecting a register block to an AMBA AHB (Advanced High-performance Bus) interconnect. The AHB interface is intended for use on **shared bus systems** where multiple masters and slaves are connected through an arbiter and multiplexer. On such systems, proper stall handling is mandatory.

---

## REQ-AHB-001: HREADY-based Stall (mandatory)

The slave **shall** drive `HREADY` low whenever it cannot complete the current transfer in the current cycle. The slave **shall** keep `HREADY` low until it is ready to provide the response (read data, write acknowledgement, or error).

On a common/shared AHB bus, the slave **must** be able to drive `HREADY` low to extend a transfer when it cannot complete in a single cycle. The master and arbiter are required to hold address and control signals stable and wait until `HREADY` goes high. A slave that cannot stall will cause protocol violations and system failures when paired with arbiters or masters that expect compliant behavior.

---

## When the Slave Must Stall (HREADY = 0)

| Condition | Rationale |
|-----------|-----------|
| **External component latency** | Accesses to external registers or memories that respond asynchronously or with multi-cycle latency. The slave must wait for `rd_ack` or `wr_ack` before completing the transfer. |
| **Write data phase** | For writes, the data phase typically follows the address phase by one cycle. The slave may need to wait for valid `HWDATA` before issuing the internal write request. |
| **Internal processing** | Any internal logic (e.g., address decode, readback mux selection) that requires more than one cycle to produce a valid result. |
| **Pipeline back-pressure** | When the internal pipeline is full and cannot accept a new transfer, the slave must not indicate completion until space is available. |

---

## Master and Arbiter Obligations When HREADY = 0

- Hold `HADDR`, `HTRANS`, `HWRITE`, `HSIZE` stable
- For writes: keep `HWDATA` valid (data phase extends with address phase)
- Do not issue a new address phase for this slave until the current transfer completes

---

## Consequences of Non-Compliant Slaves

- Arbiters may grant the bus to another master prematurely
- Data corruption on reads (stale or undefined `HRDATA`)
- Protocol deadlock or bus hangs
- Intermittent failures under load or with slow externals

---

## Protocol Overview

**Address Phase (inputs to slave):**

| Signal | Description |
|--------|-------------|
| `HSEL` | Slave select (from decoder) |
| `HTRANS[1:0]` | Transfer type (NONSEQ, SEQ, IDLE, BUSY) |
| `HWRITE` | Direction (1 = write, 0 = read) |
| `HSIZE[2:0]` | Transfer size (byte, halfword, word, etc.) |
| `HADDR` | Byte address |
| `HWDATA` | Write data (valid in data phase for writes) |

**Response Phase (outputs from slave):**

| Signal | Description |
|--------|-------------|
| `HREADY` | Transfer complete; when low, the transfer is extended (stalled) |
| `HRDATA` | Read data (valid when HREADY goes high for reads) |
| `HRESP` | Response status (OKAY = 0, ERROR = 1) |

---

## AHB5 Variant (`ahb5-flat`)

PeakRDL-etana also provides an AHB5 CPU interface variant for shared-bus fabrics
such as hazard3. It uses split HREADY (HREADYIN input + HREADYOUT output),
supports AHB5 exclusive access (`HEXCL`/`HEXOKAY`), and accepts `HBURST`/`HPROT`/
`HMASTLOCK`/`HNONSEC`/`HMASTER` signals. See `docs/cpuif/ahb5.rst`.

---

## References

- AMBA 3 AHB-Lite Protocol Specification (ARM IHI 0033)
- AMBA 5 AHB Protocol Specification
