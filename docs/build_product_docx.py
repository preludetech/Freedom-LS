"""Render docs/product/ into a single .docx for evaluators and integrators.

Run with pandoc supplied by the pypandoc-binary wheel, so neither the project
dependencies nor the system need a pandoc install:

    uv run --no-project --with pypandoc-binary python docs/build_product_docx.py

The thirteen documents are concatenated in README order. Because concatenation
collides slugs (every document has a "Summary"), each heading is given an
explicit `{#stem--slug}` identifier and every cross-document link is rewritten
against it. An unresolvable link fails the build rather than shipping a dead
cross-reference.
"""

from __future__ import annotations

import re
import shutil
import struct
import sys
import zipfile
from pathlib import Path

import pypandoc

DOCS_DIR = Path(__file__).resolve().parent
PRODUCT_DIR = DOCS_DIR / "product"
OUTPUT_PATH = PRODUCT_DIR / "_build" / "Freedom-LS-Product-Documentation.docx"

TITLE = "Freedom LS — Product Documentation"

# Reading order, taken from the tables in docs/product/README.md.
DOC_ORDER = [
    "README",
    "content-editing-workflow",
    "authentication",
    "learner-experience",
    "learner-tracking",
    "educator-interface",
    "admin-interface",
    "webhooks",
    "multi-tenancy-and-isolation",
    "security-and-data-handling",
    "configuration-and-extension",
    "deployment",
    "roadmap",
]

PAGE_BREAK = '```{=openxml}\n<w:p><w:r><w:br w:type="page"/></w:r></w:p>\n```'

# Images are laid out for a Letter/A4 page with the default one-inch margins.
PX_PER_INCH = 96.0
MAX_IMAGE_WIDTH_IN = 6.0
MAX_IMAGE_HEIGHT_IN = 7.5

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")
LINK_RE = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)\s]+)\)")
LAST_UPDATED_RE = re.compile(r"^_Last updated:\s*(.+?)_\s*$")
TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
TABLE_SEPARATOR_RE = re.compile(r"^\s*\|(?:\s*:?-{2,}:?\s*\|)+\s*$")

# Pandoc derives docx column widths from the dash counts in a pipe table's
# separator row, so the compact `|---|---|` in the sources renders every column
# equal width and wraps prose cells to shreds. Widths are recomputed from cell
# content instead, measured in these units.
TABLE_WIDTH_CHARS = 72
MAX_MEASURED_CELL_CHARS = 60


class BuildError(Exception):
    """A source document could not be converted faithfully."""


def slugify(heading: str) -> str:
    """Slugify heading text the way GitHub does, so existing anchors still match."""
    text = heading.replace("`", "").strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"\s", "-", text)


def png_dimensions(path: Path) -> tuple[int, int]:
    """Read pixel width and height out of a PNG's IHDR chunk."""
    header = path.read_bytes()[:24]
    if header[:8] != b"\x89PNG\r\n\x1a\n":
        raise BuildError(f"{path} is not a PNG")
    width, height = struct.unpack(">II", header[16:24])
    return width, height


def display_width_inches(path: Path) -> float:
    """Scale an image to fit the text block by width and by height."""
    width_px, height_px = png_dimensions(path)
    width_in = width_px / PX_PER_INCH
    height_in = height_px / PX_PER_INCH
    scale = min(1.0, MAX_IMAGE_WIDTH_IN / width_in, MAX_IMAGE_HEIGHT_IN / height_in)
    return round(width_in * scale, 2)


def iter_prose_lines(lines: list[str]) -> list[tuple[int, str, bool]]:
    """Pair each line with its index and whether it sits inside a fenced code block."""
    paired: list[tuple[int, str, bool]] = []
    in_fence = False
    for index, line in enumerate(lines):
        if FENCE_RE.match(line):
            paired.append((index, line, True))
            in_fence = not in_fence
            continue
        paired.append((index, line, in_fence))
    return paired


def collect_anchors(
    sources: dict[str, list[str]],
) -> tuple[dict[tuple[str, str], str], dict[str, str], list[tuple[int, str, str]]]:
    """Map (stem, local slug) to a unique id, each stem to its H1's id, and list all headings."""
    anchors: dict[tuple[str, str], str] = {}
    doc_anchors: dict[str, str] = {}
    headings: list[tuple[int, str, str]] = []
    for stem in DOC_ORDER:
        for _, line, in_fence in iter_prose_lines(sources[stem]):
            if in_fence:
                continue
            match = HEADING_RE.match(line)
            if match is None:
                continue
            level, text = match.groups()
            slug = slugify(text)
            key = (stem, slug)
            if key in anchors:
                raise BuildError(f"{stem}.md has two headings slugging to #{slug}")
            anchors[key] = f"{stem}--{slug}"
            headings.append((len(level), text, anchors[key]))
            if len(level) == 1:
                if stem in doc_anchors:
                    raise BuildError(f"{stem}.md has more than one H1")
                doc_anchors[stem] = anchors[key]
    missing = sorted(set(sources) - set(doc_anchors))
    if missing:
        raise BuildError(f"no H1 found in: {', '.join(missing)}")
    return anchors, doc_anchors, headings


def build_contents(headings: list[tuple[int, str, str]]) -> str:
    """Write a literal contents list.

    Pandoc's `--toc` emits a Word TOC field, which renders empty until the reader
    updates fields — so the entries are written out as an ordinary linked list
    that is visible and clickable the moment the document opens.
    """
    entries = ["# Contents {#contents}", ""]
    for level, text, anchor in headings:
        if level > 2:
            continue
        indent = "" if level == 1 else "    "
        entries.append(f"{indent}- [{text}](#{anchor})")
    return "\n".join(entries)


def visible_length(cell: str) -> int:
    """Approximate a table cell's rendered width, ignoring markdown punctuation."""
    return len(re.sub(r"[`*_]", "", LINK_RE.sub(r"\1", cell)).strip())


def column_weights(rows: list[list[str]]) -> list[int]:
    """Weight each column by its content, capped so prose columns cannot starve the rest."""
    weights: list[int] = []
    for column in zip(*rows, strict=True):
        longest_word = max(
            (len(word) for cell in column for word in cell.split()), default=1
        )
        measured = max(
            min(visible_length(cell), MAX_MEASURED_CELL_CHARS) for cell in column
        )
        weights.append(max(measured, longest_word))
    return weights


def rewrite_table_widths(lines: list[str]) -> list[str]:
    """Replace each pipe table's separator row with dashes proportional to its content."""
    rewritten = list(lines)
    prose = {
        index: line for index, line, in_fence in iter_prose_lines(lines) if not in_fence
    }
    for index, line in prose.items():
        if not TABLE_SEPARATOR_RE.match(line) or index - 1 not in prose:
            continue
        body = [prose[index - 1]]
        for following in range(index + 1, len(lines)):
            if following not in prose or not TABLE_ROW_RE.match(prose[following]):
                break
            body.append(prose[following])
        rows = [
            [cell.strip() for cell in row.strip().strip("|").split("|")] for row in body
        ]
        columns = len(rows[0])
        if any(len(row) != columns for row in rows):
            continue
        weights = column_weights(rows)
        total = sum(weights)
        dashes = [
            max(3, round(TABLE_WIDTH_CHARS * weight / total)) for weight in weights
        ]
        rewritten[index] = "|" + "|".join("-" * width for width in dashes) + "|"
    return rewritten


def repo_relative(stem: str, target: str) -> str:
    """Resolve a link that points outside docs/product/ to a repo-relative path."""
    resolved = (PRODUCT_DIR / f"{stem}.md").parent.joinpath(target).resolve()
    return str(resolved.relative_to(PRODUCT_DIR.parent.parent))


def rewrite_headings(
    lines: list[str], stem: str, anchors: dict[tuple[str, str], str]
) -> list[str]:
    """Attach the explicit identifier to every heading."""
    rewritten = list(lines)
    for index, line, in_fence in iter_prose_lines(lines):
        if in_fence:
            continue
        match = HEADING_RE.match(line)
        if match is None:
            continue
        level, text = match.groups()
        rewritten[index] = f"{level} {text} {{#{anchors[(stem, slugify(text))]}}}"
    return rewritten


def rewrite_images(line: str, counter: list[int]) -> str:
    """Give every image an explicit display width so tall screenshots stay on one page."""

    def replace(match: re.Match[str]) -> str:
        alt, src = match.groups()
        image_path = PRODUCT_DIR / src
        if not image_path.is_file():
            raise BuildError(f"missing image: {src}")
        counter[0] += 1
        return f'![{alt}]({src}){{width="{display_width_inches(image_path)}in"}}'

    return IMAGE_RE.sub(replace, line)


def rewrite_links(
    line: str,
    stem: str,
    anchors: dict[tuple[str, str], str],
    doc_anchors: dict[str, str],
    counter: list[int],
) -> str:
    """Point cross-references at internal anchors; de-link anything outside the bundle."""

    def replace(match: re.Match[str]) -> str:
        text, target = match.groups()
        if target.startswith(("http://", "https://", "mailto:", "#{")):
            return match.group(0)

        if target.startswith("#"):
            key = (stem, target[1:])
            if key not in anchors:
                raise BuildError(f"{stem}.md links to unknown anchor {target}")
            counter[0] += 1
            return f"[{text}](#{anchors[key]})"

        path, _, fragment = target.partition("#")
        if not path.endswith(".md"):
            return match.group(0)

        target_stem = Path(path).stem
        if Path(path).parent != Path("."):
            # Outside docs/product/, so there is nothing in this document to link to.
            repo_path = repo_relative(stem, path)
            counter[0] += 1
            if Path(path).name in text:
                return f"`{repo_path}`"
            return f"{text} (`{repo_path}`)"

        if target_stem not in doc_anchors:
            raise BuildError(f"{stem}.md links to unknown document {path}")
        if fragment:
            key = (target_stem, fragment)
            if key not in anchors:
                raise BuildError(f"{stem}.md links to unknown anchor {target}")
            anchor = anchors[key]
        else:
            anchor = doc_anchors[target_stem]
        counter[0] += 1
        return f"[{text}](#{anchor})"

    return LINK_RE.sub(replace, line)


def load_sources() -> dict[str, list[str]]:
    """Read the documents in reading order, refusing to silently drop a new one."""
    on_disk = {path.stem for path in PRODUCT_DIR.glob("*.md")}
    unlisted = sorted(on_disk - set(DOC_ORDER))
    if unlisted:
        raise BuildError(
            f"add {', '.join(unlisted)} to DOC_ORDER at the right place in the reading order"
        )
    missing = sorted(set(DOC_ORDER) - on_disk)
    if missing:
        raise BuildError(f"listed in DOC_ORDER but not on disk: {', '.join(missing)}")
    return {
        stem: (PRODUCT_DIR / f"{stem}.md").read_text().splitlines()
        for stem in DOC_ORDER
    }


def last_updated(readme_lines: list[str]) -> str:
    for line in readme_lines:
        match = LAST_UPDATED_RE.match(line)
        if match is not None:
            return match.group(1)
    raise BuildError("README.md has no '_Last updated: ..._' line")


def build_markdown(sources: dict[str, list[str]]) -> tuple[str, int, int]:
    anchors, doc_anchors, headings = collect_anchors(sources)
    image_count = [0]
    link_count = [0]

    documents: list[str] = [build_contents(headings)]
    for stem in DOC_ORDER:
        lines = rewrite_table_widths(rewrite_headings(sources[stem], stem, anchors))
        converted: list[str] = []
        for _, line, in_fence in iter_prose_lines(lines):
            if in_fence:
                converted.append(line)
                continue
            line = rewrite_images(line, image_count)
            converted.append(
                rewrite_links(line, stem, anchors, doc_anchors, link_count)
            )
        documents.append("\n".join(converted).strip())

    return f"\n\n{PAGE_BREAK}\n\n".join(documents) + "\n", image_count[0], link_count[0]


def apply_monospace_code_style(docx_path: Path) -> None:
    """Make code render monospaced on any reader.

    Pandoc's default styles ask for Consolas, which LibreOffice has no
    substitution for and silently renders in the proportional body font — which
    collapses the alignment of the architecture diagram in deployment.md. Courier
    New is present on Windows and macOS and maps to Liberation Mono on Linux. The
    Source Code paragraph style also gets the font outright, since pandoc leaves
    it on the linked character style alone.
    """
    styles_name = "word/styles.xml"
    with zipfile.ZipFile(docx_path) as archive:
        entries = {
            info.filename: archive.read(info.filename) for info in archive.infolist()
        }
    styles = entries[styles_name].decode("utf-8")
    if "Consolas" not in styles:
        raise BuildError(f"{styles_name} no longer names the expected code font")
    styles = styles.replace("Consolas", "Courier New")
    # A w:style holds run properties after paragraph properties, per the schema.
    paragraph_properties = '<w:pPr><w:wordWrap w:val="off" /></w:pPr>'
    if styles.count(paragraph_properties) != 1:
        raise BuildError(
            f"{styles_name} no longer matches the expected Source Code style"
        )
    fonts = '<w:rPr><w:rFonts w:ascii="Courier New" w:hAnsi="Courier New" /><w:sz w:val="20" /></w:rPr>'
    entries[styles_name] = styles.replace(
        paragraph_properties, paragraph_properties + fonts
    ).encode("utf-8")

    patched = docx_path.with_suffix(".patched")
    with zipfile.ZipFile(patched, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)
    shutil.move(patched, docx_path)


def main() -> int:
    try:
        sources = load_sources()
        markdown, image_count, link_count = build_markdown(sources)
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        pypandoc.convert_text(
            markdown,
            to="docx",
            format="markdown",
            outputfile=str(OUTPUT_PATH),
            extra_args=[
                f"--columns={TABLE_WIDTH_CHARS}",
                f"--resource-path={PRODUCT_DIR}",
                f"--metadata=title:{TITLE}",
                f"--metadata=date:Last updated {last_updated(sources['README'])}",
            ],
        )
        apply_monospace_code_style(OUTPUT_PATH)
    except BuildError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    size_kb = OUTPUT_PATH.stat().st_size / 1024
    print(f"wrote {OUTPUT_PATH} ({size_kb:.0f} KB)")
    print(
        f"{len(DOC_ORDER)} documents, {image_count} images, {link_count} links rewritten"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
