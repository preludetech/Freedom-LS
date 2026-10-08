"""Browser test for the design screenshot script: it renders artboards from a static page."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.dev_tooling

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "claude_plugins" / "sdd" / "scripts" / "design_screenshots.py"

PAGE = """<!doctype html>
<html><body>
<div data-artboard="s-1/a" style="width:300px;height:120px;background:#eef">A</div>
<div data-artboard="s-1/b" style="width:200px;height:80px;background:#fee">B</div>
</body></html>
"""


def snapshot(directory: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(directory)): path.read_bytes()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


@pytest.mark.playwright
def test_artboards_written_as_pngs_and_stale_ones_removed(tmp_path: Path) -> None:
    # Arrange
    spec_dir = tmp_path / "2026-09-29 my spec"
    source = spec_dir / "design_source"
    source.mkdir(parents=True)
    (source / "index.html").write_text(PAGE)
    (spec_dir / "design.md").write_text(
        "# Design\n\n- Entry file: `index.html`, a static page\n"
    )
    out = spec_dir / "design_screenshots"
    out.mkdir()
    (out / "old__x.png").write_bytes(b"stale")
    source_before = snapshot(source)

    # Act
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(SCRIPT), str(spec_dir)],
        capture_output=True,
        text=True,
        check=False,
    )

    # Assert
    assert result.returncode == 0, result.stderr
    assert sorted(path.name for path in out.iterdir()) == ["s-1__a.png", "s-1__b.png"]
    assert snapshot(source) == source_before


def png_width(path: Path) -> int:
    return int.from_bytes(path.read_bytes()[16:20], "big")


def make_spec_dir_with_entry(tmp_path: Path, html: str) -> Path:
    spec_dir = tmp_path / "2026-09-29 my spec"
    source = spec_dir / "design_source"
    source.mkdir(parents=True)
    (source / "index.html").write_text(html)
    (spec_dir / "design.md").write_text(
        "# Design\n\n- Entry file: `index.html`, a page\n"
    )
    return spec_dir


def run_script(spec_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, str(SCRIPT), str(spec_dir)],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.playwright
def test_canvas_page_that_renders_no_artboards_exits_1(tmp_path: Path) -> None:
    # Arrange
    spec_dir = make_spec_dir_with_entry(
        tmp_path,
        '<!doctype html><html><body><div id="root"></div>'
        '<script type="text/babel" src="design-canvas.jsx"></script>'
        "</body></html>",
    )
    (spec_dir / "design_source" / "design-canvas.jsx").write_text("// original")

    # Act
    result = run_script(spec_dir)

    # Assert
    assert result.returncode == 1
    assert "no artboards rendered" in result.stderr


@pytest.mark.playwright
def test_page_without_artboards_gets_two_whole_page_screenshots(
    tmp_path: Path,
) -> None:
    # Arrange
    spec_dir = make_spec_dir_with_entry(
        tmp_path, "<!doctype html><html><body><h1>Plain page</h1></body></html>"
    )

    # Act
    result = run_script(spec_dir)

    # Assert
    assert result.returncode == 0, result.stderr
    out = spec_dir / "design_screenshots"
    assert png_width(out / "index__1280.png") == 1280
    assert png_width(out / "index__375.png") == 375
