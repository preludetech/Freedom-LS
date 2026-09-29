"""Screenshot every [data-artboard] element of a registered design.

Usage: design_screenshots.py <spec-dir>

The entry file is named on the "Entry file" line of <spec-dir>/design.md. It is rendered from a
copy of <spec-dir>/design_source/ served over local HTTP, so the source directory is never
written to.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import quote

from playwright.sync_api import Page, sync_playwright

ENTRY_FILE_LINE = re.compile(r"^\s*-\s*Entry file:.*?`([^`]+)`", re.MULTILINE)

# Resolves once the artboard count is non-zero and has held steady for several ticks, because a
# design canvas mounts its artboards over several React renders.
ARTBOARDS_SETTLED_JS = """
() => {
  const count = document.querySelectorAll('[data-artboard]').length;
  const state = window.__artboardSettle || (window.__artboardSettle = {last: -1, stable: 0});
  state.stable = count === state.last ? state.stable + 1 : 0;
  state.last = count;
  return state.stable >= 5;
}
"""


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


def prepare_copy(source: Path, dest: Path, entry: str) -> None:
    shutil.copytree(source, dest)


def serve(directory: Path) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(QuietHandler, directory=str(directory))
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def wait_for_artboards(page: Page) -> int:
    page.wait_for_function(ARTBOARDS_SETTLED_JS, polling=100, timeout=30_000)
    return page.locator("[data-artboard]").count()


def capture(spec_dir: Path) -> list[Path]:
    entry = read_entry_file(spec_dir)
    source = spec_dir / "design_source"
    if not (source / entry).is_file():
        raise DesignScreenshotError(f"entry file not found: {source / entry}")

    written: list[Path] = []
    with TemporaryDirectory() as tmp:
        served = Path(tmp) / "site"
        prepare_copy(source, served, entry)
        server = serve(served)
        try:
            url = f"http://127.0.0.1:{server.server_port}/{quote(entry)}"
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                try:
                    context = browser.new_context(
                        viewport={"width": 1440, "height": 900}, device_scale_factor=1
                    )
                    page = context.new_page()
                    response = page.goto(url, wait_until="networkidle")
                    if response is None or not response.ok:
                        status = "no response" if response is None else response.status
                        raise DesignScreenshotError(f"could not load {url}: {status}")
                    if wait_for_artboards(page) == 0:
                        raise DesignScreenshotError("no artboards rendered")

                    out = spec_dir / "design_screenshots"
                    out.mkdir(exist_ok=True)
                    for stale in out.glob("*.png"):
                        stale.unlink()
                    artboards = page.locator("[data-artboard]")
                    for index in range(artboards.count()):
                        artboard = artboards.nth(index)
                        artboard_id = artboard.get_attribute("data-artboard") or ""
                        path = out / (artboard_id.replace("/", "__") + ".png")
                        artboard.screenshot(
                            path=path, animations="disabled", scale="css"
                        )
                        written.append(path)
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
