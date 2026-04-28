"""Shared git helpers for tests that need a real on-disk git repo.

Several tests for legal-docs / signup behaviour set up a temporary repo with
``git init`` + a single commit so the production code can read blobs via
``git show HEAD:<path>``. This module factors out the duplicated subprocess
plumbing.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def run_git(repo: Path, *args: str) -> str:
    """Run ``git`` in ``repo`` and return stripped stdout."""
    cmd = ["git", "-C", str(repo), *args]
    return subprocess.run(  # noqa: S603
        cmd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def init_repo(repo: Path) -> None:
    """Initialise a fresh git repo with a deterministic identity."""
    run_git(repo, "init", "-q", "-b", "main")
    run_git(repo, "config", "user.email", "test@example.com")
    run_git(repo, "config", "user.name", "Test")


def commit_all(repo: Path, msg: str = "init") -> None:
    """Stage everything and commit with ``msg``."""
    run_git(repo, "add", "-A")
    run_git(repo, "commit", "-q", "-m", msg)
