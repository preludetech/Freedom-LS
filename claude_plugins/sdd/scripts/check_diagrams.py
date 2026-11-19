#!/usr/bin/env python3
"""Check that each diagram under `docs/diagrams/` shows the step headings of its command.

With no arguments every diagram in `DIAGRAM_SOURCES` is checked, and a `*.drawio.svg` that is
neither listed nor exempt, or a listed diagram with no file, is reported. `--diagram <svg>
--source <md>...` checks one diagram against the given files.

A diagram passes when every `Step N` heading outside a fenced block has a label that starts with
that heading, and no label starts with a step number that no source file has.

Stdlib only. Exits 0 with no misses, 1 with the misses printed, 64 on a usage error.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import NoReturn

PLUGIN = Path(__file__).resolve().parents[1]
DIAGRAMS_DIR = PLUGIN / "docs" / "diagrams"
CONFIG_FILES = (".claude/sdd/config.md", ".claude/sdd/config.local.md")
EXIT_MISSES = 1
EXIT_USAGE = 64

# Each diagram and the plugin files whose step headings it must show. A command split across
# files lists all of them.
DIAGRAM_SOURCES: dict[str, tuple[str, ...]] = {
    "document": ("commands/document.md",),
    "rebase": (
        "commands/protected/pre_step_rebase.md",
        "resources/upstream_change_review.md",
    ),
    "start": ("commands/start.md",),
    "spec_from_idea": ("commands/spec_from_idea.md",),
    "plan_from_spec": ("commands/plan_from_spec.md",),
    "implement_plan": ("commands/implement_plan.md",),
    "do_qa": ("commands/do_qa.md",),
    "qa_fix": ("commands/qa_fix.md",),
    "finish_worktree": ("commands/finish_worktree.md",),
}
# Sources named by the project's config instead of living in this plugin:
# diagram -> (section, key) pairs in .claude/sdd/config.md.
CONFIG_SOURCES: dict[str, tuple[tuple[str, str], ...]] = {
    "rebase": (("Rebase Hooks", "Rebase command"),),
}
EXEMPT = frozenset({"overview"})

FENCED_BLOCK = re.compile(r"^(```|~~~).*?^\1", re.MULTILINE | re.DOTALL)
STEP_HEADING = re.compile(r"^#{1,3}\s+(Step \d+(?:\.\d+)?\b.*?)\s*$", re.MULTILINE)
STEP_LABEL = re.compile(r"^Step (\d+(?:\.\d+)?)(?![\d.])")
STEP_NUMBER = re.compile(r"^Step (\d+(?:\.\d+)?)")
TAG = re.compile(r"<[^>]*>")
BREAK = re.compile(r"<br\s*/?>|</(?:div|p|li)>", re.IGNORECASE)
SECTION = re.compile(r"^##\s+(.*?)\s*$")
CONFIG_BULLET = re.compile(r"^\s*-\s+([^:/]+):\s*(.*?)\s*$")


class UsageParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        sys.stderr.write(f"{self.prog}: error: {message}\n")
        sys.exit(EXIT_USAGE)


def step_headings(markdown: str) -> list[str]:
    """Step headings outside fenced blocks: a template inside a fence is not a step."""
    return STEP_HEADING.findall(FENCED_BLOCK.sub("", markdown))


def clean_label(raw: str) -> str:
    """Strip markup from a draw.io label, unescape entities and collapse whitespace."""
    text = TAG.sub(" ", BREAK.sub(" ", raw))
    return " ".join(html.unescape(text).replace("\xa0", " ").split())


def labels(svg: Path) -> list[str]:
    """Every shape label in the draw.io XML embedded in the SVG's `content` attribute,
    with markup stripped, entities unescaped and whitespace collapsed."""
    # The files are this repository's own exports, not input from outside it.
    content = ET.parse(svg).getroot().get("content", "")  # noqa: S314  # nosec B314
    if not content:
        return []
    found: list[str] = []
    for cell in ET.fromstring(content).iter():  # noqa: S314  # nosec B314
        # A shape with a link or other properties keeps its label on a wrapping element.
        raw = (
            cell.get("label", "")
            if cell.tag in ("UserObject", "object")
            else cell.get("value", "")
        )
        label = clean_label(raw)
        if label:
            found.append(label)
    return found


def shows(label: str, heading: str) -> bool:
    # "Step 1" must not be satisfied by "Step 10: ...", nor "Step 0" by "Step 0.5: ...".
    return re.match(re.escape(heading) + r"(?![\d.])", label) is not None


def misses(svg: Path, sources: list[Path]) -> list[str]:
    headings = [
        h for source in sources for h in step_headings(source.read_text("utf-8"))
    ]
    found = labels(svg)
    out = [
        f'{svg.name}: no label for "{heading}"'
        for heading in headings
        if not any(shows(label, heading) for label in found)
    ]
    numbers = {m.group(1) for h in headings if (m := STEP_NUMBER.match(h))}
    out += [
        f'{svg.name}: label "{label}" names a step no file has'
        for label in found
        if (m := STEP_LABEL.match(label)) and m.group(1) not in numbers
    ]
    return out


def config_value(project_root: Path, section: str, key: str) -> str | None:
    """The value of `- key: value` under `## section`; `config.local.md` wins."""
    for name in reversed(CONFIG_FILES):
        config = project_root / name
        if not config.is_file():
            continue
        current = ""
        for line in config.read_text(encoding="utf-8").splitlines():
            if heading := SECTION.match(line):
                current = heading.group(1)
            elif (
                current == section
                and (bullet := CONFIG_BULLET.match(line))
                and bullet.group(1) == key
                and bullet.group(2)
            ):
                return bullet.group(2).split()[0]
    return None


def config_sources(project_root: Path, name: str) -> list[Path]:
    """Config-named sources of a diagram. A blank or missing key, or a path that leaves the
    project root, is dropped."""
    root = project_root.resolve()
    found: list[Path] = []
    for section, key in CONFIG_SOURCES.get(name, ()):
        value = config_value(project_root, section, key)
        if value is None:
            continue
        path = (root / value).resolve()
        if path.is_relative_to(root) and path.is_file():
            found.append(path)
    return found


def check_all(project_root: Path) -> list[str]:
    out: list[str] = []
    present = {
        path.name.removesuffix(".drawio.svg")
        for path in DIAGRAMS_DIR.glob("*.drawio.svg")
    }
    out += [
        f"{name}.drawio.svg: not in DIAGRAM_SOURCES and not exempt"
        for name in sorted(present - set(DIAGRAM_SOURCES) - EXEMPT)
    ]
    for name, relative in DIAGRAM_SOURCES.items():
        svg = DIAGRAMS_DIR / f"{name}.drawio.svg"
        if not svg.is_file():
            out.append(f"{svg.name}: listed in DIAGRAM_SOURCES but the file is missing")
            continue
        sources = [PLUGIN / path for path in relative] + config_sources(
            project_root, name
        )
        out += misses(svg, sources)
    return out


def main(argv: list[str]) -> int:
    parser = UsageParser(description=__doc__.splitlines()[0])
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--diagram", type=Path)
    parser.add_argument("--source", type=Path, nargs="+")
    args = parser.parse_args(argv)
    if (args.diagram is None) != (args.source is None):
        parser.error("--diagram and --source go together")
    if args.diagram is not None:
        problems = misses(args.diagram, args.source)
    else:
        problems = check_all(args.project_root)
    for problem in problems:
        sys.stdout.write(f"{problem}\n")
    return EXIT_MISSES if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
