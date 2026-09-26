"""Tests for the upstream-change scan the pre-step rebase runs after a rebase replays commits.

This test assumes `claude_plugins/` sits at the project root, so the script it exercises is
`claude_plugins/sdd/scripts/upstream_change_scan.sh`. No database is needed: the script only ever
talks to a git repository built by hand in `tmp_path`, and no real `git rebase` is run here (a
hand-built "new base" and "HEAD" stand in for the rebased result).
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "claude_plugins" / "sdd" / "scripts" / "upstream_change_scan.sh"

GIT_ENV_OVERRIDES = {
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Rebase Test",
    "GIT_AUTHOR_EMAIL": "rebase-test@example.com",
    "GIT_COMMITTER_NAME": "Rebase Test",
    "GIT_COMMITTER_EMAIL": "rebase-test@example.com",
}


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
    """Return the paths listed directly under a "## <heading>" section.

    The section body is either "(none)" or one path per line, followed by a blank line before
    the next heading, so a blank line always ends the section cleanly.
    """
    lines = output.splitlines()
    marker = f"## {heading}"
    start = lines.index(marker) + 2  # skip the heading line and the blank line under it
    end = start
    while end < len(lines) and lines[end] != "":
        end += 1
    body = lines[start:end]
    if body == ["(none)"]:
        return []
    return body


def diff_block(output: str, path: str) -> list[str]:
    """Return the fenced diff lines printed under "### <path>" in the Diffs section."""
    lines = output.splitlines()
    start = lines.index(f"### {path}")
    end = start + 1
    while end < len(lines) and not lines[end].startswith("### "):
        end += 1
    return lines[start:end]


@dataclass
class GitRepo:
    path: Path
    env: dict[str, str]

    def write_text(self, relative_path: str, content: str) -> None:
        target = self.path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

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


@pytest.fixture
def repo(tmp_path: Path) -> GitRepo:
    env = {**os.environ, **GIT_ENV_OVERRIDES, "HOME": str(tmp_path)}
    _run_git(["init", "-q", "-b", "main"], tmp_path, env)
    return GitRepo(path=tmp_path, env=env)


def make_spec_dir(repo: GitRepo, idea_body: str) -> str:
    """Write a spec directory with a space in its name, holding one idea.md.

    Real spec directories under `spec_dd/2. in progress/` always have a space in their name
    (the stage prefix), so this proves the script copes with that.
    """
    relative = "spec_dd/2. in progress/my spec"
    repo.write_text(f"{relative}/idea.md", idea_body)
    return relative


def write_app_structure(repo: GitRepo, edge: str | None) -> None:
    body = "```mermaid\nflowchart TB\n"
    if edge is not None:
        body += f"    {edge}\n"
    body += "```\n"
    repo.write_text("docs/app_structure.md", body)


def test_unrelated_file_change_reports_no_signal(repo: GitRepo) -> None:
    # Arrange
    repo.write_text("unrelated.txt", "base\n")
    write_app_structure(repo, "A --> B")
    old_base = repo.commit("base")
    spec_dir = make_spec_dir(repo, "Nothing named here.\n")
    repo.write_text("unrelated.txt", "changed\n")
    new_base = repo.commit("main changes an unrelated file")

    # Act
    result = _run_script([old_base, new_base, spec_dir], repo.path, repo.env)

    # Assert
    assert result.returncode == 0
    assert parse_section(result.stdout, "Overlap") == []
    assert parse_section(result.stdout, "Shared bases") == []
    assert parse_section(result.stdout, "Conventions") == []
    assert parse_section(result.stdout, "Done specs") == []


def test_branch_also_changed_file_reports_overlap(repo: GitRepo) -> None:
    # Arrange
    repo.write_text("shared.txt", "base\n")
    old_base = repo.commit("base")
    spec_dir = make_spec_dir(repo, "Nothing named here.\n")
    repo.write_text("shared.txt", "main changed\n")
    new_base = repo.commit("main changes shared.txt")
    repo.checkout_new_branch("feature", new_base)
    repo.write_text("shared.txt", "branch changed too\n")
    repo.commit("branch also changes shared.txt")

    # Act
    result = _run_script([old_base, new_base, spec_dir], repo.path, repo.env)

    # Assert
    assert result.returncode == 2
    assert parse_section(result.stdout, "Overlap") == ["shared.txt"]


def test_file_under_backticked_directory_reports_overlap(repo: GitRepo) -> None:
    # Arrange
    repo.write_text("libdir/inner.py", "base\n")
    old_base = repo.commit("base")
    spec_dir = make_spec_dir(repo, "See `libdir` for the shared helper.\n")
    repo.write_text("libdir/inner.py", "changed\n")
    new_base = repo.commit("main changes a file under the named directory")

    # Act
    result = _run_script([old_base, new_base, spec_dir], repo.path, repo.env)

    # Assert
    assert result.returncode == 2
    assert parse_section(result.stdout, "Overlap") == ["libdir/inner.py"]


def test_non_path_backticked_span_matches_nothing(repo: GitRepo) -> None:
    # Arrange
    repo.write_text("unrelated.txt", "base\n")
    old_base = repo.commit("base")
    spec_dir = make_spec_dir(repo, "Once done this returns `status: ok`.\n")
    repo.write_text("unrelated.txt", "changed\n")
    new_base = repo.commit("main changes an unrelated file")

    # Act
    result = _run_script([old_base, new_base, spec_dir], repo.path, repo.env)

    # Assert
    assert result.returncode == 0
    assert parse_section(result.stdout, "Overlap") == []


def test_shared_base_migration_flags_shared_bases_signal(repo: GitRepo) -> None:
    # Arrange
    repo.write_text("A/existing.py", "base\n")
    repo.write_text("B/models.py", "base\n")
    write_app_structure(repo, "A --> B")
    old_base = repo.commit("base")
    spec_dir = make_spec_dir(repo, "Nothing named here.\n")
    repo.write_text("B/models.py", "main changes B's models\n")
    new_base = repo.commit("main changes B/models.py")
    repo.checkout_new_branch("feature", new_base)
    repo.write_text("A/existing.py", "branch's own change to A\n")
    repo.commit("branch changes its own app A")

    # Act
    result = _run_script([old_base, new_base, spec_dir], repo.path, repo.env)

    # Assert
    assert result.returncode == 2
    assert parse_section(result.stdout, "Shared bases") == ["B/models.py"]
    assert parse_section(result.stdout, "Overlap") == []


def test_shared_base_signal_absent_without_dependency_edge(repo: GitRepo) -> None:
    # Arrange
    repo.write_text("A/existing.py", "base\n")
    repo.write_text("B/models.py", "base\n")
    write_app_structure(repo, "C --> D")
    old_base = repo.commit("base")
    spec_dir = make_spec_dir(repo, "Nothing named here.\n")
    repo.write_text("B/models.py", "main changes B's models\n")
    new_base = repo.commit("main changes B/models.py")
    repo.checkout_new_branch("feature", new_base)
    repo.write_text("A/existing.py", "branch's own change to A\n")
    repo.commit("branch changes its own app A")

    # Act
    result = _run_script([old_base, new_base, spec_dir], repo.path, repo.env)

    # Assert
    assert result.returncode == 0
    assert parse_section(result.stdout, "Shared bases") == []


def test_skill_file_change_flags_conventions_signal(repo: GitRepo) -> None:
    # Arrange
    repo.write_text("claude_plugins/ds/skills/testing/SKILL.md", "base\n")
    old_base = repo.commit("base")
    spec_dir = make_spec_dir(repo, "Nothing named here.\n")
    repo.write_text("claude_plugins/ds/skills/testing/SKILL.md", "changed\n")
    new_base = repo.commit("main changes a skill")

    # Act
    result = _run_script([old_base, new_base, spec_dir], repo.path, repo.env)

    # Assert
    assert result.returncode == 2
    assert parse_section(result.stdout, "Conventions") == [
        "claude_plugins/ds/skills/testing/SKILL.md"
    ]


def test_new_done_spec_directory_flags_done_specs_signal(repo: GitRepo) -> None:
    # Arrange
    repo.write_text("unrelated.txt", "base\n")
    old_base = repo.commit("base")
    spec_dir = make_spec_dir(repo, "Nothing named here.\n")
    repo.write_text("spec_dd/3. done/other_spec/idea.md", "an idea\n")
    new_base = repo.commit("main finishes another spec")

    # Act
    result = _run_script([old_base, new_base, spec_dir], repo.path, repo.env)

    # Assert
    assert result.returncode == 2
    assert parse_section(result.stdout, "Done specs") == [
        "spec_dd/3. done/other_spec/idea.md"
    ]


def test_long_diff_is_truncated_with_a_marker(repo: GitRepo) -> None:
    # Arrange
    skill_path = "claude_plugins/ds/skills/testing/SKILL.md"
    repo.write_text(skill_path, "base\n")
    old_base = repo.commit("base")
    spec_dir = make_spec_dir(repo, "Nothing named here.\n")
    long_content = "\n".join(f"line {n}" for n in range(500)) + "\n"
    repo.write_text(skill_path, long_content)
    new_base = repo.commit("main rewrites a skill file at length")

    # Act
    result = _run_script([old_base, new_base, spec_dir], repo.path, repo.env)

    # Assert
    assert result.returncode == 2
    assert "truncated at 400 lines" in result.stdout
    block = diff_block(result.stdout, skill_path)
    assert any("truncated at 400 lines" in line for line in block)


def test_missing_spec_directory_exits_with_usage_error(repo: GitRepo) -> None:
    # Arrange
    repo.write_text("unrelated.txt", "base\n")
    old_base = repo.commit("base")
    repo.write_text("unrelated.txt", "changed\n")
    new_base = repo.commit("main changes an unrelated file")
    missing_spec_dir = "spec_dd/2. in progress/does not exist"

    # Act
    result = _run_script([old_base, new_base, missing_spec_dir], repo.path, repo.env)

    # Assert
    assert result.returncode == 64


def test_non_ref_argument_exits_with_usage_error(repo: GitRepo) -> None:
    # Arrange
    repo.write_text("unrelated.txt", "base\n")
    old_base = repo.commit("base")
    spec_dir = make_spec_dir(repo, "Nothing named here.\n")

    # Act
    result = _run_script([old_base, "not-a-real-ref", spec_dir], repo.path, repo.env)

    # Assert
    assert result.returncode == 64
