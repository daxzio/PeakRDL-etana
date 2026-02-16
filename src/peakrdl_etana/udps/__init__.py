from .rw_buffering import BufferWrites, WBufferTrigger
from .rw_buffering import BufferReads, RBufferTrigger
from .extended_swacc import ReadSwacc, WriteSwacc
from .reg_only import VerilogRegOnly

ALL_UDPS = [
    BufferWrites,
    WBufferTrigger,
    BufferReads,
    RBufferTrigger,
    ReadSwacc,
    WriteSwacc,
    VerilogRegOnly,
]
