"""Tests for `claude_plugins/fls-dev/scripts/check_panel_framework_pin.py`.

The script runs as a subprocess with `--lock` and `--direct-url` files, so no network or
installed package is involved. Editable cases point `direct_url.json` at a throwaway git
repo whose first commit is made with fixed author, committer and dates, so its sha is the
one the fixture `uv.lock` names.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from tests._script_trees import run_command, run_script

pytestmark = pytest.mark.dev_tooling

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    REPO_ROOT
    / "claude_plugins"
    / "fls-dev"
    / "scripts"
    / "check_panel_framework_pin.py"
)
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "panel_framework_pin"
LOCKED_COMMIT = "1eec040721306262c6ae4c7c395449d2d3222b1e"  # pragma: allowlist secret

FIXED_GIT_ENVIRONMENT = {
    **os.environ,
    "GIT_AUTHOR_NAME": "Fixture",
    "GIT_AUTHOR_EMAIL": "fixture@example.com",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00+0000",
    "GIT_COMMITTER_NAME": "Fixture",
    "GIT_COMMITTER_EMAIL": "fixture@example.com",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00+0000",
}


def git(repo: Path, *args: str) -> None:
    run_command(["git", "-C", str(repo), *args], repo, FIXED_GIT_ENVIRONMENT)


def make_framework_repo(root: Path) -> Path:
    """A git repo whose first commit has the sha the fixture lock records."""
    repo = root / "django-panel-framework"
    repo.mkdir()
    git(repo, "init", "--quiet")
    (repo / "README").write_text("hello\n")
    git(repo, "add", "README")
    git(repo, "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "first")
    return repo


def write_editable_direct_url(root: Path, repo: Path) -> Path:
    path = root / "direct_url.json"
    path.write_text(json.dumps({"url": repo.as_uri(), "dir_info": {"editable": True}}))
    return path


def run_check(root: Path, direct_url: Path) -> subprocess.CompletedProcess[str]:
    return run_script(
        SCRIPT,
        root,
        "--lock",
        str(FIXTURES / "uv.lock"),
        "--direct-url",
        str(direct_url),
    )


def test_locked_git_install_passes(tmp_path: Path) -> None:
    result = run_check(tmp_path, FIXTURES / "direct_url.json")

    assert result.returncode == 0, result.stdout + result.stderr


def test_clean_editable_copy_at_locked_commit_passes(tmp_path: Path) -> None:
    repo = make_framework_repo(tmp_path)
    direct_url = write_editable_direct_url(tmp_path, repo)

    result = run_check(tmp_path, direct_url)

    assert result.returncode == 0, result.stdout + result.stderr


def add_second_commit(repo: Path) -> None:
    (repo / "second").write_text("more\n")
    git(repo, "add", "second")
    git(repo, "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "second")


def add_uncommitted_file(repo: Path) -> None:
    (repo / "scratch").write_text("untracked\n")


@pytest.mark.parametrize("change", [add_second_commit, add_uncommitted_file])
def test_editable_copy_off_the_locked_state_fails_with_next_step(
    tmp_path: Path, change: Callable[[Path], None]
) -> None:
    repo = make_framework_repo(tmp_path)
    change(repo)
    direct_url = write_editable_direct_url(tmp_path, repo)

    result = run_check(tmp_path, direct_url)

    assert result.returncode != 0
    assert "installed:" in result.stdout
    assert f"locked:    {LOCKED_COMMIT}" in result.stdout
    assert "bump the pin in pyproject.toml" in result.stdout
