"""Helpers for building throwaway project trees that the script tests run against.

`test_generate_app_map.py` and `test_check_test_mirroring.py` both need a `tmp_path` tree
with its own `pyproject.toml` and a namespace package of Django-style apps, and both run
the scripts under test as subprocesses (their hyphenated plugin directory isn't
importable). Sharing that plumbing here keeps `subprocess.run` (and its `S603` exemption)
to one place.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def write_tree(root: Path, files: dict[str, str]) -> None:
    """Write each relative path in `files` under `root`, creating parent directories."""
    for relative_path, contents in files.items():
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")


def run_command(command: list[str], project: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        command, cwd=project, capture_output=True, text=True, check=False
    )


def run_script(
    script: Path, project: Path, *args: str
) -> subprocess.CompletedProcess[str]:
    return run_command([sys.executable, str(script), *args], project)
