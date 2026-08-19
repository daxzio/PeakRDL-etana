from .rw_buffering import BufferWrites, WBufferTrigger
from .rw_buffering import BufferReads, RBufferTrigger
from .extended_swacc import ReadSwacc, WriteSwacc
from .reg_only import VerilogRegOnly
from .early_external_read import EarlyExternalRead

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
