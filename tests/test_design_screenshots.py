"""Tests for the design screenshot script's failure paths (no browser is started).

The script is `claude_plugins/sdd/scripts/design_screenshots.py`, run with the project's Python. The
`.sh` wrapper is not run here because its first line can download Chromium.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "claude_plugins" / "sdd" / "scripts" / "design_screenshots.py"


def run_script(spec_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, str(SCRIPT), str(spec_dir)],
        capture_output=True,
        text=True,
        check=False,
    )


def make_spec_dir(tmp_path: Path) -> Path:
    spec_dir = tmp_path / "2026-09-29 my spec"
    (spec_dir / "design_source").mkdir(parents=True)
    return spec_dir


def test_missing_design_md_exits_1_naming_design_md(tmp_path: Path) -> None:
    # Arrange
    spec_dir = make_spec_dir(tmp_path)

    # Act
    result = run_script(spec_dir)

    # Assert
    assert result.returncode == 1
    assert "design.md" in result.stderr


def test_design_md_without_entry_file_line_exits_1_naming_entry_file(
    tmp_path: Path,
) -> None:
    # Arrange
    spec_dir = make_spec_dir(tmp_path)
    (spec_dir / "design.md").write_text("# Design\n\n- Made of: things\n")

    # Act
    result = run_script(spec_dir)

    # Assert
    assert result.returncode == 1
    assert "Entry file" in result.stderr


def test_entry_file_missing_from_design_source_exits_1_naming_path(
    tmp_path: Path,
) -> None:
    # Arrange
    spec_dir = make_spec_dir(tmp_path)
    (spec_dir / "design.md").write_text(
        "# Design\n\n- Entry file: `Gone Page.html`, a canvas of screens\n"
    )

    # Act
    result = run_script(spec_dir)

    # Assert
    assert result.returncode == 1
    assert "design_source/Gone Page.html" in result.stderr
    assert not (spec_dir / "design_screenshots").exists()
