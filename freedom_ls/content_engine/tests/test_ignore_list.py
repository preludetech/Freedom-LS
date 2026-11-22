"""Tests for finding the ignore list that applies to a source path."""

from pathlib import Path

from freedom_ls.content_engine.ignore_list import ignore_list_for
from freedom_ls.content_engine.validate import content_key
from freedom_ls.tests.git_repos import init_repo


def test_a_path_in_a_repo_with_a_list_gets_the_repos_ignore_list(
    tmp_path: Path,
) -> None:
    init_repo(tmp_path)
    (tmp_path / ".fls-content.yaml").write_text("ignore:\n  - drafts\n")

    assert ignore_list_for(tmp_path) == {content_key(tmp_path / "drafts")}


def test_entries_resolve_against_the_repo_root_for_a_subdirectory_path(
    tmp_path: Path,
) -> None:
    init_repo(tmp_path)
    (tmp_path / ".fls-content.yaml").write_text("ignore:\n  - drafts\n")
    (tmp_path / "courses").mkdir()

    assert ignore_list_for(tmp_path / "courses") == {content_key(tmp_path / "drafts")}


def test_a_repo_without_a_config_file_has_an_empty_list(tmp_path: Path) -> None:
    init_repo(tmp_path)

    assert ignore_list_for(tmp_path) == frozenset()


def test_a_path_outside_any_repo_has_an_empty_list(tmp_path: Path) -> None:
    assert ignore_list_for(tmp_path) == frozenset()
