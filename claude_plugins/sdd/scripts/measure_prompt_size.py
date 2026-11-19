#!/usr/bin/env python3
"""Print the size of the prompt files an SDD run loads, as a markdown table.

The measured set is every markdown file under this plugin's commands, resources, agents and
skills directories (READMEs excluded), every file the project's SDD config points at, and every
file a measured plugin file names through `${CLAUDE_PLUGIN_ROOT}/`, followed until no new file
turns up. A key set in `config.local.md` replaces the same key in `config.md`. A reference that cannot be
measured (a skill name, a missing file, a path outside the project or the plugin) is listed
under "## Unmeasured" rather than dropped, so a shrinking total cannot hide a lost file.

Token counts are a rough estimate (four characters per token), good for comparing two runs of
this script and not for budgeting against a real tokenizer.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import NoReturn

PLUGIN = Path(__file__).resolve().parents[1]
MEASURED_DIRS = ("commands", "resources", "agents", "skills")
CONFIG_FILES = (".claude/sdd/config.md", ".claude/sdd/config.local.md")
PLUGIN_ROOT_REFERENCE = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([\w./-]+)")
SKILL_NAME = re.compile(r"^[\w-]+:[\w-]+$")
# "- Key: value" or a bare "- value"; a key never holds a slash, so "- http://x" stays a value.
BULLET = re.compile(r"^\s*-\s+(?:(?P<key>[^:/]+):\s+)?(?P<value>.*?)\s*$")
SECTION = re.compile(r"^##\s+(.*?)\s*$")
EXIT_USAGE = 64


class UsageParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        sys.stderr.write(f"{self.prog}: error: {message}\n")
        sys.exit(EXIT_USAGE)


def approx_tokens(text: str) -> int:
    return len(text) // 4


def is_path_shaped(value: str) -> bool:
    """A value whose first word is a file path, so `scripts/check.sh --flag` counts."""
    words = value.split()
    if not words:
        return False
    first = words[0]
    return "/" in first and "://" not in first and bool(Path(first).suffix)


def config_values(project_root: Path) -> list[str]:
    """Every bullet value in the project's SDD config.

    The local file is read last, so a key it sets replaces the same key of the same section in
    the shared file. A bullet with no key cannot be matched to another, so all of them are kept.
    """
    keyed: dict[tuple[str, str], str] = {}
    bare: list[str] = []
    for name in CONFIG_FILES:
        config = project_root / name
        if not config.is_file():
            continue
        section = ""
        for line in config.read_text(encoding="utf-8").splitlines():
            heading = SECTION.match(line)
            if heading:
                section = heading.group(1)
                continue
            match = BULLET.match(line)
            if not match or not match.group("value"):
                continue
            key = match.group("key")
            if key is None:
                bare.append(match.group("value"))
            else:
                keyed[(section, key.strip())] = match.group("value")
    return [*keyed.values(), *bare]


def resolve_inside(candidate: Path, root: Path) -> Path | None:
    """The resolved file when it exists under `root`, otherwise None."""
    resolved = candidate.resolve()
    if resolved.is_relative_to(root.resolve()) and resolved.is_file():
        return resolved
    return None


def measured_files(project_root: Path) -> tuple[list[Path], list[str]]:
    """The files an SDD run loads, and the references that could not be measured."""
    files: set[Path] = set()
    unmeasured: set[str] = set()
    for directory in MEASURED_DIRS:
        for path in (PLUGIN / directory).rglob("*.md"):
            if path.name != "README.md":
                files.add(path.resolve())
    for value in config_values(project_root):
        if SKILL_NAME.match(value):
            unmeasured.add(value)
        elif is_path_shaped(value):
            path_word = value.split()[0]
            found = resolve_inside(project_root / path_word, project_root)
            if found is None:
                unmeasured.add(path_word)
            else:
                files.add(found)
    # A referenced file joins the queue, so the files it names are measured too.
    pending = [path for path in files if path.is_relative_to(PLUGIN)]
    while pending:
        text = pending.pop().read_text(encoding="utf-8")
        for captured in PLUGIN_ROOT_REFERENCE.findall(text):
            # The pattern also swallows sentence punctuation after the path.
            reference = captured.rstrip(".")
            found = resolve_inside(PLUGIN / reference, PLUGIN)
            if found is None:
                unmeasured.add(f"${{CLAUDE_PLUGIN_ROOT}}/{reference}")
            elif found not in files:
                files.add(found)
                pending.append(found)
    return sorted(files), sorted(unmeasured)


def display_name(path: Path, project_root: Path) -> str:
    if path.is_relative_to(PLUGIN):
        return (
            f"{PLUGIN.parent.name}/{PLUGIN.name}/{path.relative_to(PLUGIN).as_posix()}"
        )
    return path.relative_to(project_root.resolve()).as_posix()


def render(project_root: Path) -> str:
    files, unmeasured = measured_files(project_root)
    rows: list[tuple[str, int, int, int]] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        rows.append(
            (
                display_name(path, project_root),
                len(text.splitlines()),
                len(text.split()),
                approx_tokens(text),
            )
        )
    rows.sort()
    lines = [
        "| File | Lines | Words | Approx tokens |",
        "| --- | ---: | ---: | ---: |",
    ]
    lines += [
        f"| {name} | {n_lines} | {words} | {tokens} |"
        for name, n_lines, words, tokens in rows
    ]
    totals = [sum(row[index] for row in rows) for index in (1, 2, 3)]
    lines.append(f"| **Total** | {totals[0]} | {totals[1]} | {totals[2]} |")
    lines += ["", "## Unmeasured", ""]
    lines += [f"- {item}" for item in unmeasured] or ["(none)"]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = UsageParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    sys.stdout.write(render(args.project_root))
    return 0


if __name__ == "__main__":
    sys.exit(main())
