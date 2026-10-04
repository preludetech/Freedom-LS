"""Tests for the content scanner's file discovery."""

from pathlib import Path

from freedom_ls.content_engine.validate import get_all_files


def test_get_all_files_skips_widget_declarations(tmp_path: Path) -> None:
    """Widget declarations live in the dot-prefixed `.claude/` directory,
    which is never scanned as content."""
    # Arrange
    (tmp_path / "course.md").write_text("---\ncontent_type: COURSE\ntitle: X\n---\n")
    widgets_dir = tmp_path / ".claude" / "fls-content" / "widgets"
    widgets_dir.mkdir(parents=True)
    (widgets_dir / "c-foo.md").write_text("# `c-foo`\n\n**Allowed attributes:** none\n")

    # Act
    found = get_all_files(tmp_path)

    # Assert
    assert found == [tmp_path / "course.md"]
