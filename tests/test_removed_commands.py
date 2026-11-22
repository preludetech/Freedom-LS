"""Removed commands and scripts leave no tracked reference behind."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.dev_tooling

REPO_ROOT = Path(__file__).resolve().parents[1]
THIS_FILE = "tests/test_removed_commands.py"


@pytest.mark.parametrize("name", ["address_pr_review", "fetch_pr_comments"])
def test_removed_name_is_not_referenced_in_tracked_files(name: str) -> None:
    result = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "git",
            "grep",
            "-l",
            "-I",
            name,
            "--",
            ".",
            ":!spec_dd",
            # The stored durations list this file's own test IDs, which carry these names.
            ":!.test_durations",
            f":!{THIS_FILE}",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.stdout.splitlines() == []
