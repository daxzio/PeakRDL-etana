"""Access hwif array ports in both Verilog and VHDL wrappers.

Verilog (etana / regblock) exposes unpacked arrays, so ``sig[i]`` is one
element. The VHDL wrapper concatenates those elements into a single
``std_logic_vector`` with index 0 at the LSB (matching the wrapper's
``e(N-1) & ... & e(0)`` concat). GHDL cannot index that vector; NVC can,
but ``sig[0]`` is then a single bit, not a 32-bit word.

Probe the handle once: use unpacked indexing only when the indexed
element has the expected width. Otherwise slice the packed integer.
"""


def _elem_width(elem) -> int:
    try:
        return len(elem)
    except TypeError:
        return 1


def is_unpacked_array(sig, width: int) -> bool:
    """True when ``sig[0]`` is an element of ``width`` bits."""
    try:
        elem = sig[0]
    except (IndexError, TypeError, KeyError, AttributeError):
        return False
    return _elem_width(elem) == width


def packed_get(value: int, index: int, width: int) -> int:
    mask = (1 << width) - 1
    return (value >> (index * width)) & mask


def packed_set(value: int, index: int, elem: int, width: int) -> int:
    mask = (1 << width) - 1
    value &= ~(mask << (index * width))
    return value | ((elem & mask) << (index * width))


class HwifArray:
    """Read/write one array-like hwif port, unpacked or packed."""

    def __init__(self, sig, count: int, width: int):
        self.sig = sig
        self.count = count
        self.width = width
        self._mask = (1 << width) - 1
        self._unpacked = is_unpacked_array(sig, width)

    def get(self, index: int) -> int:
        if self._unpacked:
            return int(self.sig[index].value) & self._mask
        try:
            value = int(self.sig.value)
        except ValueError:
            raise
        return packed_get(value, index, self.width)

    def set(self, index: int, elem: int) -> None:
        elem &= self._mask
        if self._unpacked:
            self.sig[index].value = elem
            return
        try:
            current = int(self.sig.value)
        except ValueError:
            current = 0
        self.sig.value = packed_set(current, index, elem, self.width)

    def fill(self, elem: int) -> None:
        elem &= self._mask
        if self._unpacked:
            for index in range(self.count):
                self.sig[index].value = elem
            return
        if elem == 0:
            self.sig.value = 0
            return
        packed = 0
        for index in range(self.count):
            packed = packed_set(packed, index, elem, self.width)
        self.sig.value = packed
