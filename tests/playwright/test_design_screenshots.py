"""Browser test for the design screenshot script: it renders artboards from a static page."""

from __future__ import annotations

import base64
import json
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


SUPPORT_JS = """document.addEventListener('DOMContentLoaded', () => {
  const dc = document.querySelector('x-dc');
  const root = document.createElement('div'); root.id = 'dc-root';
  const host = document.createElement('div'); host.className = 'sc-host';
  host.innerHTML = dc.innerHTML; root.appendChild(host); dc.replaceWith(root);
});
"""

BLOB_ID = "0123456789abcdef0123456789abcdef"

ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/"
    "iZk9HQAAAABJRU5ErkJggg=="
)

ARTBOARD = (
    "<!doctype html><html><body><x-dc><p>{text}</p>{extra}</x-dc>"
    '<script src="{support}"></script></body></html>'
)


def png_height(path: Path) -> int:
    return int.from_bytes(path.read_bytes()[20:24], "big")


def make_canvas_spec_dir(tmp_path: Path) -> Path:
    spec_dir = tmp_path / "2026-09-29 my spec"
    project = spec_dir / "design_source" / "project"
    (project / "flows").mkdir(parents=True)
    (project / "support.js").write_text(SUPPORT_JS)
    (project / "Fixed.dc.html").write_text(
        ARTBOARD.format(text="Fixed board", extra="", support="./support.js")
    )
    # A nested artboard loads `./support.js` from its own folder, as the canvas writes it.
    (project / "flows" / "Fill.dc.html").write_text(
        ARTBOARD.format(
            text="Fill board",
            extra=f'<img src="/_blob/{BLOB_ID}">',
            support="./support.js",
        )
    )
    (spec_dir / "design_source" / "_blob").mkdir()
    (spec_dir / "design_source" / "_blob" / f"{BLOB_ID}.png").write_bytes(ONE_PIXEL_PNG)
    (project / "canvas.json").write_text(
        json.dumps(
            {
                "boards": {
                    "Fixed.dc.html": {"w": 300, "h": 200},
                    "flows/Fill.dc.html": {"w": 400, "h": 300, "expand": "fill"},
                },
                "order": ["Fixed.dc.html", "flows/Fill.dc.html"],
            }
        )
    )
    return spec_dir


@pytest.mark.playwright
def test_canvas_json_renders_one_png_per_artboard_at_its_drawn_size(
    tmp_path: Path,
) -> None:
    # Arrange
    spec_dir = make_canvas_spec_dir(tmp_path)

    # Act
    result = run_script(spec_dir)

    # Assert
    assert result.returncode == 0, result.stderr
    out = spec_dir / "design_screenshots"
    assert sorted(path.name for path in out.iterdir()) == [
        "Fixed.png",
        "flows__Fill.png",
    ]
    assert (png_width(out / "Fixed.png"), png_height(out / "Fixed.png")) == (300, 200)
    assert png_width(out / "flows__Fill.png") == 400


@pytest.mark.playwright
def test_blob_url_is_served_from_the_saved_blob_file(tmp_path: Path) -> None:
    # Arrange
    spec_dir = make_canvas_spec_dir(tmp_path)

    # Act
    result = run_script(spec_dir)

    # Assert
    assert result.returncode == 0, result.stderr
    assert "missing blob" not in result.stderr


@pytest.mark.playwright
def test_missing_blob_is_reported_once_and_screenshots_still_written(
    tmp_path: Path,
) -> None:
    # Arrange
    spec_dir = make_canvas_spec_dir(tmp_path)
    (spec_dir / "design_source" / "_blob" / f"{BLOB_ID}.png").unlink()

    # Act
    result = run_script(spec_dir)

    # Assert
    assert result.returncode == 0, result.stderr
    missing = [line for line in result.stderr.splitlines() if "missing blob" in line]
    assert len(missing) == 1
    assert BLOB_ID in missing[0]
    out = spec_dir / "design_screenshots"
    assert sorted(path.name for path in out.iterdir()) == [
        "Fixed.png",
        "flows__Fill.png",
    ]


@pytest.mark.playwright
def test_blank_artboard_exits_1_naming_it_and_the_others_are_still_written(
    tmp_path: Path,
) -> None:
    # Arrange
    spec_dir = make_canvas_spec_dir(tmp_path)
    project = spec_dir / "design_source" / "project"
    (project / "Empty.dc.html").write_text(
        '<!doctype html><html><body><x-dc><dc-import name="Other"></dc-import></x-dc>'
        "</body></html>"
    )
    canvas = json.loads((project / "canvas.json").read_text())
    canvas["boards"]["Empty.dc.html"] = {"w": 300, "h": 200}
    canvas["order"] = ["Empty.dc.html", *canvas["order"]]
    (project / "canvas.json").write_text(json.dumps(canvas))

    # Act
    result = run_script(spec_dir)

    # Assert
    assert result.returncode == 1
    assert "Empty.dc.html: rendered blank" in result.stderr
    out = spec_dir / "design_screenshots"
    assert sorted(path.name for path in out.iterdir()) == [
        "Fixed.png",
        "flows__Fill.png",
    ]


@pytest.mark.playwright
def test_artboard_drawn_only_with_css_is_not_blank(tmp_path: Path) -> None:
    # Arrange
    spec_dir = make_canvas_spec_dir(tmp_path)
    project = spec_dir / "design_source" / "project"
    (project / "Swatch.dc.html").write_text(
        "<!doctype html><html><body>"
        '<div style="width:100px;height:100px;background:#c33"></div></body></html>'
    )
    canvas = json.loads((project / "canvas.json").read_text())
    canvas["boards"]["Swatch.dc.html"] = {"w": 300, "h": 200}
    (project / "canvas.json").write_text(json.dumps(canvas))

    # Act
    result = run_script(spec_dir)

    # Assert
    assert result.returncode == 0, result.stderr
    assert (spec_dir / "design_screenshots" / "Swatch.png").is_file()
    assert "Swatch.dc.html: not in order, rendered last" in result.stderr
