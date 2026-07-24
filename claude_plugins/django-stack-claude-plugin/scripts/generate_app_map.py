# ruff: noqa: T201
#!/usr/bin/env python3
"""Generate a mermaid dependency diagram of the project's Django apps.

Walks each Django app (directory containing `apps.py`), collects cross-app
imports via the stdlib `ast` module, and writes the diagram to
`docs/app_structure.md`. If the output file already exists, prints a diff
summary of added and removed edges to stderr.

Usage:
    python generate_app_map.py [--apps-root PATH] [--output PATH]

Stdlib only; no third-party dependencies.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

SKIP_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        "node_modules",
        "migrations",
        ".tox",
        "build",
        "dist",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
    }
)

TEST_PATH_MARKERS: tuple[str, ...] = ("/tests/", "/test_")


@dataclass(frozen=True)
class App:
    short_name: str
    module_path: str
    directory: Path


@dataclass
class Edges:
    runtime: set[tuple[str, str]] = field(default_factory=set)
    test: set[tuple[str, str]] = field(default_factory=set)


def find_apps(root: Path) -> list[App]:
    apps: list[App] = []
    for apps_py in root.rglob("apps.py"):
        if any(part in SKIP_DIRS for part in apps_py.parts):
            continue
        app_dir = apps_py.parent
        try:
            rel = app_dir.relative_to(root)
        except ValueError:
            continue
        module_path = ".".join(rel.parts)
        short_name = rel.parts[-1]
        apps.append(App(short_name, module_path, app_dir))
    apps.sort(key=lambda a: a.short_name)
    return apps


def is_test_path(path: Path) -> bool:
    normalised = str(path).replace("\\", "/")
    if path.name == "conftest.py":
        return True
    return any(marker in normalised for marker in TEST_PATH_MARKERS)


def walk_app_imports(app: App) -> list[tuple[str, Path]]:
    results: list[tuple[str, Path]] = []
    for py_file in app.directory.rglob("*.py"):
        if any(part in SKIP_DIRS for part in py_file.parts):
            continue
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
        except (SyntaxError, UnicodeDecodeError) as exc:
            print(f"WARN: could not parse {py_file}: {exc}", file=sys.stderr)
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                results.append((node.module, py_file))
    return results


def compute_edges(apps: list[App]) -> Edges:
    by_module: dict[str, App] = {a.module_path: a for a in apps}
    module_paths_sorted = sorted(by_module.keys(), key=len, reverse=True)
    edges = Edges()
    for app in apps:
        for imported, file_path in walk_app_imports(app):
            target: App | None = None
            for mp in module_paths_sorted:
                if imported == mp or imported.startswith(mp + "."):
                    target = by_module[mp]
                    break
            if target is None or target.short_name == app.short_name:
                continue
            edge = (app.short_name, target.short_name)
            if is_test_path(file_path):
                edges.test.add(edge)
            else:
                edges.runtime.add(edge)
    edges.test -= edges.runtime
    return edges


def render_mermaid(apps: list[App], edges: Edges) -> str:
    lines = ["```mermaid", "flowchart TB"]
    for app in apps:
        lines.append(f"    {app.short_name}")
    for src, dst in sorted(edges.runtime):
        lines.append(f"    {src} --> {dst}")
    for src, dst in sorted(edges.test):
        lines.append(f"    {src} -.-> {dst}")
    lines.append("```")
    return "\n".join(lines)


def render_table(apps: list[App], edges: Edges) -> str:
    rows = [
        "| App | Runtime deps | Test-only deps |",
        "| --- | --- | --- |",
    ]
    for app in apps:
        runtime_deps = sorted(
            dst for src, dst in edges.runtime if src == app.short_name
        )
        test_deps = sorted(dst for src, dst in edges.test if src == app.short_name)
        rows.append(
            f"| {app.short_name} "
            f"| {', '.join(runtime_deps) or '—'} "
            f"| {', '.join(test_deps) or '—'} |"
        )
    return "\n".join(rows)


HEADER: str = """# App Structure

This file is the authoritative picture of inter-app dependencies in this project. It is **generated** by running `/app_map`.

Treat it as the source of truth for what cross-app imports are allowed. Any implementation plan that introduces a new edge must flag the change via `/plan_structure_review` and get approval before code is written.

- **Solid arrows** — runtime imports (one app imports from another outside of tests).
- **Dashed arrows** — test-only imports (cross-app fixtures or helpers).
- **No arrow** — no import relationship; treat these apps as independent.

Regenerate this file whenever the graph changes: `/app_map`.

"""

LEGEND: str = """

## Legend

- `A --> B` — `A` imports from `B` at runtime.
- `A -.-> B` — `A` imports from `B` only in test code (tests, conftest, factories).
- Apps with no edges are self-contained.
"""


MERMAID_BLOCK_RE = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)
SOLID_EDGE_RE = re.compile(r"^(\w+)\s*-->\s*(\w+)$")
DASHED_EDGE_RE = re.compile(r"^(\w+)\s*-\.->\s*(\w+)$")


def parse_existing_edges(path: Path) -> Edges | None:
    if not path.exists():
        return None
    content = path.read_text(encoding="utf-8")
    match = MERMAID_BLOCK_RE.search(content)
    if not match:
        return None
    edges = Edges()
    for raw in match.group(1).splitlines():
        line = raw.strip()
        solid = SOLID_EDGE_RE.match(line)
        dashed = DASHED_EDGE_RE.match(line)
        if solid:
            edges.runtime.add((solid.group(1), solid.group(2)))
        elif dashed:
            edges.test.add((dashed.group(1), dashed.group(2)))
    return edges


def diff_edges(old: Edges, new: Edges) -> tuple[list[str], list[str]]:
    added_runtime = sorted(new.runtime - old.runtime)
    added_test = sorted(new.test - old.test)
    removed_runtime = sorted(old.runtime - new.runtime)
    removed_test = sorted(old.test - new.test)
    added = [f"+ {s} --> {d} (runtime)" for s, d in added_runtime] + [
        f"+ {s} -.-> {d} (test-only)" for s, d in added_test
    ]
    removed = [f"- {s} --> {d} (runtime)" for s, d in removed_runtime] + [
        f"- {s} -.-> {d} (test-only)" for s, d in removed_test
    ]
    return added, removed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apps-root",
        type=Path,
        default=Path.cwd(),
        help="Directory to scan for Django apps (default: cwd).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/app_structure.md"),
        help="Path to write the diagram file (default: docs/app_structure.md).",
    )
    args = parser.parse_args()

    root: Path = args.apps_root.resolve()
    output: Path = (
        args.output.resolve()
        if args.output.is_absolute()
        else (Path.cwd() / args.output).resolve()
    )

    apps = find_apps(root)
    if not apps:
        print(
            f"ERROR: no Django apps found under {root} (no apps.py files).",
            file=sys.stderr,
        )
        return 1
    print(
        f"Found {len(apps)} app(s): {', '.join(a.short_name for a in apps)}",
        file=sys.stderr,
    )

    new_edges = compute_edges(apps)
    old_edges = parse_existing_edges(output)

    body = (
        HEADER
        + render_mermaid(apps, new_edges)
        + "\n\n## Dependency table\n\n"
        + render_table(apps, new_edges)
        + LEGEND
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(body, encoding="utf-8")
    print(f"Wrote {output}", file=sys.stderr)

    if old_edges is None:
        print("\nInitial generation. No prior diagram to diff against.")
        return 0

    added, removed = diff_edges(old_edges, new_edges)
    if not added and not removed:
        print("\nNo changes vs the previous diagram.")
        return 0
    print("\nChanges vs previous diagram:")
    for line in added:
        print(line)
    for line in removed:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
