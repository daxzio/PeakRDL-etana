from .early_external_read import EarlyExternalRead
from .extended_swacc import ReadSwacc, WriteSwacc
from .reg_only import VerilogRegOnly
from .rw_buffering import BufferReads, BufferWrites, RBufferTrigger, WBufferTrigger

ALL_UDPS = [
    BufferWrites,
    WBufferTrigger,
    BufferReads,
    RBufferTrigger,
    ReadSwacc,
    WriteSwacc,
    VerilogRegOnly,
    EarlyExternalRead,
]
