#!/usr/bin/env python3
"""
Post-process generated SystemVerilog to remove redundant lower-bound comparisons
against zero that can trigger Verilator UNSIGNED warnings (when treated as errors).

This is safe for unsigned address vectors (logic [N-1:0]) because:
  (addr >= 0) is always true.

We keep the upper-bound checks intact.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


ZERO_CMP_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Remove "(cpuif_addr >= <w>'h0) & "  and  "(cpuif_addr >= <w>'d0) & "
    (
        re.compile(r"\(\s*cpuif_addr\s*>=\s*\d+'\s*[hd]\s*0\s*\)\s*&\s*"),
        "",
    ),
    # Remove "(rd_mux_addr >= <w>'h0) && " and "(rd_mux_addr >= <w>'d0) && "
    (
        re.compile(r"\(\s*rd_mux_addr\s*>=\s*\d+'\s*[hd]\s*0\s*\)\s*&&\s*"),
        "",
    ),
]


def process_text(text: str) -> str:
    out = text
    for pat, repl in ZERO_CMP_PATTERNS:
        out = pat.sub(repl, out)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("target", help="File or directory to process")
    args = ap.parse_args()

    target = Path(args.target)
    if target.is_dir():
        files = sorted(target.rglob("*.sv"))
    else:
        files = [target]

    changed = 0
    for f in files:
        if not f.exists() or f.is_dir():
            continue
        before = f.read_text()
        after = process_text(before)
        if after != before:
            f.write_text(after)
            changed += 1

    # Quiet success; callers can log if desired
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
