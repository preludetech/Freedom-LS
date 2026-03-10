from pathlib import Path
from unittest.mock import patch

import pytest

from django.test import RequestFactory

from freedom_ls.base.context_processors import (
    branch_name_to_color,
    debug_branch_info,
    get_current_branch,
    get_text_color,
)


@pytest.fixture(autouse=True)
def _reset_branch_cache() -> None:
    get_current_branch.cache_clear()


# --- Task 1: get_current_branch ---


class TestGetCurrentBranch:
    def test_normal_git_head_returns_branch_name(self, tmp_path: Path) -> None:
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "HEAD").write_text("ref: refs/heads/main\n")

        with patch("freedom_ls.base.context_processors.settings") as mock_settings:
            mock_settings.BASE_DIR = tmp_path
            result = get_current_branch()

        assert result == "main"

    def test_worktree_git_file_returns_branch_name(self, tmp_path: Path) -> None:
        actual_git_dir = tmp_path / "actual_git" / "worktrees" / "my-worktree"
        actual_git_dir.mkdir(parents=True)
        (actual_git_dir / "HEAD").write_text("ref: refs/heads/feature-branch\n")

        git_file = tmp_path / ".git"
        git_file.write_text(f"gitdir: {actual_git_dir}\n")

        with patch("freedom_ls.base.context_processors.settings") as mock_settings:
            mock_settings.BASE_DIR = tmp_path
            result = get_current_branch()

        assert result == "feature-branch"

    def test_worktree_relative_gitdir_path(self, tmp_path: Path) -> None:
        worktree_dir = tmp_path / ".bare" / "worktrees" / "wt"
        worktree_dir.mkdir(parents=True)
        (worktree_dir / "HEAD").write_text("ref: refs/heads/relative-branch\n")

        git_file = tmp_path / ".git"
        relative = Path(".bare") / "worktrees" / "wt"
        git_file.write_text(f"gitdir: {relative}\n")

        with patch("freedom_ls.base.context_processors.settings") as mock_settings:
            mock_settings.BASE_DIR = tmp_path
            result = get_current_branch()

        assert result == "relative-branch"

    def test_detached_head_returns_short_sha(self, tmp_path: Path) -> None:
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        sha = "abc1234def5678901234567890abcdef12345678"  # pragma: allowlist secret
        (git_dir / "HEAD").write_text(f"{sha}\n")

        with patch("freedom_ls.base.context_processors.settings") as mock_settings:
            mock_settings.BASE_DIR = tmp_path
            result = get_current_branch()

        assert result == "abc1234"

    def test_no_git_path_returns_none(self, tmp_path: Path) -> None:
        with patch("freedom_ls.base.context_processors.settings") as mock_settings:
            mock_settings.BASE_DIR = tmp_path
            result = get_current_branch()

        assert result is None

    def test_malformed_git_file_returns_none(self, tmp_path: Path) -> None:
        git_file = tmp_path / ".git"
        git_file.write_text("not a valid gitdir line\n")

        with patch("freedom_ls.base.context_processors.settings") as mock_settings:
            mock_settings.BASE_DIR = tmp_path
            result = get_current_branch()

        assert result is None

    def test_caching_returns_cached_value(self, tmp_path: Path) -> None:
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "HEAD").write_text("ref: refs/heads/cached-branch\n")

        with patch("freedom_ls.base.context_processors.settings") as mock_settings:
            mock_settings.BASE_DIR = tmp_path
            first = get_current_branch()

        (git_dir / "HEAD").write_text("ref: refs/heads/different-branch\n")

        second = get_current_branch()

        assert first == "cached-branch"
        assert second == "cached-branch"

    def test_head_file_missing_returns_none(self, tmp_path: Path) -> None:
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        # No HEAD file created

        with patch("freedom_ls.base.context_processors.settings") as mock_settings:
            mock_settings.BASE_DIR = tmp_path
            result = get_current_branch()

        assert result is None


# --- Task 2: Color generation ---


class TestBranchNameToColor:
    def test_same_name_produces_same_color(self) -> None:
        assert branch_name_to_color("main") == branch_name_to_color("main")

    def test_different_names_produce_different_colors(self) -> None:
        assert branch_name_to_color("main") != branch_name_to_color("develop")

    def test_returns_valid_hex_color(self) -> None:
        color = branch_name_to_color("feature-x")
        assert color.startswith("#")
        assert len(color) == 7
        int(color[1:], 16)  # should not raise

    def test_known_input_output(self) -> None:
        assert branch_name_to_color("main") == "#a937b4"


class TestGetTextColor:
    def test_light_background_returns_black(self) -> None:
        assert get_text_color("#ffffff") == "#000000"

    def test_dark_background_returns_white(self) -> None:
        assert get_text_color("#000000") == "#ffffff"

    def test_medium_light_returns_black(self) -> None:
        assert get_text_color("#aabbcc") == "#000000"

    def test_dark_blue_returns_white(self) -> None:
        assert get_text_color("#001144") == "#ffffff"


# --- Task 4: Settings isolation ---


class TestDebugBranchNotInProdSettings:
    def test_not_in_base_settings_source(self) -> None:
        from django.conf import settings

        base_settings_path = Path(settings.BASE_DIR) / "config" / "settings_base.py"
        content = base_settings_path.read_text()
        assert "debug_branch_info" not in content

    def test_not_in_prod_settings_source(self) -> None:
        from django.conf import settings

        prod_settings_path = Path(settings.BASE_DIR) / "config" / "settings_prod.py"
        content = prod_settings_path.read_text()
        assert "debug_branch_info" not in content


# --- Task 3: Context processor ---


class TestDebugBranchInfo:
    def test_returns_all_keys_when_branch_detected(self, tmp_path: Path) -> None:
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "HEAD").write_text("ref: refs/heads/my-feature\n")

        factory = RequestFactory()
        request = factory.get("/")

        with patch("freedom_ls.base.context_processors.settings") as mock_settings:
            mock_settings.BASE_DIR = tmp_path
            mock_settings.DEBUG = True
            result = debug_branch_info(request)

        assert result["debug_branch_name"] == "my-feature"
        assert result["debug_branch_color"].startswith("#")
        assert result["debug_branch_text_color"] in ("#000000", "#ffffff")

    def test_returns_empty_dict_when_no_branch(self, tmp_path: Path) -> None:
        factory = RequestFactory()
        request = factory.get("/")

        with patch("freedom_ls.base.context_processors.settings") as mock_settings:
            mock_settings.BASE_DIR = tmp_path
            mock_settings.DEBUG = True
            result = debug_branch_info(request)

        assert result == {}

    def test_returns_empty_dict_when_debug_false(self, tmp_path: Path) -> None:
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "HEAD").write_text("ref: refs/heads/my-feature\n")

        factory = RequestFactory()
        request = factory.get("/")

        with patch("freedom_ls.base.context_processors.settings") as mock_settings:
            mock_settings.BASE_DIR = tmp_path
            mock_settings.DEBUG = False
            result = debug_branch_info(request)

        assert result == {}
