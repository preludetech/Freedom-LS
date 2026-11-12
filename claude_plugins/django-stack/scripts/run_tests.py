#!/usr/bin/env python3
# ruff: noqa: T201
"""Run one pytest command with an xdist worker count sized to the memory that is free.

Usage:
    python run_tests.py <pytest command...>

The command must start with `pytest`, `python -m pytest`, `python3 -m pytest`,
`uv run pytest` or `uv run --directory <dir> pytest`; anything else exits 2. When the
command has an xdist `-n` option, the runner appends its own `-n <k>`, which pytest
reads last. Setting `DS_TEST_MEMORY_GUARD=off` runs the command unchanged. Stdlib only,
like its siblings.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

# None matches any single token: the directory `uv run --directory` is given.
ACCEPTED_PREFIXES: tuple[tuple[str | None, ...], ...] = (
    ("pytest",),
    ("python", "-m", "pytest"),
    ("python3", "-m", "pytest"),
    ("uv", "run", "pytest"),
    ("uv", "run", "--directory", None, "pytest"),
)

PER_WORKER_MB = 1024
RESERVE_MB = 2048
MAX_WORKERS = os.cpu_count() or 1

# `-nauto`, `-n4`: the attached form, which must not match other `-n...` flags like `-no:cacheprovider`.
NUMPROCESSES_ATTACHED = re.compile(r"-n(auto|logical|\d+)")

WORKER_FLAGS = frozenset({"-n", "--numprocesses"})

DEFAULT_MEMINFO = Path("/proc/meminfo")


def is_pytest_command(argv: list[str]) -> bool:
    """Whether argv starts with one of the accepted forms, compared token for token.

    Bare names only: a path such as `/tmp/x/pytest` is refused, because the wrapper is
    allowed prompt-free and must not run a caller-chosen executable. The flags after the
    prefix are pytest's own and are passed through, as a direct pytest call would take them.
    """
    return any(
        len(argv) >= len(prefix)
        and all(
            expected is None or token == expected
            for token, expected in zip(argv, prefix, strict=False)
        )
        for prefix in ACCEPTED_PREFIXES
    )


def run_plain(argv: list[str]) -> int:
    """Run the command as given and return its exit code."""
    return subprocess.run(argv, check=False).returncode  # noqa: S603


def meminfo_path() -> Path:
    return Path(os.environ.get("DS_TEST_MEMINFO_PATH") or DEFAULT_MEMINFO)


def mem_available_mb(meminfo: Path) -> int | None:
    """MemAvailable in MB, or None when the file is missing (no /proc on this platform)."""
    try:
        text = meminfo.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    for line in text.splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) // 1024
    return None


def worker_fit(available_mb: int, reserve_mb: int, per_worker_mb: int) -> int:
    """How many workers fit once `reserve_mb` is left free. Zero or negative: none."""
    return (available_mb - reserve_mb) // per_worker_mb


def has_worker_option(argv: list[str]) -> bool:
    """True for `-n <x>`, `-n<x>`, `--numprocesses <x>` and `--numprocesses=<x>`."""
    return any(
        arg in WORKER_FLAGS
        or NUMPROCESSES_ATTACHED.fullmatch(arg) is not None
        or arg.startswith("--numprocesses=")
        for arg in argv
    )


def main() -> int:
    argv = sys.argv[1:]
    if not is_pytest_command(argv):
        print(
            "run_tests.py runs only a pytest command. Accepted forms: "
            "pytest, python -m pytest, python3 -m pytest, uv run pytest, "
            "uv run --directory <dir> pytest.",
            file=sys.stderr,
        )
        return 2
    if os.environ.get("DS_TEST_MEMORY_GUARD") == "off":
        return run_plain(argv)
    available = mem_available_mb(meminfo_path())
    if available is None:
        print("ram: no /proc/meminfo on this platform; running the command as given")
        return run_plain(argv)
    k = max(1, min(worker_fit(available, RESERVE_MB, PER_WORKER_MB), MAX_WORKERS))
    command = [*argv, "-n", str(k)] if has_worker_option(argv) else argv
    print(f"ram: MemAvailable {available} MB, xdist workers -n {k}")
    return run_plain(command)


if __name__ == "__main__":
    sys.exit(main())
