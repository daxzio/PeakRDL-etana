#!/usr/bin/env python3
"""
Strip trailing whitespace from generated SystemVerilog files.
This script processes all .sv files in specified directories and removes
trailing whitespace to satisfy pre-commit hooks.

Usage:
    python3 strip_trailing_whitespace.py [directory...]

If no directory is specified, processes current directory recursively.
"""

import sys
import argparse
from pathlib import Path
from typing import Tuple


def strip_trailing_whitespace(file_path: Path) -> Tuple[int, bool]:
    """
    Strip trailing whitespace from a file.

    Args:
        file_path: Path to the file to process

    Returns:
        Tuple of (lines_modified, file_changed)
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr)
        return 0, False

    modified_lines = 0
    new_lines = []

    for line in lines:
        stripped = line.rstrip()
        if stripped != line.rstrip("\n"):
            modified_lines += 1
        new_lines.append(stripped + "\n")

    # Remove trailing newline from last line if it exists
    if new_lines and new_lines[-1] == "\n":
        new_lines[-1] = new_lines[-1].rstrip("\n")

    if modified_lines > 0:
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            return modified_lines, True
        except Exception as e:
            print(f"Error writing {file_path}: {e}", file=sys.stderr)
            return 0, False

    return 0, False


def process_directory(
    directory: Path, pattern: str = "*.sv", recursive: bool = True
) -> Tuple[int, int]:
    """
    Process all files matching pattern in directory.

    Args:
        directory: Directory to process
        pattern: Glob pattern for files to process
        recursive: If True, search recursively

    Returns:
        Tuple of (files_modified, total_lines_modified)
    """
    files_modified = 0
    total_lines_modified = 0

    if recursive:
        files = directory.rglob(pattern)
    else:
        files = directory.glob(pattern)

    for file_path in files:
        if file_path.is_file():
            lines_modified, changed = strip_trailing_whitespace(file_path)
            if changed:
                files_modified += 1
                total_lines_modified += lines_modified
                print(
                    f"✓ {file_path.relative_to(directory.parent if directory.parent != file_path.parent else directory)}: {lines_modified} lines cleaned"
                )

    return files_modified, total_lines_modified


def main():
    parser = argparse.ArgumentParser(
        description="Strip trailing whitespace from SystemVerilog files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                           # Process current directory recursively
  %(prog)s tests/                    # Process tests directory
  %(prog)s tests/ src/               # Process multiple directories
  %(prog)s --pattern "*.v" tests/    # Process .v files instead of .sv
  %(prog)s --no-recursive tests/     # Only process top-level, not subdirs
        """,
    )

    parser.add_argument(
        "directories",
        nargs="*",
        help="Directories to process (default: current directory)",
    )

    parser.add_argument(
        "--pattern", default="*.sv", help="File pattern to match (default: *.sv)"
    )

    parser.add_argument(
        "--no-recursive",
        dest="recursive",
        action="store_false",
        help="Do not search directories recursively",
    )

    args = parser.parse_args()

    directories = args.directories if args.directories else ["."]

    total_files = 0
    total_lines = 0

    for dir_path in directories:
        path = Path(dir_path)
        if not path.exists():
            print(f"Warning: {dir_path} does not exist, skipping", file=sys.stderr)
            continue

        if not path.is_dir():
            print(f"Warning: {dir_path} is not a directory, skipping", file=sys.stderr)
            continue

        print(f"\nProcessing {path}...")
        files_modified, lines_modified = process_directory(
            path, args.pattern, args.recursive
        )
        total_files += files_modified
        total_lines += lines_modified

    print(f"\n{'='*60}")
    print(f"Summary: {total_files} files modified, {total_lines} lines cleaned")

    # Return 0 (success) regardless of whether files were modified
    # This is a cleanup script, not a checker
    return 0


if __name__ == "__main__":
    sys.exit(main())
