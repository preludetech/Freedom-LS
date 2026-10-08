# ruff: noqa: T201
#!/usr/bin/env python3
"""Pick the pytest tier for a set of changed paths and print the paths to run.

Usage:
    python select_tests.py [--working-tree] [<path>...]

Prints `tier:`, one `why:` line per changed path and, for a targeted or full
run, the `command:` to run. Project-specific globs come from `[tool.test_tiers]`
in `pyproject.toml`. Stdlib only, like its siblings.
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

from check_test_mirroring import is_collected, owning_app
from generate_app_map import App, Edges, find_apps, parse_existing_edges

# Paths whose change cannot alter a test result. "*.md" is root-level only on purpose:
# markdown deeper in the tree can be content that tests read.
NONE_GLOBS: tuple[str, ...] = (
    "docs/**",
    ".github/**",
    "*.md",
    ".claude/**/*.md",
    ".claude/**/*.json",
    ".claude/agent-memory/**",
    ".gitignore",
)

# Paths with fan-out the mirror and the app map cannot see. One hit means the whole suite.
ESCALATION_GLOBS: tuple[str, ...] = (
    "**/migrations/**",
    "**/conftest.py",
    "**/factories.py",
    "**/fixtures/**",
    "**/urls.py",
    "**/middleware.py",
    "**/signals.py",
    "**/apps.py",
    "pyproject.toml",
    "uv.lock",
)

# Repository tooling has its tests in the top-level tests/ directory: the wrappers
# ds:init generates, and helpers beside those tests.
TOOLING: tuple[tuple[str, tuple[str, ...]], ...] = (
    (".claude/*/scripts/**", ("tests",)),
    ("tests/**", ("tests",)),
)

# Changes a browser can see; the touched app's browser tests stay in the targeted run.
UI_GLOBS: tuple[str, ...] = (
    "**/templates/**",
    "**/static/**",
    "**/*.html",
    "**/*.css",
    "**/*.js",
    "**/views.py",
    "**/views/**",
)

APP_MAP = "docs/app_structure.md"

FULL_COMMAND = "uv run pytest -n auto"
TARGETED_PREFIX = "uv run pytest -n auto --no-cov"


class ConfigError(Exception):
    """A malformed `[tool.test_tiers]` table."""


@dataclass(frozen=True)
class TierConfig:
    none: tuple[str, ...]
    escalation: tuple[str, ...]
    tooling: tuple[tuple[str, tuple[str, ...]], ...]


@dataclass(frozen=True)
class Decision:
    path: str
    kind: Literal["none", "select", "full"]
    selects: tuple[str, ...]
    reason: str
    touched: tuple[str, ...] = ()


def glob_list(
    table: dict[str, object], key: str, key_prefix: str = ""
) -> tuple[str, ...]:
    value = table.get(key, [])
    if not isinstance(value, list) or not all(isinstance(g, str) for g in value):
        raise ConfigError(
            f"[tool.test_tiers] {key_prefix}'{key}' must be a list of strings"
        )
    return tuple(value)


def tooling_entries(
    table: dict[str, object],
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """The `tooling` array of tables: each entry maps a glob to test directories."""
    value = table.get("tooling", [])
    if not isinstance(value, list):
        raise ConfigError("[tool.test_tiers] 'tooling' must be an array of tables")
    entries: list[tuple[str, tuple[str, ...]]] = []
    for entry in value:
        if not isinstance(entry, dict):
            raise ConfigError("[tool.test_tiers] 'tooling' must be an array of tables")
        glob = entry.get("glob")
        if not isinstance(glob, str):
            raise ConfigError("[tool.test_tiers] 'tooling' entry needs a string 'glob'")
        entries.append((glob, glob_list(entry, "tests", key_prefix="tooling ")))
    return tuple(entries)


def load_tier_config(project_root: Path) -> TierConfig:
    """Read `[tool.test_tiers]`, with the generic lists extended by the project's.

    An absent file or table leaves the generic lists as they are.
    """
    try:
        data = tomllib.loads((project_root / "pyproject.toml").read_text("utf-8"))
    except FileNotFoundError:
        data = {}
    table = data.get("tool", {}).get("test_tiers", {})
    return TierConfig(
        none=NONE_GLOBS + glob_list(table, "none"),
        escalation=ESCALATION_GLOBS + glob_list(table, "escalation"),
        tooling=TOOLING + tooling_entries(table),
    )


def first_match(path: str, globs: tuple[str, ...]) -> str | None:
    """The first glob that matches `path`, so the reason can name it."""
    posix = PurePosixPath(path)
    return next((glob for glob in globs if posix.full_match(glob)), None)


def importers(app: App, edges: Edges) -> list[tuple[str, str]]:
    """(importer short name, reason) for every app with a dep on `app` in the map."""
    found = []
    for pairs, dep in ((edges.runtime, "runtime dep"), (edges.test, "test-only dep")):
        found += [
            (src, f"{src} has a {dep} on {app.short_name}")
            for src, dst in pairs
            if dst == app.short_name
        ]
    return sorted(found)


def tests_dir_of(app: App, project_root: Path) -> str:
    return (app.directory / "tests").relative_to(project_root).as_posix()


def decide_app_path(
    path: str,
    app: App,
    apps: list[App],
    edges: Edges | None,
    project_root: Path,
) -> list[Decision]:
    """The owning app's test directory, then one decision per importer of the app."""
    if edges is None:
        return [Decision(path, "full", (), f"{APP_MAP} missing")]

    tests_dir = tests_dir_of(app, project_root)
    if not (project_root / tests_dir).is_dir():
        owner = Decision(
            path, "none", (), f"owning app {app.short_name} has no tests directory"
        )
    else:
        reason = f"owning app {app.short_name}"
        touched: tuple[str, ...] = ()
        playwright_dir = f"{tests_dir}/playwright"
        if first_match(path, UI_GLOBS) is not None:
            touched = (tests_dir,)
            if (project_root / playwright_dir).is_dir():
                reason += f"; playwright: {playwright_dir}"
        owner = Decision(path, "select", (tests_dir,), reason, touched)

    by_name = {a.short_name: a for a in apps}
    decisions = [owner]
    for name, reason in importers(app, edges):
        importer = by_name.get(name)
        if importer is None:
            decisions.append(Decision(path, "none", (), f"{reason}; app not found"))
            continue
        importer_tests = tests_dir_of(importer, project_root)
        if (project_root / importer_tests).is_dir():
            decisions.append(Decision(path, "select", (importer_tests,), reason))
        else:
            decisions.append(
                Decision(path, "none", (), f"{reason}; no tests directory")
            )
    return decisions


def decide_tooling(
    path: str, config: TierConfig, project_root: Path
) -> list[Decision] | None:
    """The test directories of the first tooling entry whose glob matches `path`.

    Each listed directory that does not exist selects nothing and gets its own reason.
    """
    posix = PurePosixPath(path)
    for glob, directories in config.tooling:
        if not posix.full_match(glob):
            continue
        present = tuple(d for d in directories if (project_root / d).is_dir())
        decisions = [
            Decision(path, "none", (), f"tooling; {d} does not exist")
            for d in directories
            if d not in present
        ]
        if present:
            decisions.insert(0, Decision(path, "select", present, "tooling"))
        return decisions
    return None


def decide(
    path: str,
    apps: list[App],
    config: TierConfig,
    edges: Edges | None,
    project_root: Path,
) -> list[Decision]:
    """Apply the rules in order; the first one that matches `path` decides."""
    none_glob = first_match(path, config.none)
    if none_glob is not None:
        return [Decision(path, "none", (), f"matches {none_glob}")]

    posix = PurePosixPath(path)
    app = owning_app(apps, project_root, path)
    if is_collected(posix.name) and "tests" in posix.parts:
        if not (project_root / path).exists():
            return [Decision(path, "none", (), "deleted test file")]
        reason = "changed test file"
        touched: tuple[str, ...] = ()
        if app is not None:
            tests_dir = tests_dir_of(app, project_root)
            if path.startswith(f"{tests_dir}/playwright/"):
                reason += f"; playwright: {tests_dir}/playwright"
                touched = (tests_dir,)
        return [Decision(path, "select", (path,), reason, touched)]

    escalation_glob = first_match(path, config.escalation)
    if escalation_glob is not None:
        return [Decision(path, "full", (), f"matches {escalation_glob}")]

    if app is not None:
        return decide_app_path(path, app, apps, edges, project_root)

    tooling = decide_tooling(path, config, project_root)
    if tooling is not None:
        return tooling

    return [Decision(path, "full", (), "unmapped path")]


def git_lines(argv: list[str]) -> list[str]:
    result = subprocess.run(  # noqa: S603
        argv, check=True, capture_output=True, text=True
    )
    return result.stdout.splitlines()


def changed_paths(paths: list[str], working_tree: bool) -> list[str]:
    """The given paths plus, with `working_tree`, uncommitted and untracked ones."""
    found = set(paths)
    if working_tree:
        found.update(git_lines(["git", "diff", "--name-only", "HEAD"]))
        found.update(git_lines(["git", "ls-files", "--others", "--exclude-standard"]))
    return sorted(found)


def compose_command(selected: set[str], touched: set[str], project_root: Path) -> str:
    """The pytest line for a targeted run; `touched` keeps those apps' browser tests in."""
    ignores = [
        f"--ignore={shlex.quote(d + '/playwright')}"
        for d in sorted(selected)
        if d not in touched and (project_root / d / "playwright").is_dir()
    ]
    return " ".join(
        [TARGETED_PREFIX, *ignores, *(shlex.quote(p) for p in sorted(selected))]
    )


def minimal_selection(selects: set[str], project_root: Path) -> set[str]:
    """Drop every selected path that lies inside another selected directory."""
    directories = {s for s in selects if (project_root / s).is_dir()}
    return {
        s
        for s in selects
        if s in directories or not any(s.startswith(d + "/") for d in directories)
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="repo-relative changed paths")
    parser.add_argument(
        "--working-tree",
        action="store_true",
        help="also use uncommitted and untracked paths",
    )
    args = parser.parse_args()

    project_root = Path.cwd()
    try:
        paths = changed_paths(args.paths, args.working_tree)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        parser.error(f"git failed: {exc}")
    try:
        config = load_tier_config(project_root)
    except (tomllib.TOMLDecodeError, ConfigError) as exc:
        parser.error(str(exc))

    apps = find_apps(project_root)
    edges = parse_existing_edges(project_root / APP_MAP)
    decisions = [d for p in paths for d in decide(p, apps, config, edges, project_root)]

    selected = minimal_selection(
        {s for d in decisions for s in d.selects}, project_root
    )
    touched = {t for d in decisions for t in d.touched}
    if any(d.kind == "full" for d in decisions):
        tier = "full"
    elif selected:
        tier = "targeted"
    else:
        tier = "none"

    print(f"tier: {tier}")
    for d in decisions:
        outcome = {"none": "none", "full": "full"}.get(d.kind) or ", ".join(d.selects)
        print(f"why: {d.path} -> {outcome} ({d.reason})")
    if tier == "full":
        print(f"command: {FULL_COMMAND}")
    elif tier == "targeted":
        print(f"command: {compose_command(selected, touched, project_root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
