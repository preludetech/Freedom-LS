#!/usr/bin/env python3
# ruff: noqa: T201
"""Pick the pytest tier for a set of changed paths and print the paths to run.

Usage:
    python select_tests.py [--working-tree] [--range <rev>..<rev>]...
        [--tests-changed-in <rev>..<rev>] [<path>...]

Prints `tier:`, one `why:` line per changed path and, for a targeted or full
run, the `command:` to run. Project-specific globs come from `[tool.test_tiers]`
in `pyproject.toml`. Stdlib only, like its siblings.
"""

from __future__ import annotations

import argparse
import re
import shlex
import subprocess
import tomllib
from dataclasses import dataclass, replace
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

# Plain revision characters on both sides of `..`. Nothing else reaches git, and
# `--end-of-options` stops a value from reading as an option either way.
RANGE_PATTERN = re.compile(r"^[A-Za-z0-9_./~^@{}-]+\.\.[A-Za-z0-9_./~^@{}-]+$")

BRANCH_TEST_REASON = "branch test file; runs only with a targeted tier"

FULL_COMMAND = "uv run pytest -n auto"
TARGETED_PREFIX = "uv run pytest -n auto --no-cov"


class ConfigError(Exception):
    """A malformed `[tool.test_tiers]` table."""


@dataclass(frozen=True)
class TierConfig:
    none: tuple[str, ...]
    escalation: tuple[str, ...]
    tooling: tuple[tuple[str, tuple[str, ...]], ...]
    # The marker expression every tier runs with. A later `-m` replaces the one in
    # `addopts`, so tests the default run deselects still run when a tier selects them.
    markers: str | None = None


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
    """The `tooling` array of tables: each entry maps a glob to test directories or files."""
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


def marker_expression(table: dict[str, object]) -> str | None:
    value = table.get("markers")
    if value is not None and not isinstance(value, str):
        raise ConfigError("[tool.test_tiers] 'markers' must be a string")
    return value


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
        markers=marker_expression(table),
    )


def marker_args(config: TierConfig) -> list[str]:
    return [] if config.markers is None else ["-m", shlex.quote(config.markers)]


def full_command(config: TierConfig) -> str:
    return " ".join([FULL_COMMAND, *marker_args(config)])


def first_match(path: str, globs: tuple[str, ...]) -> str | None:
    """The first glob that matches `path`, so the reason can name it."""
    posix = PurePosixPath(path)
    return next((glob for glob in globs if posix.full_match(glob)), None)


def importers(app: App, edges: Edges) -> list[tuple[str, str]]:
    """(importer short name, reason) for every app whose code or tests reach `app`.

    Runtime deps chain: an app that imports an importer of `app` runs `app`'s code too.
    A test-only dep is one hop, since only that app's tests reach `app`, not its code.
    """
    found: dict[str, str] = {}
    queue = [app.short_name]
    while queue:
        target = queue.pop(0)
        via = "" if target == app.short_name else f" through {target}"
        for pairs, dep in (
            (edges.runtime, "runtime dep"),
            (edges.test, "test-only dep"),
        ):
            for src, dst in sorted(pairs):
                if dst != target or src == app.short_name or src in found:
                    continue
                found[src] = f"{src} has a {dep} on {app.short_name}{via}"
                if dep == "runtime dep":
                    queue.append(src)
    return sorted(found.items())


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


def is_test_target(target: Path) -> bool:
    """A directory, or a file pytest collects."""
    return target.is_dir() or (target.is_file() and is_collected(target.name))


def playwright_tests_root(posix: PurePosixPath) -> str | None:
    """The tests directory whose `playwright/` subdirectory holds `posix`, if any."""
    parts = posix.parts
    for index in range(1, len(parts) - 1):
        if parts[index] == "playwright" and parts[index - 1] == "tests":
            return "/".join(parts[:index])
    return None


def decide_tooling(
    path: str, config: TierConfig, project_root: Path
) -> list[Decision] | None:
    """The test directories and files of the first tooling entry whose glob matches `path`.

    Each listed entry that does not exist selects nothing and gets its own reason.
    """
    posix = PurePosixPath(path)
    for glob, targets in config.tooling:
        if not posix.full_match(glob):
            continue
        present = tuple(t for t in targets if is_test_target(project_root / t))
        decisions = [
            Decision(path, "none", (), f"tooling; {t} does not exist")
            for t in targets
            if t not in present
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
    untracked: bool = False,
) -> list[Decision]:
    """Apply the rules in order; the first one that matches `path` decides.

    A path no rule knows is the whole suite, unless git does not know it either: a stray
    untracked file is not a change that any test can see.
    """
    none_glob = first_match(path, config.none)
    if none_glob is not None:
        return [Decision(path, "none", (), f"matches {none_glob}")]

    posix = PurePosixPath(path)
    if is_collected(posix.name) and "tests" in posix.parts:
        if not (project_root / path).exists():
            return [Decision(path, "none", (), "deleted test file")]
        reason = "changed test file"
        touched: tuple[str, ...] = ()
        tests_root = playwright_tests_root(posix)
        if tests_root is not None:
            reason += f"; playwright: {tests_root}/playwright"
            touched = (tests_root,)
        return [Decision(path, "select", (path,), reason, touched)]

    escalation_glob = first_match(path, config.escalation)
    if escalation_glob is not None:
        return [Decision(path, "full", (), f"matches {escalation_glob}")]

    app = owning_app(apps, project_root, path)
    if app is not None:
        return decide_app_path(path, app, apps, edges, project_root)

    tooling = decide_tooling(path, config, project_root)
    if tooling is not None:
        return tooling

    if untracked:
        return [Decision(path, "none", (), "untracked and unmapped")]
    return [Decision(path, "full", (), "unmapped path")]


def git_paths(argv: list[str]) -> list[str]:
    """The NUL-separated paths a git command prints, so no name is ever quoted."""
    result = subprocess.run(  # noqa: S603
        argv, check=True, capture_output=True, text=True
    )
    return [p for p in result.stdout.split("\0") if p]


def range_type(value: str) -> str:
    if RANGE_PATTERN.fullmatch(value) is None:
        raise argparse.ArgumentTypeError(f"not a <rev>..<rev> range: {value!r}")
    return value


def range_paths(revision_range: str) -> list[str]:
    """Both sides of a rename are changes: the old module's importers still name it."""
    return git_paths(
        [
            "git",
            "diff",
            "-z",
            "--name-only",
            "--no-renames",
            "--end-of-options",
            revision_range,
        ]
    )


def changed_paths(
    paths: list[str], working_tree: bool, revision_ranges: list[str]
) -> tuple[list[str], set[str]]:
    """The given paths, those each range changed and, with `working_tree`, uncommitted
    and untracked ones. The second value is the untracked subset.
    """
    found = set(paths)
    for revision_range in revision_ranges:
        found.update(range_paths(revision_range))
    untracked: set[str] = set()
    if working_tree:
        found.update(
            git_paths(["git", "diff", "-z", "--name-only", "--no-renames", "HEAD"])
        )
        untracked.update(
            git_paths(["git", "ls-files", "-z", "--others", "--exclude-standard"])
        )
        found.update(untracked)
    return sorted(found), untracked


def branch_test_decisions(
    revision_range: str,
    apps: list[App],
    config: TierConfig,
    edges: Edges | None,
    project_root: Path,
) -> list[Decision]:
    """One decision per collected test file the range changed and the checkout still has.

    These files join the selection but are kept out of the tier calculation, so a
    branch's own tests never turn a `none` result into a run.
    """
    decisions = [
        d
        for path in sorted(range_paths(revision_range))
        for d in decide(path, apps, config, edges, project_root)
        if d.kind == "select" and d.reason.startswith("changed test file")
    ]
    return [replace(d, reason=BRANCH_TEST_REASON) for d in decisions]


def compose_command(
    selected: set[str], touched: set[str], config: TierConfig, project_root: Path
) -> str:
    """The pytest line for a targeted run; `touched` keeps those apps' browser tests in."""
    ignores = [
        f"--ignore={shlex.quote(d + '/playwright')}"
        for d in sorted(selected)
        if d not in touched and (project_root / d / "playwright").is_dir()
    ]
    return " ".join(
        [
            TARGETED_PREFIX,
            *marker_args(config),
            *ignores,
            *(shlex.quote(p) for p in sorted(selected)),
        ]
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
    parser.add_argument(
        "--range",
        type=range_type,
        action="append",
        default=[],
        help="also use the paths changed in <rev>..<rev>; may be repeated",
    )
    parser.add_argument(
        "--tests-changed-in",
        type=range_type,
        help=(
            "add the test files changed in <rev>..<rev> to a targeted run; "
            "they never raise the tier"
        ),
    )
    args = parser.parse_args()

    project_root = Path.cwd()
    try:
        paths, untracked = changed_paths(args.paths, args.working_tree, args.range)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        parser.error(f"git failed: {exc}")
    try:
        config = load_tier_config(project_root)
    except (tomllib.TOMLDecodeError, ConfigError) as exc:
        parser.error(str(exc))

    apps = find_apps(project_root)
    edges = parse_existing_edges(project_root / APP_MAP)
    decisions = [
        d
        for p in paths
        for d in decide(p, apps, config, edges, project_root, p in untracked)
    ]
    tier_decisions = decisions
    if args.tests_changed_in is not None:
        try:
            decisions = decisions + branch_test_decisions(
                args.tests_changed_in, apps, config, edges, project_root
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            parser.error(f"git failed: {exc}")

    if any(d.kind == "full" for d in tier_decisions):
        tier = "full"
    elif any(d.selects for d in tier_decisions):
        tier = "targeted"
    else:
        tier = "none"
    selected = minimal_selection(
        {s for d in decisions for s in d.selects}, project_root
    )
    touched = {t for d in decisions for t in d.touched}

    print(f"tier: {tier}")
    for d in decisions:
        outcome = {"none": "none", "full": "full"}.get(d.kind) or ", ".join(d.selects)
        print(f"why: {d.path} -> {outcome} ({d.reason})")
    if tier == "full":
        print(f"command: {full_command(config)}")
    elif tier == "targeted":
        print(f"command: {compose_command(selected, touched, config, project_root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
