from collections.abc import Iterator
from pathlib import Path

import pytest

from freedom_ls.base.git_utils import (
    _clear_branch_cache,
    branch_to_db_name,
    get_current_branch,
)


@pytest.fixture(autouse=True)
def _reset_branch_cache() -> Iterator[None]:
    _clear_branch_cache()
    yield
    _clear_branch_cache()


# --- get_current_branch with explicit base_dir ---


class TestGetCurrentBranch:
    def test_normal_git_head_returns_branch_name(self, tmp_path: Path) -> None:
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "HEAD").write_text("ref: refs/heads/main\n")

        result = get_current_branch(base_dir=tmp_path)
        assert result == "main"

    def test_worktree_git_file_returns_branch_name(self, tmp_path: Path) -> None:
        actual_git_dir = tmp_path / "actual_git" / "worktrees" / "my-worktree"
        actual_git_dir.mkdir(parents=True)
        (actual_git_dir / "HEAD").write_text("ref: refs/heads/feature-branch\n")

        git_file = tmp_path / ".git"
        git_file.write_text(f"gitdir: {actual_git_dir}\n")

        result = get_current_branch(base_dir=tmp_path)
        assert result == "feature-branch"

    def test_worktree_relative_gitdir_path(self, tmp_path: Path) -> None:
        worktree_dir = tmp_path / ".bare" / "worktrees" / "wt"
        worktree_dir.mkdir(parents=True)
        (worktree_dir / "HEAD").write_text("ref: refs/heads/relative-branch\n")

        git_file = tmp_path / ".git"
        relative = Path(".bare") / "worktrees" / "wt"
        git_file.write_text(f"gitdir: {relative}\n")

        result = get_current_branch(base_dir=tmp_path)
        assert result == "relative-branch"

    def test_detached_head_returns_short_sha(self, tmp_path: Path) -> None:
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        sha = "abc1234def5678901234567890abcdef12345678"  # pragma: allowlist secret
        (git_dir / "HEAD").write_text(f"{sha}\n")

        result = get_current_branch(base_dir=tmp_path)
        assert result == "abc1234"

    def test_no_git_path_returns_none(self, tmp_path: Path) -> None:
        result = get_current_branch(base_dir=tmp_path)
        assert result is None

    def test_malformed_git_file_returns_none(self, tmp_path: Path) -> None:
        git_file = tmp_path / ".git"
        git_file.write_text("not a valid gitdir line\n")

        result = get_current_branch(base_dir=tmp_path)
        assert result is None

    def test_head_file_missing_returns_none(self, tmp_path: Path) -> None:
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        # No HEAD file created

        result = get_current_branch(base_dir=tmp_path)
        assert result is None


class TestGetCurrentBranchNoBaseDir:
    def test_uses_settings_base_dir_when_no_arg(
        self, tmp_path: Path, settings: object
    ) -> None:
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "HEAD").write_text("ref: refs/heads/settings-branch\n")

        settings.BASE_DIR = tmp_path
        result = get_current_branch()

        assert result == "settings-branch"


class TestGetCurrentBranchCaching:
    def test_second_call_returns_cached_value(self, tmp_path: Path) -> None:
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "HEAD").write_text("ref: refs/heads/cached-branch\n")

        first = get_current_branch(base_dir=tmp_path)
        (git_dir / "HEAD").write_text("ref: refs/heads/different-branch\n")
        second = get_current_branch(base_dir=tmp_path)

        assert first == "cached-branch"
        assert second == "cached-branch"

    def test_clear_cache_resets(self, tmp_path: Path) -> None:
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "HEAD").write_text("ref: refs/heads/first-branch\n")

        first = get_current_branch(base_dir=tmp_path)
        assert first == "first-branch"

        (git_dir / "HEAD").write_text("ref: refs/heads/second-branch\n")
        _clear_branch_cache()

        second = get_current_branch(base_dir=tmp_path)
        assert second == "second-branch"


# --- branch_to_db_name ---


class TestBranchToDbName:
    def test_lowercase(self) -> None:
        assert branch_to_db_name("MAIN") == "db_main"

    def test_replaces_slash_dash_dot(self) -> None:
        assert branch_to_db_name("feature/auth-flow") == "db_feature_auth_flow"

    def test_prefix_with_db(self) -> None:
        assert branch_to_db_name("main") == "db_main"

    def test_truncates_to_50_chars(self) -> None:
        long_branch = "a" * 60
        result = branch_to_db_name(long_branch)
        # db_ prefix + 50 chars = 53 total
        assert result == "db_" + "a" * 50
        assert len(result) == 53

    def test_hotfix_with_dots(self) -> None:
        assert branch_to_db_name("hotfix-2.1") == "db_hotfix_2_1"
