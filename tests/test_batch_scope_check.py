"""Tests for the script that keeps a batch's boy-scout commits inside its own touched files.

This test assumes `claude_plugins/` sits at the project root, so the script it exercises is
`claude_plugins/sdd/scripts/batch_scope_check.sh`. No database is needed: the script only ever
talks to a git repository built by hand in `tmp_path`.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "claude_plugins" / "sdd" / "scripts" / "batch_scope_check.sh"

GIT_ENV_OVERRIDES = {
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Scope Check Test",
    "GIT_AUTHOR_EMAIL": "scope-check-test@example.com",
    "GIT_COMMITTER_NAME": "Scope Check Test",
    "GIT_COMMITTER_EMAIL": "scope-check-test@example.com",
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

    def checkout_new_branch(self, branch: str, start_point: str) -> None:
        _run_git(["checkout", "-q", "-b", branch, start_point], self.path, self.env)

    def git_mv(self, old_path: str, new_path: str) -> None:
        _run_git(["mv", old_path, new_path], self.path, self.env)

    def remove(self, relative_path: str) -> None:
        _run_git(["rm", "-q", relative_path], self.path, self.env)


@pytest.fixture
def repo(tmp_path: Path) -> GitRepo:
    env = {**os.environ, **GIT_ENV_OVERRIDES, "HOME": str(tmp_path)}
    _run_git(["init", "-q", "-b", "main"], tmp_path, env)
    git_repo = GitRepo(path=tmp_path, env=env)
    git_repo.write_text("README.md", "base\n")
    base = git_repo.commit("base")
    _run_git(["update-ref", "refs/remotes/origin/main", base], tmp_path, env)
    git_repo.checkout_new_branch("feature", base)
    return git_repo


def add_batch(repo: GitRepo, n: int, paths: dict[str, str]) -> str:
    """Write and commit `[batch n] implement`, touching each of `paths` (path -> content)."""
    for path, content in paths.items():
        repo.write_text(path, content)
    return repo.commit(f"[batch {n}] implement")


def test_boy_scout_modify_inside_allowed_set_passes(repo: GitRepo) -> None:
    # Arrange
    from_ref = add_batch(
        repo, 1, {"freedom_ls/app_a/tests/test_models.py": "content\n"}
    )
    repo.write_text("freedom_ls/app_a/tests/test_models.py", "content, tidied\n")
    repo.commit("[batch 1 boy-scout] edit tidy import")

    # Act
    result = _run_script(["1", from_ref], repo.path, repo.env)

    # Assert
    assert result.returncode == 0


def test_boy_scout_move_of_allowed_file_then_edit_at_new_path_passes(
    repo: GitRepo,
) -> None:
    # Arrange
    from_ref = add_batch(
        repo, 1, {"freedom_ls/app_a/tests/test_models.py": "content\n"}
    )
    repo.git_mv(
        "freedom_ls/app_a/tests/test_models.py", "freedom_ls/app_a/tests/test_model.py"
    )
    repo.commit(
        "[batch 1 boy-scout] move freedom_ls/app_a/tests/test_models.py -> "
        "freedom_ls/app_a/tests/test_model.py"
    )
    repo.write_text("freedom_ls/app_a/tests/test_model.py", "content, renamed\n")
    repo.commit("[batch 1 boy-scout] edit fix import after rename")

    # Act
    result = _run_script(["1", from_ref], repo.path, repo.env)

    # Assert
    assert result.returncode == 0


def test_boy_scout_modify_outside_allowed_set_fails_and_names_it(repo: GitRepo) -> None:
    # Arrange
    repo.write_text("freedom_ls/app_b/models.py", "existing\n")
    repo.commit("pre-existing app_b model")
    from_ref = add_batch(
        repo, 1, {"freedom_ls/app_a/tests/test_models.py": "content\n"}
    )
    repo.write_text("freedom_ls/app_b/models.py", "changed\n")
    repo.commit("[batch 1 boy-scout] edit accidentally touches app_b")

    # Act
    result = _run_script(["1", from_ref], repo.path, repo.env)

    # Assert
    assert result.returncode == 1
    assert "OUT_OF_SCOPE:" in result.stdout
    assert "freedom_ls/app_b/models.py" in result.stdout


def test_new_file_under_same_app_tests_dir_passes(repo: GitRepo) -> None:
    # Arrange
    from_ref = add_batch(
        repo, 1, {"freedom_ls/app_a/tests/test_models.py": "content\n"}
    )
    repo.write_text("freedom_ls/app_a/tests/test_helpers.py", "helper\n")
    repo.commit("[batch 1 boy-scout] edit split helper out")

    # Act
    result = _run_script(["1", from_ref], repo.path, repo.env)

    # Assert
    assert result.returncode == 0


def test_new_file_under_another_app_fails(repo: GitRepo) -> None:
    # Arrange
    from_ref = add_batch(
        repo, 1, {"freedom_ls/app_a/tests/test_models.py": "content\n"}
    )
    repo.write_text("freedom_ls/app_b/tests/test_helpers.py", "helper\n")
    repo.commit("[batch 1 boy-scout] edit add fixture in the wrong app")

    # Act
    result = _run_script(["1", from_ref], repo.path, repo.env)

    # Assert
    assert result.returncode == 1
    assert "freedom_ls/app_b/tests/test_helpers.py" in result.stdout


def test_delete_that_is_not_a_rename_fails(repo: GitRepo) -> None:
    # Arrange
    from_ref = add_batch(
        repo, 1, {"freedom_ls/app_a/tests/test_models.py": "content\n"}
    )
    repo.remove("freedom_ls/app_a/tests/test_models.py")
    repo.commit("[batch 1 boy-scout] edit remove stale test")

    # Act
    result = _run_script(["1", from_ref], repo.path, repo.env)

    # Assert
    assert result.returncode == 1
    assert "freedom_ls/app_a/tests/test_models.py" in result.stdout


def test_path_touched_only_by_review_fix_commit_is_allowed(repo: GitRepo) -> None:
    # Arrange
    add_batch(repo, 1, {"freedom_ls/app_a/tests/test_models.py": "content\n"})
    repo.write_text("freedom_ls/app_a/tests/test_fixture.py", "fixture\n")
    from_ref = repo.commit("[batch 1 review-fix] add missing fixture")
    repo.write_text("freedom_ls/app_a/tests/test_fixture.py", "fixture, tidied\n")
    repo.commit("[batch 1 boy-scout] edit tidy fixture")

    # Act
    result = _run_script(["1", from_ref], repo.path, repo.env)

    # Assert
    assert result.returncode == 0


def test_other_batch_number_does_not_widen_allowed_set(repo: GitRepo) -> None:
    # Arrange
    add_batch(repo, 1, {"freedom_ls/app_a/tests/test_models.py": "content\n"})
    from_ref = add_batch(
        repo, 11, {"freedom_ls/app_b/tests/test_other.py": "content\n"}
    )
    repo.write_text("freedom_ls/app_b/tests/test_other.py", "changed\n")
    repo.commit("[batch 1 boy-scout] edit touches batch 11 file")

    # Act
    result = _run_script(["1", from_ref], repo.path, repo.env)

    # Assert
    assert result.returncode == 1
    assert "freedom_ls/app_b/tests/test_other.py" in result.stdout


def test_non_boy_scout_commit_in_range_is_not_checked(repo: GitRepo) -> None:
    # Arrange
    from_ref = add_batch(
        repo, 1, {"freedom_ls/app_a/tests/test_models.py": "content\n"}
    )
    repo.write_text("freedom_ls/app_z/whatever.py", "new\n")
    repo.commit("chore: unrelated tidy, not a boy-scout commit")

    # Act
    result = _run_script(["1", from_ref], repo.path, repo.env)

    # Assert
    assert result.returncode == 0


@pytest.mark.parametrize(
    "args_factory",
    [
        lambda from_ref: [],
        lambda from_ref: ["abc", from_ref],
        lambda from_ref: ["1", "not-a-real-ref"],
    ],
    ids=["no_args", "non_numeric_batch", "unknown_ref"],
)
def test_bad_arguments_exit_64(
    repo: GitRepo, args_factory: Callable[[str], list[str]]
) -> None:
    # Arrange
    from_ref = add_batch(
        repo, 1, {"freedom_ls/app_a/tests/test_models.py": "content\n"}
    )

    # Act
    result = _run_script(args_factory(from_ref), repo.path, repo.env)

    # Assert
    assert result.returncode == 64
