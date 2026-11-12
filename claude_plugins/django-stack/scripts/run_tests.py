#!/usr/bin/env python3
# ruff: noqa: T201
"""Run one pytest command with an xdist worker count sized to the memory that is free.

Usage:
    python run_tests.py <pytest command...>
    python run_tests.py --capacity <unit-mb>

The command must start with `pytest`, `python -m pytest`, `python3 -m pytest`,
`uv run pytest` or `uv run --directory <dir> pytest`; anything else exits 2. When the
command has an xdist `-n` option, the runner appends its own `-n <k>`, which pytest
reads last. Setting `DS_TEST_MEMORY_GUARD=off` runs the command unchanged. `--capacity`
prints how many units of `<unit-mb>` fit in free memory, at least 1.

Each setting comes from its environment variable, then from `[tool.test_tiers.memory]` in
`pyproject.toml`, then from the default. Stdlib only, like its siblings.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

# None matches any single token: the directory `uv run --directory` is given.
ACCEPTED_PREFIXES: tuple[tuple[str | None, ...], ...] = (
    ("pytest",),
    ("python", "-m", "pytest"),
    ("python3", "-m", "pytest"),
    ("uv", "run", "pytest"),
    ("uv", "run", "--directory", None, "pytest"),
)

# Printed by `--capacity` when free memory cannot be read: large enough never to limit a caller.
UNKNOWN_CAPACITY = 999

# key -> (env var, type, default, minimum). The single list of keys: anything else in
# [tool.test_tiers.memory] is an unknown key. A per-worker memory or worker ceiling of 0
# would divide by zero or allow no worker, so those two need at least 1.
SETTINGS: dict[str, tuple[str, type[int] | type[float], float, int | None]] = {
    "per_worker_mb": ("DS_TEST_PER_WORKER_MB", int, 1024, 1),
    "reserve_mb": ("DS_TEST_RESERVE_MB", int, 2048, None),
    "max_workers": ("DS_TEST_MAX_WORKERS", int, os.cpu_count() or 1, 1),
    "psi_some_avg10_limit": ("DS_TEST_PSI_LIMIT", float, 10.0, None),
    "wait_timeout_s": ("DS_TEST_WAIT_TIMEOUT_S", int, 600, None),
    "max_retries": ("DS_TEST_MAX_RETRIES", int, 2, None),
    "oom_score_adj": ("DS_TEST_OOM_SCORE_ADJ", int, 500, None),
}

# `-nauto`, `-n4`: the attached form, which must not match other `-n...` flags like `-no:cacheprovider`.
NUMPROCESSES_ATTACHED = re.compile(r"-n(auto|logical|\d+)")

WORKER_FLAGS = frozenset({"-n", "--numprocesses"})

DEFAULT_MEMINFO = Path("/proc/meminfo")


class ConfigError(Exception):
    """A malformed `[tool.test_tiers.memory]` table or memory environment variable."""


@dataclass(frozen=True)
class MemorySettings:
    per_worker_mb: int
    reserve_mb: int
    max_workers: int
    psi_some_avg10_limit: float
    wait_timeout_s: int
    max_retries: int
    oom_score_adj: int
    # Setting name -> "env" or "pyproject", for each setting that is not the default.
    sources: dict[str, str] = field(default_factory=dict)


def type_noun(kind: type[int] | type[float]) -> str:
    return "an integer" if kind is int else "a number"


def check_value(value: object, kind: type[int] | type[float]) -> int | float | None:
    """The value as `kind`, or None when it is the wrong type. A bool is never a number."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return kind(value)
    if kind is float and isinstance(value, float):
        return value
    return None


def parse_env_value(name: str, text: str, kind: type[int] | type[float]) -> int | float:
    try:
        return kind(text)
    except ValueError:
        raise ConfigError(f"{name} must be {type_noun(kind)}") from None


def read_memory_table(project_root: Path) -> dict[str, object]:
    """The `[tool.test_tiers.memory]` table. A missing file, `[tool]` or `[tool.test_tiers]`
    leaves the defaults, as the tier config does."""
    try:
        data = tomllib.loads((project_root / "pyproject.toml").read_text("utf-8"))
    except FileNotFoundError:
        return {}
    table = data.get("tool", {}).get("test_tiers", {}).get("memory", {})
    if not isinstance(table, dict):
        raise ConfigError("[tool.test_tiers] 'memory' must be a table")
    for key in table:
        if key not in SETTINGS:
            raise ConfigError(f"[tool.test_tiers.memory] unknown key '{key}'")
    return table


def load_memory_settings(
    project_root: Path, environ: Mapping[str, str]
) -> MemorySettings:
    """Resolve each setting: environment variable, then pyproject, then the default."""
    table = read_memory_table(project_root)
    values: dict[str, int | float] = {}
    sources: dict[str, str] = {}
    for key, (env_name, kind, default, minimum) in SETTINGS.items():
        if env_name in environ:
            value = parse_env_value(env_name, environ[env_name], kind)
            origin, label = "env", env_name
        elif key in table:
            checked = check_value(table[key], kind)
            if checked is None:
                raise ConfigError(
                    f"[tool.test_tiers.memory] '{key}' must be {type_noun(kind)}"
                )
            value = checked
            origin, label = "pyproject", f"[tool.test_tiers.memory] '{key}'"
        else:
            values[key] = kind(default)
            continue
        if minimum is not None and value < minimum:
            raise ConfigError(f"{label} must be at least {minimum}")
        values[key] = value
        sources[key] = origin
    return MemorySettings(
        per_worker_mb=int(values["per_worker_mb"]),
        reserve_mb=int(values["reserve_mb"]),
        max_workers=int(values["max_workers"]),
        psi_some_avg10_limit=float(values["psi_some_avg10_limit"]),
        wait_timeout_s=int(values["wait_timeout_s"]),
        max_retries=int(values["max_retries"]),
        oom_score_adj=int(values["oom_score_adj"]),
        sources=sources,
    )


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


def describe_sources(settings: MemorySettings) -> str:
    """` (key=value from source, ...)` for each setting that is not the default."""
    parts = [
        f"{key}={getattr(settings, key)} from {origin}"
        for key, origin in settings.sources.items()
    ]
    return f" ({', '.join(parts)})" if parts else ""


def print_capacity(unit_text: str, settings: MemorySettings) -> int:
    """Print how many units of `unit_text` MB fit in free memory, never fewer than 1."""
    if not unit_text.isascii() or not unit_text.isdigit() or int(unit_text) < 1:
        print("--capacity takes a positive integer number of MB", file=sys.stderr)
        return 2
    available = mem_available_mb(meminfo_path())
    if available is None:
        print(UNKNOWN_CAPACITY)
        return 0
    print(max(1, (available - settings.reserve_mb) // int(unit_text)))
    return 0


def main() -> int:
    try:
        return run(sys.argv[1:])
    except (ConfigError, tomllib.TOMLDecodeError) as error:
        print(f"run_tests.py: {error}", file=sys.stderr)
        return 2


def run(argv: list[str]) -> int:
    if argv[:1] == ["--capacity"]:
        settings = load_memory_settings(Path.cwd(), os.environ)
        return print_capacity(argv[1] if len(argv) == 2 else "", settings)
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
    settings = load_memory_settings(Path.cwd(), os.environ)
    available = mem_available_mb(meminfo_path())
    if available is None:
        print("ram: no /proc/meminfo on this platform; running the command as given")
        return run_plain(argv)
    fit = worker_fit(available, settings.reserve_mb, settings.per_worker_mb)
    k = max(1, min(fit, settings.max_workers))
    command = [*argv, "-n", str(k)] if has_worker_option(argv) else argv
    print(
        f"ram: MemAvailable {available} MB, xdist workers -n {k}"
        f"{describe_sources(settings)}"
    )
    return run_plain(command)


if __name__ == "__main__":
    sys.exit(main())
