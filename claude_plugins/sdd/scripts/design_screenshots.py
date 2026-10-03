"""Screenshot every screen of a registered design.

Usage: design_screenshots.py <spec-dir>

Renders every HTML page at the top level of <spec-dir>/design_source/, the entry file named on
the "Entry file" line of <spec-dir>/design.md first, from a copy served over local HTTP, so the
source directory is never written to. Writes one PNG per screen to <spec-dir>/design_screenshots/.

Claude Design draws screens in two shapes, and a page is read for each in turn:

1. Artboards: `[data-artboard]` elements, which a design-canvas.jsx project draws. Named
   `<section-id>__<artboard-id>.png`, the ids the canvas gives them.
2. Frames: elements whose inline style sets a width and height in px of at least 320 by 480 and
   hides overflow, and that sit inside no other such frame. That is how a `.dc.html` document draws
   its screens: a fixed box per screen in document flow. Named `<page>__<screen>.png`, from the
   page's file name and the screen's label (its nearest `data-screen-label` ancestor, else the text
   just before it), both slugified.
3. The whole page, when it draws neither: a component at its `$preview` size, else the page at 1280
   and 375 wide. Named `<page>__<width>.png`.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
import threading
import unicodedata
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TypedDict
from urllib.parse import quote

from playwright.sync_api import Page, sync_playwright

# Replaces the design's own design-canvas.jsx in the served copy. Claude Design's canvas pans and
# zooms, which leaves artboards scaled and offscreen; this one lays them out at 1:1.
STAND_IN = Path(__file__).resolve().parents[1] / "resources" / "design_canvas_flat.jsx"

# Wide enough that a 1440 desktop frame and the page padding around it fit without scrolling.
VIEWPORT = {"width": 1600, "height": 1000}

# A page that draws no screens is captured whole at these widths.
FALLBACK_WIDTHS = (1280, 375)

ENTRY_FILE_LINE = re.compile(r"^\s*-\s*Entry file:.*?`([^`]+)`", re.MULTILINE)

# The props block of a .dc.html component. Its `$preview` is the size the designer drew it at.
DATA_PROPS = re.compile(r'<script[^>]*\bdata-dc-script\b[^>]*\bdata-props="([^"]*)"')

# Resolves once the element count has held steady for several ticks, because both a design canvas
# and a .dc.html document mount their screens over several React renders and sibling fetches.
SETTLED_JS = """
() => {
  const count = document.querySelectorAll('*').length;
  const state = window.__settle || (window.__settle = {last: -1, stable: 0});
  state.stable = count === state.last ? state.stable + 1 : 0;
  state.last = count;
  return state.stable >= 5;
}
"""

# Finds the frames of a .dc.html document, tags each with its index for the locator, and returns
# its label and size.
FRAMES_JS = """
() => {
  const MIN_WIDTH = 320, MIN_HEIGHT = 480;
  const px = (value) => {
    const match = (value || '').match(/^(\\d+(?:\\.\\d+)?)px$/);
    return match ? parseFloat(match[1]) : null;
  };
  const isFrame = (el) => {
    const width = px(el.style.width), height = px(el.style.height);
    const hidesOverflow = ['overflow', 'overflowX', 'overflowY'].some((p) => el.style[p] === 'hidden');
    return width !== null && height !== null && width >= MIN_WIDTH && height >= MIN_HEIGHT && hidesOverflow;
  };
  const candidates = [...document.body.querySelectorAll('*')].filter(isFrame);
  const frames = candidates.filter((el) => !candidates.some((other) => other !== el && other.contains(el)));
  const precedingText = (el) => {
    for (let node = el; node && node !== document.body; node = node.parentElement) {
      for (let sibling = node.previousElementSibling; sibling; sibling = sibling.previousElementSibling) {
        const text = (sibling.innerText || '').replace(/\\s+/g, ' ').trim();
        if (text) return text;
      }
    }
    return '';
  };
  return frames.map((el, index) => {
    el.setAttribute('data-design-screenshot', String(index));
    const labelled = el.closest('[data-screen-label]');
    const label = (labelled && labelled.getAttribute('data-screen-label'))
      || el.getAttribute('data-label') || el.getAttribute('aria-label') || precedingText(el);
    return {index, label, width: px(el.style.width), height: px(el.style.height)};
  });
}
"""

# Chains a component's `height:100%` through to the viewport, the way its preview pane does.
PREVIEW_CSS = "html,body,#dc-root,#dc-root>.sc-host{height:100%;margin:0}"


class Frame(TypedDict):
    index: int
    label: str
    width: float
    height: float


class Preview(TypedDict):
    width: int
    height: int


class DesignScreenshotError(Exception):
    pass


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


def read_entry_file(spec_dir: Path) -> str:
    design_md = spec_dir / "design.md"
    if not design_md.is_file():
        raise DesignScreenshotError(f"no design.md in {spec_dir}")
    match = ENTRY_FILE_LINE.search(design_md.read_text())
    if match is None:
        raise DesignScreenshotError(f"no 'Entry file' line in {design_md}")
    return match.group(1)


def list_pages(source: Path, entry: str) -> list[str]:
    others = sorted(
        path.name
        for path in source.iterdir()
        if path.is_file() and path.suffix == ".html" and path.name != entry
    )
    return [entry, *others]


def uses_design_canvas(page_html: str) -> bool:
    return "design-canvas.jsx" in page_html


def read_preview(page_html: str) -> Preview | None:
    match = DATA_PROPS.search(page_html)
    if match is None:
        return None
    try:
        props = json.loads(html.unescape(match.group(1)))
    except json.JSONDecodeError:
        return None
    preview = props.get("$preview") if isinstance(props, dict) else None
    if not isinstance(preview, dict):
        return None
    width, height = preview.get("width"), preview.get("height")
    if not isinstance(width, int) or not isinstance(height, int):
        return None
    return {"width": width, "height": height}


def slugify(text: str, fallback: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")[:60].strip("-")
    return slug or fallback


def page_id(name: str) -> str:
    stem = Path(name).stem
    if stem.endswith(".dc"):
        stem = stem[: -len(".dc")]
    return slugify(stem, "page")


def unique_path(out: Path, name: str, taken: set[Path]) -> Path:
    path = out / f"{name}.png"
    counter = 2
    while path in taken:
        path = out / f"{name}-{counter}.png"
        counter += 1
    taken.add(path)
    return path


def prepare_copy(source: Path, dest: Path, is_canvas: bool) -> None:
    shutil.copytree(source, dest)
    if is_canvas:
        shutil.copyfile(STAND_IN, dest / "design-canvas.jsx")


def serve(directory: Path) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(QuietHandler, directory=str(directory))
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def load(page: Page, url: str) -> None:
    response = page.goto(url, wait_until="networkidle")
    if response is None or not response.ok:
        status = "no response" if response is None else response.status
        raise DesignScreenshotError(f"could not load {url}: {status}")
    page.wait_for_function(SETTLED_JS, polling=100, timeout=30_000)
    page.evaluate("() => document.fonts.ready")


def screenshot_artboards(page: Page, out: Path, taken: set[Path]) -> list[Path]:
    written: list[Path] = []
    artboards = page.locator("[data-artboard]")
    for index in range(artboards.count()):
        artboard = artboards.nth(index)
        artboard_id = artboard.get_attribute("data-artboard") or ""
        path = unique_path(out, artboard_id.replace("/", "__"), taken)
        artboard.screenshot(path=path, animations="disabled", scale="css")
        written.append(path)
    return written


def screenshot_frames(
    page: Page, out: Path, name: str, frames: list[Frame], taken: set[Path]
) -> list[Path]:
    written: list[Path] = []
    for frame in frames:
        index = frame["index"]
        screen = slugify(frame["label"], f"screen-{index + 1}")
        path = unique_path(out, f"{page_id(name)}__{screen}", taken)
        page.locator(f'[data-design-screenshot="{index}"]').screenshot(
            path=path, animations="disabled", scale="css"
        )
        written.append(path)
    return written


def screenshot_whole_page(
    page: Page, out: Path, name: str, preview: Preview | None, taken: set[Path]
) -> list[Path]:
    written: list[Path] = []
    if preview is not None:
        page.set_viewport_size({"width": preview["width"], "height": preview["height"]})
        page.add_style_tag(content=PREVIEW_CSS)
        path = unique_path(out, f"{page_id(name)}__{preview['width']}", taken)
        page.screenshot(path=path, animations="disabled", scale="css")
        return [path]
    for width in FALLBACK_WIDTHS:
        page.set_viewport_size({"width": width, "height": 900})
        path = unique_path(out, f"{page_id(name)}__{width}", taken)
        page.screenshot(path=path, full_page=True, animations="disabled", scale="css")
        written.append(path)
    return written


def capture_page(
    page: Page, base_url: str, source: Path, name: str, out: Path, taken: set[Path]
) -> list[Path]:
    page_html = (source / name).read_text()
    page.set_viewport_size(VIEWPORT)
    load(page, f"{base_url}/{quote(name)}")

    if page.locator("[data-artboard]").count() > 0:
        written = screenshot_artboards(page, out, taken)
        sys.stderr.write(f"{name}: {len(written)} artboards\n")
        return written
    if uses_design_canvas(page_html):
        raise DesignScreenshotError(f"{name}: no artboards rendered")

    frames: list[Frame] = page.evaluate(FRAMES_JS)
    if frames:
        written = screenshot_frames(page, out, name, frames, taken)
        sys.stderr.write(f"{name}: {len(written)} screens\n")
        return written

    written = screenshot_whole_page(page, out, name, read_preview(page_html), taken)
    sys.stderr.write(f"{name}: no screens drawn, captured whole\n")
    return written


def capture(spec_dir: Path) -> list[Path]:
    entry = read_entry_file(spec_dir)
    source = spec_dir / "design_source"
    if not (source / entry).is_file():
        raise DesignScreenshotError(f"entry file not found: {source / entry}")
    pages = list_pages(source, entry)
    is_canvas = any(uses_design_canvas((source / name).read_text()) for name in pages)

    out = spec_dir / "design_screenshots"
    out.mkdir(exist_ok=True)
    for stale in out.glob("*.png"):
        stale.unlink()

    written: list[Path] = []
    taken: set[Path] = set()
    with TemporaryDirectory() as tmp:
        served = Path(tmp) / "site"
        prepare_copy(source, served, is_canvas)
        server = serve(served)
        try:
            base_url = f"http://127.0.0.1:{server.server_port}"
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                try:
                    context = browser.new_context(
                        viewport=VIEWPORT, device_scale_factor=1
                    )
                    page = context.new_page()
                    for name in pages:
                        written.extend(
                            capture_page(page, base_url, source, name, out, taken)
                        )
                finally:
                    browser.close()
        finally:
            server.shutdown()
    return written


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec_dir", type=Path)
    args = parser.parse_args(argv)
    try:
        written = capture(args.spec_dir)
    except DesignScreenshotError as error:
        sys.stderr.write(f"design_screenshots: {error}\n")
        return 1
    for path in written:
        sys.stdout.write(f"{path}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
