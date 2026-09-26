"""Tests for the lost-change check the ds plugin runs after every rebase.

This test assumes `claude_plugins/` and `.claude/ds/scripts/` sit at the project root, so
the wrapper it exercises is `.claude/ds/scripts/rebase_lost_change_check.sh`. No database is
needed: the script only ever talks to a git repository built by hand in `tmp_path`, and no
real `git rebase` is run here (a hand-built "new" branch stands in for the rebased result).
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / ".claude" / "ds" / "scripts" / "rebase_lost_change_check.sh"

GIT_ENV_OVERRIDES = {
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Rebase Test",
    "GIT_AUTHOR_EMAIL": "rebase-test@example.com",
    "GIT_COMMITTER_NAME": "Rebase Test",
    "GIT_COMMITTER_EMAIL": "rebase-test@example.com",
}

RANGE_DIFF_COMMIT_LINE = re.compile(r"^\d+:\s+\S+\s+[!<>=]\s+\d+:", re.MULTILINE)


def _run_git(
    args: list[str], cwd: Path, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )


def _run_script(
    args: list[str], cwd: Path, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [str(SCRIPT), *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def parse_section(output: str, heading: str) -> list[str]:
    """Return the paths listed directly under a "LOST:"/"REVIEW:" heading.

    Stops at the first blank line or the other heading, whichever comes first, so a
    trailing range-diff (printed after a blank line) is never mistaken for a path.
    """
    lines = output.splitlines()
    other_headings = {"LOST:", "REVIEW:"} - {heading}
    start = lines.index(heading) + 1
    end = len(lines)
    for index in range(start, len(lines)):
        if lines[index] == "" or lines[index] in other_headings:
            end = index
            break
    return lines[start:end]


def has_range_diff_commit_line(output: str) -> bool:
    return RANGE_DIFF_COMMIT_LINE.search(output) is not None


@dataclass
class GitRepo:
    path: Path
    env: dict[str, str]

    def write_text(self, relative_path: str, content: str) -> None:
        (self.path / relative_path).write_text(content)

    def write_bytes(self, relative_path: str, content: bytes) -> None:
        (self.path / relative_path).write_bytes(content)

    def remove(self, relative_path: str) -> None:
        (self.path / relative_path).unlink()

    def commit(self, message: str) -> str:
        _run_git(["add", "-A"], self.path, self.env)
        _run_git(["commit", "-q", "-m", message], self.path, self.env)
        return self.rev_parse("HEAD")

    def rev_parse(self, ref: str) -> str:
        return _run_git(["rev-parse", ref], self.path, self.env).stdout.strip()

    def checkout(self, ref: str) -> None:
        _run_git(["checkout", "-q", ref], self.path, self.env)

    def checkout_new_branch(self, branch: str, start_point: str) -> None:
        _run_git(["checkout", "-q", "-b", branch, start_point], self.path, self.env)

    def update_ref(self, ref_name: str, target: str) -> None:
        _run_git(["update-ref", ref_name, target], self.path, self.env)


@pytest.fixture
def repo(tmp_path: Path) -> GitRepo:
    env = {**os.environ, **GIT_ENV_OVERRIDES, "HOME": str(tmp_path)}
    _run_git(["init", "-q", "-b", "main"], tmp_path, env)
    return GitRepo(path=tmp_path, env=env)


def test_disjoint_changes_that_survive_a_rebase_pass(repo: GitRepo) -> None:
    # Arrange
    repo.write_text("a.txt", "base\n")
    repo.write_text("b.txt", "base\n")
    old_base = repo.commit("base")
    repo.checkout_new_branch("feature", old_base)
    repo.write_text("a.txt", "branch change\n")
    old_tip = repo.commit("branch changes a")
    repo.checkout("main")
    repo.write_text("b.txt", "main change\n")
    new_base = repo.commit("main changes b")
    repo.checkout_new_branch("rebased", new_base)
    repo.write_text("a.txt", "branch change\n")
    new_tip = repo.commit("branch changes a, rebased")

    # Act
    result = _run_script([old_base, old_tip, new_base, new_tip], repo.path, repo.env)

    # Assert
    assert result.returncode == 0
    assert parse_section(result.stdout, "LOST:") == []


def test_branch_hunk_missing_after_rebase_is_flagged_as_lost(repo: GitRepo) -> None:
    # Arrange
    repo.write_text("a.txt", "base\n")
    old_base = repo.commit("base")
    repo.checkout_new_branch("feature", old_base)
    repo.write_text("a.txt", "branch change\n")
    old_tip = repo.commit("branch changes a")
    repo.checkout_new_branch("rebased", old_base)
    repo.write_text("marker.txt", "rebase happened\n")
    new_tip = repo.commit("rebase replays a marker, but not a's change")

    # Act
    result = _run_script([old_base, old_tip, old_base, new_tip], repo.path, repo.env)

    # Assert
    assert result.returncode == 1
    assert parse_section(result.stdout, "LOST:") == ["a.txt"]


def test_branch_file_absent_after_rebase_is_flagged_as_lost(repo: GitRepo) -> None:
    # Arrange
    repo.write_text("a.txt", "base\n")
    old_base = repo.commit("base")
    repo.checkout_new_branch("feature", old_base)
    repo.write_text("a.txt", "branch adds detail\n")
    old_tip = repo.commit("branch changes a")
    repo.checkout_new_branch("rebased", old_base)
    repo.remove("a.txt")
    new_tip = repo.commit("rebase drops a.txt entirely")

    # Act
    result = _run_script([old_base, old_tip, old_base, new_tip], repo.path, repo.env)

    # Assert
    assert result.returncode == 1
    assert parse_section(result.stdout, "LOST:") == ["a.txt"]


def test_binary_file_differing_after_rebase_is_flagged_as_lost(repo: GitRepo) -> None:
    # Arrange
    repo.write_bytes("img.bin", b"\x00\x01binA")
    old_base = repo.commit("base")
    repo.checkout_new_branch("feature", old_base)
    repo.write_bytes("img.bin", b"\x00\x01binB")
    old_tip = repo.commit("branch changes the binary")
    repo.checkout_new_branch("rebased", old_base)
    repo.write_bytes("img.bin", b"\x00\x01binC")
    new_tip = repo.commit("rebase produces different bytes")

    # Act
    result = _run_script([old_base, old_tip, old_base, new_tip], repo.path, repo.env)

    # Assert
    assert result.returncode == 1
    assert parse_section(result.stdout, "LOST:") == ["img.bin"]


def test_file_both_sides_changed_with_branch_hunk_intact_needs_review(
    repo: GitRepo,
) -> None:
    # Arrange
    repo.write_text("shared.txt", "line1\nline2\nline3\n")
    old_base = repo.commit("base")
    repo.checkout_new_branch("feature", old_base)
    repo.write_text("shared.txt", "line1\nBRANCH-EDIT\nline3\n")
    old_tip = repo.commit("branch edits line2")
    repo.checkout("main")
    repo.write_text("shared.txt", "line1\nline2\nMAIN-EDIT\n")
    new_base = repo.commit("main edits line3")
    repo.checkout_new_branch("rebased", new_base)
    repo.write_text("shared.txt", "line1\nBRANCH-EDIT\nMAIN-EDIT\n")
    new_tip = repo.commit("branch edits line2, rebased")

    # Act
    result = _run_script([old_base, old_tip, new_base, new_tip], repo.path, repo.env)

    # Assert
    assert result.returncode == 2
    assert parse_section(result.stdout, "REVIEW:") == ["shared.txt"]
    assert has_range_diff_commit_line(result.stdout)


def test_file_only_changed_after_rebase_needs_review(repo: GitRepo) -> None:
    # Arrange
    repo.write_text("a.txt", "base\n")
    repo.write_text("untouched.txt", "same\n")
    old_base = repo.commit("base")
    repo.checkout_new_branch("feature", old_base)
    repo.write_text("a.txt", "branch change\n")
    old_tip = repo.commit("branch changes a")
    new_base = old_base
    repo.checkout_new_branch("rebased", new_base)
    repo.write_text("a.txt", "branch change\n")
    repo.write_text("untouched.txt", "surprising edit\n")
    new_tip = repo.commit("branch change plus an edit neither side made before")

    # Act
    result = _run_script([old_base, old_tip, new_base, new_tip], repo.path, repo.env)

    # Assert
    assert result.returncode == 2
    assert parse_section(result.stdout, "REVIEW:") == ["untouched.txt"]


def test_non_ref_argument_exits_with_usage_error(repo: GitRepo) -> None:
    # Arrange
    repo.write_text("a.txt", "base\n")
    old_base = repo.commit("base")

    # Act
    result = _run_script([old_base, "not-a-real-ref"], repo.path, repo.env)

    # Assert
    assert result.returncode == 64


def test_default_refs_are_origin_main_and_head(repo: GitRepo) -> None:
    # Arrange
    repo.write_text("a.txt", "base\n")
    old_base = repo.commit("base")
    repo.checkout_new_branch("feature", old_base)
    repo.write_text("a.txt", "branch change\n")
    old_tip = repo.commit("branch changes a")
    repo.update_ref("refs/remotes/origin/main", old_base)

    # Act
    result = _run_script([old_base, old_tip], repo.path, repo.env)

    # Assert
    assert result.returncode == 0
