#!/usr/bin/env python3
"""Report the EDA tool versions this repo pins against their latest releases.

Dependabot tracks action refs (``@v1``) and PyPI requirements, but it does not
look at the ``version:`` inputs passed to setup actions, nor at the git
dependencies in ``requirements.txt``. This script fills that gap: it reads the
pins out of ``.github/workflows`` and compares them with the newest published
tool version.

Usage::

    python scripts/check_tool_versions.py [--markdown PATH] [--fail-on-drift]

Exit status is 0 unless ``--fail-on-drift`` is given and something is behind.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"
REQUIREMENTS = REPO_ROOT / "requirements.txt"

# action -> workflow file whose `version:` input is the pin
PINNED_ACTIONS = {
    "daxzio/setup-icarus": "test_etana_icarus.yml",
    "daxzio/setup-xezim": "test_etana_xezim.yml",
    "veryl-lang/setup-verilator": "test_etana_verilator.yml",
    "ghdl/setup-ghdl": "test_regblock_vhdl_ghdl.yml",
    "nickg/setup-nvc": "test_regblock_vhdl_nvc.yml",
}

# tool -> where the newest version is published
LATEST_SOURCES = {
    "icarus": ("github-release", "daxzio/icarus-package"),
    "xezim": ("github-release", "daxzio/xezim-package"),
    "verilator": ("github-release", "veryl-lang/verilator-package"),
    "ghdl": ("github-release", "ghdl/ghdl"),
    "nvc": ("github-release", "nickg/nvc"),
    "cocotb": ("pypi", "cocotb"),
    "peakrdl-regblock": ("pypi", "peakrdl-regblock"),
}

ACTION_TO_TOOL = {
    "daxzio/setup-icarus": "icarus",
    "daxzio/setup-xezim": "xezim",
    "veryl-lang/setup-verilator": "verilator",
    "ghdl/setup-ghdl": "ghdl",
    "nickg/setup-nvc": "nvc",
}


def _read_action_input(action: str, filename: str, key: str = "version") -> str | None:
    """Return the first uncommented ``key:`` value inside an action's with block."""
    path = WORKFLOW_DIR / filename
    if not path.is_file():
        return None

    lines = path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if f"uses: {action}@" not in line:
            continue
        for follow in lines[index + 1 : index + 6]:
            stripped = follow.strip()
            if stripped.startswith("#") or not stripped:
                continue
            if not stripped.startswith(("with:", key + ":")):
                break
            match = re.match(rf"{key}:\s*(.+)", stripped)
            if match:
                return match.group(1).strip().strip("\"'")
    return None


def _cocotb_rev() -> str | None:
    """Return the COCOTB_REV passed to test_all.sh in the Icarus workflow."""
    path = WORKFLOW_DIR / "test_etana_icarus.yml"
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    match = re.search(r"COCOTB_REV=([0-9][0-9.]*)", text)
    return match.group(1) if match else None


def _requirements_pin(package: str) -> str | None:
    """Return a ``package==version`` pin from requirements.txt, if any."""
    if not REQUIREMENTS.is_file():
        return None
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        match = re.match(rf"{re.escape(package)}\s*==\s*(\S+)", line.strip())
        if match:
            return match.group(1)
    return None


def _get_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith("https://api.github.com"):
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def latest_version(kind: str, target: str) -> str | None:
    """Query the newest published version, or None when it cannot be read."""
    try:
        if kind == "github-release":
            data = _get_json(f"https://api.github.com/repos/{target}/releases/latest")
            return str(data.get("tag_name") or "").lstrip("v") or None
        if kind == "pypi":
            data = _get_json(f"https://pypi.org/pypi/{target}/json")
            return str(data["info"]["version"])
    except (urllib.error.URLError, KeyError, ValueError, OSError) as error:
        print(f"warning: could not read latest {target}: {error}", file=sys.stderr)
    return None


def _normalise(version: str) -> str:
    """Drop a leading ``v``/``r`` tag prefix so tags compare with plain versions."""
    return re.sub(r"^[vr](?=\d)", "", version.strip())


def collect() -> list[dict]:
    """Build one row per tool: name, pin, where it is pinned, and latest."""
    pins: dict[str, tuple[str | None, str]] = {}

    for action, filename in PINNED_ACTIONS.items():
        tool = ACTION_TO_TOOL[action]
        pins[tool] = (_read_action_input(action, filename), filename)

    pins["cocotb"] = (_cocotb_rev(), "test_etana_icarus.yml")
    pins["peakrdl-regblock"] = (
        _requirements_pin("peakrdl-regblock"),
        "requirements.txt",
    )

    rows = []
    for tool, (kind, target) in LATEST_SOURCES.items():
        pinned, source = pins.get(tool, (None, "requirements.txt"))
        latest = latest_version(kind, target)
        unpinned = pinned is None or pinned.lower() in {"latest", "nightly"}
        rows.append(
            {
                "tool": tool,
                "pinned": pinned or "latest",
                "source": source,
                "latest": latest or "unknown",
                "unpinned": unpinned,
                "behind": (
                    bool(latest)
                    and not unpinned
                    and _normalise(pinned) != _normalise(latest)
                ),
            }
        )
    return rows


def render(rows: list[dict]) -> str:
    """Render a markdown summary table plus a drift list."""
    lines = [
        "| Tool | Pinned | Pinned in | Latest | Status |",
        "|------|--------|-----------|--------|--------|",
    ]
    for row in rows:
        if row["unpinned"]:
            status = "tracks latest"
        elif row["behind"]:
            status = "**update available**"
        elif row["latest"] == "unknown":
            status = "unknown"
        else:
            status = "up to date"
        lines.append(
            f"| {row['tool']} | {row['pinned']} | {row['source']} "
            f"| {row['latest']} | {status} |"
        )

    behind = [row for row in rows if row["behind"]]
    lines.append("")
    if behind:
        lines.append("Updates available:")
        lines.append("")
        for row in behind:
            lines.append(
                f"- `{row['tool']}` {row['pinned']} -> {row['latest']} "
                f"(`{row['source']}`)"
            )
    else:
        lines.append("No pinned tool is behind its latest release.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--markdown", type=Path, help="write the report to this path")
    parser.add_argument(
        "--fail-on-drift",
        action="store_true",
        help="exit 1 when a pinned tool is behind its latest release",
    )
    args = parser.parse_args()

    rows = collect()
    report = render(rows)
    print(report, end="")

    if args.markdown:
        args.markdown.write_text(report, encoding="utf-8")

    if args.fail_on_drift and any(row["behind"] for row in rows):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
