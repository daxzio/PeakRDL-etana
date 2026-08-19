# Parameterization in test_read_fanin

## Original tests-regblock Approach

**24 test variations** created automatically:
- TestFanin: 4 variations (regwidth: 8, 16, 32, 64)
- TestRetimedFanin: 20 variations (n_regs: 1,4,7,9,11 × regwidth: 8,16,32,64)

Using Python's `parameterized` library to create test classes.

---

## Cocotb Approach (3 Options)

### Option 1: Default Parameters (Current)

**Simplest:** Test with default values only (N_REGS=1, REGWIDTH=32)

```python
@test()
async def test_dut_read_fanin(dut):
    N_REGS = 1
    REGWIDTH = 32
    # ... test logic
```

**Pros:** Simple, fast
**Cons:** Only tests one configuration

---

### Option 2: Manual RDL Parameter Override

**Generate RTL with different params:**

```bash
# Test with N_REGS=20, REGWIDTH=64
make clean
peakrdl regblock regblock.rdl -o rdl-rtl/ --cpuif apb4-flat \
    --rename regblock --top-def-name top \
    --param N_REGS=20 --param REGWIDTH=64
make sim SIM=verilator

# Test with N_REGS=4, REGWIDTH=8
make clean
peakrdl regblock regblock.rdl -o rdl-rtl/ --cpuif apb4-flat \
    --rename regblock --top-def-name top \
    --param N_REGS=4 --param REGWIDTH=8
make sim SIM=verilator
```

**Pros:** Can test any configuration
**Cons:** Manual, requires RTL regeneration each time

---

### Option 3: Pytest Parameterization

**Create run.py with pytest.mark.parametrize:**

```python
import pytest
from pathlib import Path

@pytest.mark.parametrize("n_regs,regwidth", [
    (1, 8), (1, 16), (1, 32), (1, 64),
    (20, 8), (20, 16), (20, 32), (20, 64),
])
def test_read_fanin_parameterized(n_regs, regwidth):
    import subprocess

    # Generate RTL with parameters
    subprocess.run([
        "peakrdl", "regblock", "regblock.rdl",
        "-o", "rdl-rtl/",
        "--cpuif", "apb4-flat",
        "--rename", "regblock",
        "--param", f"N_REGS={n_regs}",
        "--param", f"REGWIDTH={regwidth}",
    ])

    # Run cocotb test
    subprocess.run(["make", "sim", f"SIM=verilator"])
```

**Pros:** Automated, tests all configs
**Cons:** Slower, more complex setup

---

## Recommended Approach

**For cocotb:** Use Option 1 (default params) initially

**For comprehensive testing:**
- Use Option 2 manually for critical configs
- Or keep tests-regblock for parameterized testing

**Why:**
- Cocotb excels at test logic, not parameterization
- tests-regblock infrastructure better suited for parameter sweeps
- Most value is in testing logic, not parameter combinations

---

## Current Implementation

```python
# Default: N_REGS=1, REGWIDTH=32
@test()
async def test_dut_read_fanin(dut):
    N_REGS = 1
    REGWIDTH = 32
    STRIDE = REGWIDTH // 8

    data = [randint(0, 2**REGWIDTH - 1) for _ in range(N_REGS)]

    # Test read fanin logic
    for i in range(N_REGS):
        await tb.intf.write(i * STRIDE, data[i])

    for i in range(N_REGS):
        await tb.intf.read(i * STRIDE, data[i])
```

**Result:** ✅ PASS with default parameters

---

## To Test Other Configurations

```bash
# Example: 20 registers, 64-bit width
cd tests-cocotb/test_read_fanin
source ../../venv.2.0.0/bin/activate

make clean
peakrdl regblock regblock.rdl -o rdl-rtl/ --cpuif apb4-flat \
    --rename regblock --top-def-name top \
    --param N_REGS=20 --param REGWIDTH=64

# Update test_dut.py to use N_REGS=20, REGWIDTH=64
# Then:
make sim SIM=verilator REGBLOCK=1
```

---

**Recommendation:** Accept default params for cocotb, use tests-regblock for full parameter sweeps.
