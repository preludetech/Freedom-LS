"""Tests for the content_validate command."""

from pathlib import Path

import pytest

from django.core.management import call_command

from freedom_ls.tests.git_repos import init_repo

INVALID_TOPIC = "---\ncontent_type: NOT_A_TYPE\ntitle: Broken\n---\n"


def _repo_with_invalid_file(root: Path) -> Path:
    init_repo(root)
    drafts = root / "drafts"
    drafts.mkdir()
    (drafts / "broken.md").write_text(INVALID_TOPIC)
    (root / "good.md").write_text(
        "---\ncontent_type: TOPIC\ntitle: Good\n---\n\nBody.\n"
    )
    return root


def test_a_tree_whose_only_invalid_file_is_ignored_validates(tmp_path: Path) -> None:
    root = _repo_with_invalid_file(tmp_path)
    (root / ".fls-content.yaml").write_text("ignore:\n  - drafts\n")

    call_command("content_validate", str(root))


def test_the_same_tree_without_the_ignore_entry_fails(tmp_path: Path) -> None:
    root = _repo_with_invalid_file(tmp_path)
    (root / ".fls-content.yaml").write_text("ignore: []\n")

    with pytest.raises(ValueError, match="Validation failed"):
        call_command("content_validate", str(root))


def test_a_tree_with_no_config_file_validates_as_before(tmp_path: Path) -> None:
    root = _repo_with_invalid_file(tmp_path)
    (root / "drafts" / "broken.md").unlink()

    call_command("content_validate", str(root))
