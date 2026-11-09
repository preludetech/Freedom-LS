"""Screenshot every screen of a registered design.

Usage: design_screenshots.py <spec-dir>

A Design Artifact's <spec-dir>/design_source/project/canvas.json names the artboards and their
sizes, and each is rendered from <spec-dir>/design_source/project/<path>: one PNG per artboard, in
the canvas's `order` and then any board `order` omits, named `<path without .dc.html, with / as
__>.png`. A fixed artboard is captured at its drawn width and height; an `expand: "fill"` artboard
is captured full-page at its drawn width. Every artboard loads `./support.js` from its own folder,
so `project/support.js` is served at that name in every folder. An artboard that renders blank gets
no PNG and is named on stderr; the remaining artboards are still captured and the exit status is 1.
design.md is not read.

Without a canvas.json, the older shapes below apply. Every HTML page at the top level of
<spec-dir>/design_source/ is rendered, the entry file named on the "Entry file" line of
<spec-dir>/design.md first. Pages are served over local HTTP from a copy, so the source directory
is never written to. One PNG per screen goes to <spec-dir>/design_screenshots/.

Claude Design draws screens in three shapes, and a page is read for each in turn:

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
from collections.abc import Iterator
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TypedDict
from urllib.parse import quote, urlsplit

from playwright.sync_api import Page, Response, sync_playwright

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

# An unmounted <x-dc> template or a <dc-import>-only artboard draws nothing. A board drawn only
# with CSS (swatches, wireframe boxes) has no text or image but does paint a background.
BLANK_JS = """
() => {
  if (document.body.innerText.trim()) return false;
  if (document.body.querySelector('img, svg, canvas, video, picture')) return false;
  const painted = [...document.body.querySelectorAll('*')].some((el) => {
    const style = getComputedStyle(el);
    return style.backgroundImage !== 'none'
      || (style.backgroundColor !== 'rgba(0, 0, 0, 0)' && style.backgroundColor !== 'transparent');
  });
  return !painted;
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

# A saved image asset is requested at this root-absolute URL; its id is 32 hex characters.
BLOB_URL = re.compile(r"^/_blob/([0-9a-f]{32})$")

# Every artboard loads `./support.js` relative to its own folder; one copy serves them all.
SUPPORT_JS_URL = re.compile(r"^/project/(?:.+/)?support\.js$")

CANVAS_JSON = Path("project") / "canvas.json"

# Chromium's viewport limit; also stops a corrupt size from exhausting memory.
MAX_ARTBOARD_SIDE = 10_000

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


class Artboard(TypedDict):
    path: str
    width: int
    height: int
    fill: bool


class DesignScreenshotError(Exception):
    pass


class BlankArtboardsError(DesignScreenshotError):
    """Some artboards rendered blank; the others' PNGs were still written."""

    def __init__(self, blank: list[str], written: list[Path]) -> None:
        super().__init__(f"{len(blank)} artboard(s) rendered blank: {', '.join(blank)}")
        self.written = written


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


class SourceHandler(QuietHandler):
    def translate_path(self, path: str) -> str:
        url_path = urlsplit(path).path
        if SUPPORT_JS_URL.match(url_path):
            return str(Path(self.directory) / "project" / "support.js")
        match = BLOB_URL.match(url_path)
        if match:
            blobs = Path(self.directory) / "_blob"
            saved = min(blobs.glob(f"{match.group(1)}.*"), default=None)
            if saved is not None:
                return str(saved)
        return super().translate_path(path)


def read_entry_file(spec_dir: Path) -> str:
    design_md = spec_dir / "design.md"
    if not design_md.is_file():
        raise DesignScreenshotError(f"no design.md in {spec_dir}")
    match = ENTRY_FILE_LINE.search(design_md.read_text())
    if match is None:
        raise DesignScreenshotError(f"no 'Entry file' line in {design_md}")
    return match.group(1)


def load_canvas(canvas_json: Path) -> dict[str, object]:
    try:
        canvas = json.loads(canvas_json.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise DesignScreenshotError(f"could not read {canvas_json}: {error}") from error
    if not isinstance(canvas, dict):
        raise DesignScreenshotError(f"{canvas_json}: not a JSON object")
    return canvas


def parse_artboard(path: str, board: object, canvas_json: Path) -> Artboard:
    if not isinstance(board, dict):
        raise DesignScreenshotError(f"{canvas_json}: board {path!r} is not an object")
    try:
        width, height = int(board["w"]), int(board["h"])
    except (KeyError, TypeError, ValueError) as error:
        raise DesignScreenshotError(
            f"{canvas_json}: board {path!r} has no usable w and h"
        ) from error
    for side in (width, height):
        if not 0 < side <= MAX_ARTBOARD_SIDE:
            raise DesignScreenshotError(
                f"{canvas_json}: board {path!r} is {width}x{height}"
            )
    return {
        "path": path,
        "width": width,
        "height": height,
        "fill": board.get("expand") == "fill",
    }


def board_paths(
    canvas: dict[str, object], boards: dict[str, object], canvas_json: Path
) -> list[str]:
    order = canvas.get("order")
    if not isinstance(order, list):
        order = []
    paths: list[str] = []
    for path in order:
        if not isinstance(path, str) or path not in boards:
            raise DesignScreenshotError(
                f"{canvas_json}: order names {path!r}, not a board"
            )
        if path not in paths:
            paths.append(path)
    for path in boards:
        if path not in paths:
            sys.stderr.write(f"{path}: not in order, rendered last\n")
            paths.append(path)
    return paths


def read_canvas(source: Path) -> list[Artboard]:
    canvas_json = source / CANVAS_JSON
    canvas = load_canvas(canvas_json)
    boards = canvas.get("boards")
    if not isinstance(boards, dict):
        raise DesignScreenshotError(f"{canvas_json}: no boards")
    project = (source / "project").resolve()
    artboards: list[Artboard] = []
    stems: dict[str, str] = {}
    for path in board_paths(canvas, boards, canvas_json):
        file = (project / path).resolve()
        if not file.is_relative_to(project):
            raise DesignScreenshotError(
                f"{canvas_json}: board {path!r} points outside project/"
            )
        if not file.is_file():
            raise DesignScreenshotError(
                f"artboard file not found: {source / 'project' / path}"
            )
        stem = artboard_stem(path)
        if stem in stems:
            raise DesignScreenshotError(
                f"{canvas_json}: boards {stems[stem]!r} and {path!r} "
                f"both screenshot as {stem}.png"
            )
        stems[stem] = path
        artboards.append(parse_artboard(path, boards[path], canvas_json))
    return artboards


def artboard_stem(path: str) -> str:
    return path.removesuffix(".dc.html").replace("/", "__")


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
        ("127.0.0.1", 0), partial(SourceHandler, directory=str(directory))
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


def missing_blob_id(response: Response) -> str | None:
    if response.status != 404:
        return None
    match = BLOB_URL.match(urlsplit(response.url).path)
    return match.group(1) if match else None


def is_blank(page: Page) -> bool:
    return bool(page.evaluate(BLANK_JS))


def screenshot_page(page: Page, path: Path, full_page: bool = False) -> None:
    page.screenshot(path=path, full_page=full_page, animations="disabled", scale="css")


def screenshot_canvas_artboard(
    page: Page, base_url: str, artboard: Artboard, out: Path
) -> Path | None:
    """Write the artboard's PNG and return its path, or None when the artboard rendered blank."""
    # Sized before loading so an expand: "fill" artboard lays out at its drawn width.
    page.set_viewport_size({"width": artboard["width"], "height": artboard["height"]})
    missing: list[str] = []

    def note_missing(response: Response) -> None:
        blob_id = missing_blob_id(response)
        # A page can request the same blob more than once; report it once.
        if blob_id is not None and blob_id not in missing:
            missing.append(blob_id)

    # The listener stays on through the screenshot: a full-page capture can fetch lazy images.
    page.on("response", note_missing)
    try:
        load(page, f"{base_url}/project/{quote(artboard['path'])}")
        if is_blank(page):
            sys.stderr.write(f"{artboard['path']}: rendered blank\n")
            return None
        page.add_style_tag(content=PREVIEW_CSS)
        path = out / f"{artboard_stem(artboard['path'])}.png"
        screenshot_page(page, path, full_page=artboard["fill"])
    finally:
        page.remove_listener("response", note_missing)
    for blob_id in missing:
        sys.stderr.write(f"{artboard['path']}: missing blob {blob_id}\n")
    return path


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
        screenshot_page(page, path)
        return [path]
    for width in FALLBACK_WIDTHS:
        page.set_viewport_size({"width": width, "height": 900})
        path = unique_path(out, f"{page_id(name)}__{width}", taken)
        screenshot_page(page, path, full_page=True)
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


@contextmanager
def served_page(
    source: Path, out: Path, needs_stand_in: bool
) -> Iterator[tuple[Page, str]]:
    out.mkdir(exist_ok=True)
    for stale in out.glob("*.png"):
        stale.unlink()
    with TemporaryDirectory() as tmp:
        served = Path(tmp) / "site"
        prepare_copy(source, served, needs_stand_in)
        server = serve(served)
        try:
            base_url = f"http://127.0.0.1:{server.server_port}"
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                try:
                    context = browser.new_context(
                        viewport=VIEWPORT, device_scale_factor=1
                    )
                    yield context.new_page(), base_url
                finally:
                    browser.close()
        finally:
            server.shutdown()


def capture_canvas(source: Path, out: Path) -> list[Path]:
    # Read before anything is copied or launched, so a missing artboard file fails fast.
    artboards = read_canvas(source)
    written: list[Path] = []
    blank: list[str] = []
    with served_page(source, out, needs_stand_in=False) as (page, base_url):
        for artboard in artboards:
            path = screenshot_canvas_artboard(page, base_url, artboard, out)
            if path is None:
                blank.append(artboard["path"])
                continue
            written.append(path)
            fill = " fill" if artboard["fill"] else ""
            sys.stderr.write(
                f"{artboard['path']}: artboard {artboard['width']}x{artboard['height']}{fill}\n"
            )
    if blank:
        raise BlankArtboardsError(blank, written)
    return written


def capture(spec_dir: Path) -> list[Path]:
    source = spec_dir / "design_source"
    out = spec_dir / "design_screenshots"
    if (source / CANVAS_JSON).is_file():
        return capture_canvas(source, out)

    entry = read_entry_file(spec_dir)
    if not (source / entry).is_file():
        raise DesignScreenshotError(f"entry file not found: {source / entry}")
    pages = list_pages(source, entry)
    is_canvas = any(uses_design_canvas((source / name).read_text()) for name in pages)

    written: list[Path] = []
    taken: set[Path] = set()
    with served_page(source, out, is_canvas) as (page, base_url):
        for name in pages:
            written.extend(capture_page(page, base_url, source, name, out, taken))
    return written


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec_dir", type=Path)
    args = parser.parse_args(argv)
    try:
        written = capture(args.spec_dir)
    except BlankArtboardsError as error:
        print_written(error.written)
        sys.stderr.write(f"design_screenshots: {error}\n")
        return 1
    except DesignScreenshotError as error:
        sys.stderr.write(f"design_screenshots: {error}\n")
        return 1
    print_written(written)
    return 0


def print_written(written: list[Path]) -> None:
    for path in written:
        sys.stdout.write(f"{path}\n")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
