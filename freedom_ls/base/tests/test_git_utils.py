from collections.abc import Iterator
from pathlib import Path

import pytest
from dulwich import porcelain

from freedom_ls.base.git_utils import (
    UncommittedPath,
    _clear_branch_cache,
    branch_to_db_name,
    find_repo_root,
    get_current_branch,
    get_head_commit,
    head_commit_of,
    submodule_paths,
    tracked_files,
    uncommitted_paths,
)
from freedom_ls.tests.git_repos import (
    add_committed_submodule,
    add_linked_worktree,
    commit_all,
    detach_head,
    init_repo,
    pack_all_refs,
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


# --- get_head_commit ---


SHA = "abc1234def5678901234567890abcdef12345678"  # pragma: allowlist secret
SHA2 = "1111111111111111111111111111111111111111"  # pragma: allowlist secret


class TestGetHeadCommit:
    def test_detached_head_returns_sha(self, tmp_path: Path) -> None:
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "HEAD").write_text(f"{SHA}\n")

        assert get_head_commit(base_dir=tmp_path) == SHA

    def test_loose_ref_returns_sha(self, tmp_path: Path) -> None:
        git_dir = tmp_path / ".git"
        (git_dir / "refs" / "heads").mkdir(parents=True)
        (git_dir / "HEAD").write_text("ref: refs/heads/main\n")
        (git_dir / "refs" / "heads" / "main").write_text(f"{SHA}\n")

        assert get_head_commit(base_dir=tmp_path) == SHA

    def test_packed_ref_returns_sha(self, tmp_path: Path) -> None:
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "HEAD").write_text("ref: refs/heads/main\n")
        (git_dir / "packed-refs").write_text(
            f"# pack-refs with: peeled fully-peeled sorted\n{SHA} refs/heads/main\n"
        )

        assert get_head_commit(base_dir=tmp_path) == SHA

    def test_worktree_resolves_ref_via_commondir(self, tmp_path: Path) -> None:
        """In a git worktree, refs live in the common git dir, not the
        per-worktree git dir. The per-worktree dir contains a `commondir`
        file pointing at the common dir (typically `../..`)."""
        common_dir = tmp_path / "common"
        (common_dir / "refs" / "heads").mkdir(parents=True)
        (common_dir / "refs" / "heads" / "feature").write_text(f"{SHA}\n")

        worktree_git_dir = common_dir / "worktrees" / "feature"
        worktree_git_dir.mkdir(parents=True)
        (worktree_git_dir / "HEAD").write_text("ref: refs/heads/feature\n")
        (worktree_git_dir / "commondir").write_text("../..\n")

        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".git").write_text(f"gitdir: {worktree_git_dir}\n")

        assert get_head_commit(base_dir=repo) == SHA

    def test_worktree_resolves_packed_ref_via_commondir(self, tmp_path: Path) -> None:
        common_dir = tmp_path / "common"
        common_dir.mkdir()
        (common_dir / "packed-refs").write_text(f"{SHA2} refs/heads/feature\n")

        worktree_git_dir = common_dir / "worktrees" / "feature"
        worktree_git_dir.mkdir(parents=True)
        (worktree_git_dir / "HEAD").write_text("ref: refs/heads/feature\n")
        (worktree_git_dir / "commondir").write_text("../..\n")

        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".git").write_text(f"gitdir: {worktree_git_dir}\n")

        assert get_head_commit(base_dir=repo) == SHA2

    def test_no_git_dir_returns_none(self, tmp_path: Path) -> None:
        assert get_head_commit(base_dir=tmp_path) is None

    def test_unresolvable_ref_returns_none(self, tmp_path: Path) -> None:
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "HEAD").write_text("ref: refs/heads/missing\n")

        assert get_head_commit(base_dir=tmp_path) is None


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


def test_find_repo_root_at_the_repo_root_returns_it(
    committed_content_repo: Path,
) -> None:
    assert find_repo_root(committed_content_repo) == committed_content_repo.resolve()


def test_find_repo_root_outside_any_repo_returns_none(tmp_path: Path) -> None:
    assert find_repo_root(tmp_path) is None


def test_uncommitted_paths_on_a_clean_tree_is_empty(
    committed_content_repo: Path,
) -> None:
    assert uncommitted_paths(committed_content_repo) == []


def _modify(repo: Path) -> None:
    (repo / "topic.md").write_text("changed\n")


def _stage(repo: Path) -> None:
    (repo / "topic.md").write_text("changed\n")
    porcelain.add(str(repo), paths=[str(repo / "topic.md")])


def _delete(repo: Path) -> None:
    (repo / "topic.md").unlink()


def _add_untracked(repo: Path) -> None:
    (repo / "new.md").write_text("new\n")


@pytest.mark.parametrize(
    ("change", "name", "kind"),
    [
        (_modify, "topic.md", "modified"),
        (_stage, "topic.md", "staged"),
        (_delete, "topic.md", "deleted"),
        (_add_untracked, "new.md", "untracked"),
    ],
)
def test_uncommitted_paths_reports_each_kind_of_change(
    committed_content_repo: Path, change, name: str, kind: str
) -> None:
    change(committed_content_repo)

    assert uncommitted_paths(committed_content_repo) == [UncommittedPath(name, kind)]


def test_head_commit_of_returns_the_committed_sha(committed_content_repo: Path) -> None:
    (committed_content_repo / "second.md").write_text("second\n")
    sha = commit_all(committed_content_repo)

    assert head_commit_of(committed_content_repo) == sha


def test_head_commit_of_a_repo_with_no_commits_raises(tmp_path: Path) -> None:
    init_repo(tmp_path / "empty")

    with pytest.raises(ValueError, match="no commits"):
        head_commit_of(tmp_path / "empty")


@pytest.fixture
def repo_with_subdirectory(committed_content_repo: Path) -> Path:
    """The committed repo plus a committed `courses/` subdirectory."""
    (committed_content_repo / "courses").mkdir()
    (committed_content_repo / "courses" / "intro.md").write_text("intro\n")
    commit_all(committed_content_repo)
    return committed_content_repo


def test_find_repo_root_from_a_subdirectory_returns_the_repo_root(
    repo_with_subdirectory: Path,
) -> None:
    assert (
        find_repo_root(repo_with_subdirectory / "courses")
        == repo_with_subdirectory.resolve()
    )


def test_find_repo_root_from_a_file_returns_the_repo_root(
    repo_with_subdirectory: Path,
) -> None:
    assert (
        find_repo_root(repo_with_subdirectory / "courses" / "intro.md")
        == repo_with_subdirectory.resolve()
    )


def test_uncommitted_paths_reports_only_what_is_under_the_subdirectory(
    repo_with_subdirectory: Path,
) -> None:
    (repo_with_subdirectory / "topic.md").write_text("changed\n")
    (repo_with_subdirectory / "courses" / "new.md").write_text("new\n")

    assert uncommitted_paths(repo_with_subdirectory / "courses") == [
        UncommittedPath("courses/new.md", "untracked")
    ]


def test_uncommitted_paths_for_a_single_file_reports_that_file_only(
    repo_with_subdirectory: Path,
) -> None:
    (repo_with_subdirectory / "topic.md").write_text("changed\n")
    (repo_with_subdirectory / "courses" / "intro.md").write_text("changed\n")

    assert uncommitted_paths(repo_with_subdirectory / "topic.md") == [
        UncommittedPath("topic.md", "modified")
    ]


def test_uncommitted_paths_for_a_staged_then_modified_file_is_one_entry(
    committed_content_repo: Path,
) -> None:
    _stage(committed_content_repo)
    (committed_content_repo / "topic.md").write_text("changed again\n")

    assert uncommitted_paths(committed_content_repo) == [
        UncommittedPath("topic.md", "staged, modified")
    ]


def test_uncommitted_paths_for_a_staged_then_deleted_file_is_one_entry(
    committed_content_repo: Path,
) -> None:
    _stage(committed_content_repo)
    _delete(committed_content_repo)

    assert uncommitted_paths(committed_content_repo) == [
        UncommittedPath("topic.md", "staged, deleted")
    ]


def test_uncommitted_paths_ignores_a_gitignored_file(
    committed_content_repo: Path,
) -> None:
    (committed_content_repo / ".gitignore").write_text("ignored.md\n")
    commit_all(committed_content_repo)
    (committed_content_repo / "ignored.md").write_text("ignored\n")

    assert uncommitted_paths(committed_content_repo) == []


@pytest.fixture
def linked_worktree(committed_content_repo: Path, tmp_path: Path) -> Path:
    worktree_dir = tmp_path / "linked_worktree"
    add_linked_worktree(committed_content_repo, worktree_dir)
    return worktree_dir


def test_find_repo_root_in_a_linked_worktree_returns_the_worktree(
    linked_worktree: Path,
) -> None:
    assert find_repo_root(linked_worktree) == linked_worktree.resolve()


def test_uncommitted_paths_in_a_linked_worktree_are_the_worktrees_own(
    committed_content_repo: Path, linked_worktree: Path
) -> None:
    (linked_worktree / "topic.md").write_text("changed in the worktree\n")

    assert uncommitted_paths(linked_worktree) == [
        UncommittedPath("topic.md", "modified")
    ]
    assert uncommitted_paths(committed_content_repo) == []


def test_head_commit_of_a_linked_worktree_follows_the_worktrees_own_head(
    committed_content_repo: Path, linked_worktree: Path
) -> None:
    (linked_worktree / "second.md").write_text("second\n")
    sha = commit_all(linked_worktree)

    assert head_commit_of(linked_worktree) == sha
    assert head_commit_of(committed_content_repo) != sha


def test_head_commit_of_a_detached_head_returns_the_commit(
    committed_content_repo: Path,
) -> None:
    sha = detach_head(committed_content_repo)

    assert head_commit_of(committed_content_repo) == sha


def test_head_commit_of_packed_refs_returns_the_commit(
    committed_content_repo: Path,
) -> None:
    sha = head_commit_of(committed_content_repo)
    pack_all_refs(committed_content_repo)

    assert head_commit_of(committed_content_repo) == sha


def _tracking_fixture_files(repo: Path) -> None:
    """Add a staged file, an untracked file and a gitignored file to a committed repo."""
    (repo / ".gitignore").write_text("ignored.md\n")
    commit_all(repo)
    (repo / "staged.md").write_text("staged\n")
    porcelain.add(str(repo), paths=[str(repo / "staged.md")])
    (repo / "untracked.md").write_text("untracked\n")
    (repo / "ignored.md").write_text("ignored\n")


def test_tracked_files_holds_committed_and_staged_files_only(
    committed_content_repo: Path,
) -> None:
    _tracking_fixture_files(committed_content_repo)
    root = committed_content_repo.resolve()

    assert tracked_files(committed_content_repo) == frozenset(
        {root / "topic.md", root / ".gitignore", root / "staged.md"}
    )


def test_tracked_files_from_a_subdirectory_covers_the_whole_repo(
    committed_content_repo: Path,
) -> None:
    (committed_content_repo / "courses").mkdir()

    assert (committed_content_repo.resolve() / "topic.md") in tracked_files(
        committed_content_repo / "courses"
    )


def test_tracked_files_in_a_linked_worktree_are_the_worktrees_own(
    committed_content_repo: Path, linked_worktree: Path
) -> None:
    (linked_worktree / "staged.md").write_text("staged\n")
    porcelain.add(str(linked_worktree), paths=[str(linked_worktree / "staged.md")])

    assert tracked_files(linked_worktree) == frozenset(
        {
            linked_worktree.resolve() / "topic.md",
            linked_worktree.resolve() / "staged.md",
        }
    )


def test_submodule_paths_lists_a_committed_submodule(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    init_repo(repo_dir)
    (repo_dir / "topic.md").write_text("topic\n")
    commit_all(repo_dir)
    add_committed_submodule(repo_dir, "assets")

    assert submodule_paths(repo_dir) == ["assets"]


def test_submodule_paths_leaves_out_a_submodule_outside_the_path(
    tmp_path: Path,
) -> None:
    repo_dir = tmp_path / "repo"
    init_repo(repo_dir)
    (repo_dir / "courses").mkdir()
    (repo_dir / "courses" / "topic.md").write_text("topic\n")
    commit_all(repo_dir)
    add_committed_submodule(repo_dir, "assets")

    assert submodule_paths(repo_dir / "courses") == []
