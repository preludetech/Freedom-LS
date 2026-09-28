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
import tomllib
from collections.abc import Iterator
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

# Django relation fields whose first positional argument may name a related
# model by "<app label>.<Model>" instead of importing it.
RELATION_FIELDS: frozenset[str] = frozenset(
    {"ForeignKey", "OneToOneField", "ManyToManyField"}
)

REQUIRED_CONFIG_KEYS: tuple[str, ...] = (
    "user_model_app",
    "declared_edges",
    "import_contracts",
    "import_baseline",
    "mirroring_baseline",
    "mirroring_exemptions",
)


@dataclass(frozen=True)
class App:
    short_name: str
    module_path: str
    directory: Path


@dataclass
class Edges:
    runtime: set[tuple[str, str]] = field(default_factory=set)
    test: set[tuple[str, str]] = field(default_factory=set)


@dataclass(frozen=True)
class TestOrganisationConfig:
    user_model_app: str
    declared_edges: Path
    import_contracts: Path
    import_baseline: Path
    mirroring_baseline: Path
    mirroring_exemptions: Path


class ConfigError(Exception):
    """A bad `[tool.test_organisation]` table, declared edge, baseline or exemption line."""


def load_config(project_root: Path) -> TestOrganisationConfig | None:
    """Read `[tool.test_organisation]` from `project_root/pyproject.toml`.

    Returns `None` when the file or the table is absent, so the rest of the script
    can run in its original, table-free mode.
    """
    pyproject = project_root / "pyproject.toml"
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    table = data.get("tool", {}).get("test_organisation")
    if table is None:
        return None
    for key in REQUIRED_CONFIG_KEYS:
        if key not in table:
            raise ConfigError(f"[tool.test_organisation] is missing '{key}'")
    return TestOrganisationConfig(
        user_model_app=table["user_model_app"],
        declared_edges=project_root / table["declared_edges"],
        import_contracts=project_root / table["import_contracts"],
        import_baseline=project_root / table["import_baseline"],
        mirroring_baseline=project_root / table["mirroring_baseline"],
        mirroring_exemptions=project_root / table["mirroring_exemptions"],
    )


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
    """Classify a file by its path relative to the apps root, not its absolute path.

    A path like `tmp_path`'s `test_something0/pkg/alpha/models.py` must not read as
    test code just because the *project* happens to sit under a directory named
    `test_something0`; only markers under the apps root count.
    """
    normalised = "/" + path.as_posix()
    if path.name in ("conftest.py", "factories.py"):
        return True
    return any(marker in normalised for marker in TEST_PATH_MARKERS)


def iter_app_trees(app: App) -> Iterator[tuple[Path, ast.Module]]:
    for py_file in app.directory.rglob("*.py"):
        if any(part in SKIP_DIRS for part in py_file.parts):
            continue
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
        except (SyntaxError, UnicodeDecodeError) as exc:
            print(f"WARN: could not parse {py_file}: {exc}", file=sys.stderr)
            continue
        yield py_file, tree


def relative_path(app: App, file_path: Path) -> Path:
    """`file_path`'s path relative to the apps root, rebuilt without threading the root through.

    `find_apps` derives `module_path` from the app directory's path under the apps
    root, so re-splitting it and appending the file's path within the app directory
    gives the same result.
    """
    return Path(*app.module_path.split("."), file_path.relative_to(app.directory))


def module_name(app: App, file_path: Path) -> str:
    parts = list(relative_path(app, file_path).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def call_name(node: ast.Call) -> str | None:
    """The called name for both `ForeignKey(...)` and `models.ForeignKey(...)`."""
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def app_labels(apps: list[App]) -> dict[str, App]:
    """Map each app's Django app label to its `App`, read from `apps.py`.

    Falls back to the app's short name, which is what Django itself defaults an
    `AppConfig.label` to when the class doesn't set one.
    """
    labels: dict[str, App] = {}
    for app in apps:
        label = app.short_name
        apps_py = app.directory / "apps.py"
        try:
            tree = ast.parse(apps_py.read_text(encoding="utf-8"), filename=str(apps_py))
        except (OSError, SyntaxError, UnicodeDecodeError):
            labels[label] = app
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for stmt in node.body:
                if (
                    isinstance(stmt, ast.Assign)
                    and any(
                        isinstance(target, ast.Name) and target.id == "label"
                        for target in stmt.targets
                    )
                    and isinstance(stmt.value, ast.Constant)
                    and isinstance(stmt.value.value, str)
                ):
                    label = stmt.value.value
        labels[label] = app
    return labels


def is_auth_user_model_attribute(node: ast.expr) -> bool:
    """Whether `node` is `settings.AUTH_USER_MODEL` (however `settings` is imported)."""
    return isinstance(node, ast.Attribute) and node.attr == "AUTH_USER_MODEL"


def walk_model_relations(app: App, labels: dict[str, App], user_app: App) -> set[App]:
    """Apps a relation field or `get_user_model()` call in `app`'s non-test code names.

    Only `"<label>.<Model>"` first arguments count for the string-label case; a label
    with no dot names a model in the same app and is skipped, and a label matching no
    known app (a third-party app such as `sites`) is ignored. `settings.AUTH_USER_MODEL`
    as that first argument, and any `get_user_model()` call, both name `user_app`.
    """
    targets: set[App] = set()
    for file_path, tree in iter_app_trees(app):
        if is_test_path(relative_path(app, file_path)):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = call_name(node)
            if name == "get_user_model":
                if user_app is not app:
                    targets.add(user_app)
                continue
            if not (name in RELATION_FIELDS and node.args):
                continue
            first = node.args[0]
            if is_auth_user_model_attribute(first):
                if user_app is not app:
                    targets.add(user_app)
                continue
            if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
                continue
            if "." not in first.value:
                continue
            target = labels.get(first.value.split(".", 1)[0])
            if target is not None and target is not app:
                targets.add(target)
    return targets


def load_declared_edges(path: Path, apps: list[App]) -> set[tuple[str, str]]:
    """Read `[[edge]]` entries from `declared_edges.toml`.

    A project's config can name this file before the file exists (earlier slices'
    test trees do), so a missing file means no declared edges rather than an error.
    """
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return set()
    short_names = {app.short_name for app in apps}
    edges: set[tuple[str, str]] = set()
    for entry in data.get("edge", []):
        src, dst, reason = entry.get("from"), entry.get("to"), entry.get("reason")
        for name in (src, dst):
            if name not in short_names:
                raise ConfigError(f"declared_edges.toml: '{name}' is not a known app")
        if not reason:
            raise ConfigError(f"declared_edges.toml: {src} -> {dst} has no reason")
        edges.add((src, dst))
    return edges


def walk_app_imports(app: App) -> list[tuple[str, Path]]:
    results: list[tuple[str, Path]] = []
    for py_file, tree in iter_app_trees(app):
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                results.append((node.module, py_file))
    return results


def compute_edges(apps: list[App], config: TestOrganisationConfig | None) -> Edges:
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
            if is_test_path(relative_path(app, file_path)):
                edges.test.add(edge)
            else:
                edges.runtime.add(edge)
    if config is not None:
        user_app = by_module.get(config.user_model_app)
        if user_app is None:
            raise ConfigError(
                f"user_model_app '{config.user_model_app}' names no known app"
            )
        labels = app_labels(apps)
        for app in apps:
            for target in walk_model_relations(app, labels, user_app):
                edges.runtime.add((app.short_name, target.short_name))
        for src, dst in load_declared_edges(config.declared_edges, apps):
            if (src, dst) in edges.runtime:
                raise ConfigError(
                    f"declared edge {src} -> {dst} is already detected; "
                    "remove it from declared_edges.toml"
                )
            edges.runtime.add((src, dst))
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

Treat it as the source of truth for what cross-app imports are allowed. Any implementation plan that introduces a new cross-app edge should be called out and approved before code is written.

- **Solid arrows** — runtime imports (one app imports from another outside of tests).
- **Dashed arrows** — test-only imports (cross-app fixtures or helpers).
- **No arrow** — no import relationship; treat these apps as independent.

Regenerate this file whenever the graph changes: `/app_map`.

"""

HEADER_WITH_TEST_ORGANISATION: str = """# App Structure

This file is the authoritative picture of inter-app dependencies in this project. It is **generated** by running `/app_map`.

Treat it as the source of truth for what cross-app imports are allowed. Any implementation plan that introduces a new cross-app edge should be called out and approved before code is written.

- **Solid arrows** — runtime imports (one app imports from another outside of tests), model relations by string label or to the user model, and declared edges.
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

LEGEND_WITH_TEST_ORGANISATION: str = """

## Legend

- `A --> B` — `A` imports from `B` at runtime, has a model relation to `B` by string label or the user model, or declares the edge in `declared_edges.toml`.
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
    project_root: Path = Path.cwd()
    output: Path = (
        args.output.resolve()
        if args.output.is_absolute()
        else (project_root / args.output).resolve()
    )

    try:
        config = load_config(project_root)
    except ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

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

    try:
        new_edges = compute_edges(apps, config)
    except ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    old_edges = parse_existing_edges(output)

    header = HEADER_WITH_TEST_ORGANISATION if config is not None else HEADER
    legend = LEGEND_WITH_TEST_ORGANISATION if config is not None else LEGEND
    body = (
        header
        + render_mermaid(apps, new_edges)
        + "\n\n## Dependency table\n\n"
        + render_table(apps, new_edges)
        + legend
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
