#!/usr/bin/env python3
# ruff: noqa: T201
"""Pick the pytest tier for a set of changed paths and print the paths to run.

Usage:
    python select_tests.py [--working-tree] [--range <rev>..<rev>]...
        [--upstream-range <old>..<new>] [--tests-changed-in <rev>..<rev>] [<path>...]

Prints `tier:`, one `why:` line per changed path and, for a targeted or full
run, the `command:` to run. Project-specific globs come from `[tool.test_tiers]`
in `pyproject.toml`. Stdlib only, like its siblings.

`--upstream-range` names the paths another line of history brought in (main, after a
rebase). One the branch's own diff (`<new>..HEAD` plus the working tree) does not hold
counts only where it meets the apps the branch changed or imports.
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
)

# Dependency manifests and lockfiles change what every test imports, whoever changed them.
DEPENDENCY_GLOBS: tuple[str, ...] = ("pyproject.toml", "uv.lock")

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

RUNNER_WRAPPER = ".claude/ds/scripts/run_tests.sh"

FULL_COMMAND = "uv run pytest -n auto"
TARGETED_PREFIX = "uv run pytest -n auto --no-cov"


class ConfigError(Exception):
    """A malformed `[tool.test_tiers]` table."""


@dataclass(frozen=True)
class TierConfig:
    none: tuple[str, ...]
    escalation: tuple[str, ...]
    dependency: tuple[str, ...]
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
        dependency=DEPENDENCY_GLOBS + glob_list(table, "dependency_files"),
        tooling=TOOLING + tooling_entries(table),
        markers=marker_expression(table),
    )


def marker_args(config: TierConfig) -> list[str]:
    return [] if config.markers is None else ["-m", shlex.quote(config.markers)]


def runner_prefix(project_root: Path) -> list[str]:
    """The runner wrapper when the project has it. A project that has not installed it keeps
    the bare command."""
    return [RUNNER_WRAPPER] if (project_root / RUNNER_WRAPPER).is_file() else []


def full_command(config: TierConfig, project_root: Path) -> str:
    return " ".join([*runner_prefix(project_root), FULL_COMMAND, *marker_args(config)])


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


def runtime_closure(apps: set[str], edges: Edges) -> set[str]:
    """`apps` plus every app their code imports, through any number of runtime deps."""
    found = set(apps)
    queue = list(apps)
    while queue:
        source = queue.pop()
        for src, dst in edges.runtime:
            if src == source and dst not in found:
                found.add(dst)
                queue.append(dst)
    return found


def app_dependencies(app: str, edges: Edges) -> set[str]:
    """Every app whose code `app`'s code or tests run.

    Runtime deps chain. A test-only dep is one hop from `app` itself, then that app's own
    runtime deps chain: `app`'s tests import it, and it imports them.
    """
    test_only = {dst for src, dst in edges.test if src == app}
    return (runtime_closure({app}, edges) | runtime_closure(test_only, edges)) - {app}


def owner_decision(path: str, app: App, project_root: Path) -> Decision:
    """The owning app's test directory, or `none` when it has none."""
    tests_dir = tests_dir_of(app, project_root)
    if not (project_root / tests_dir).is_dir():
        return Decision(
            path, "none", (), f"owning app {app.short_name} has no tests directory"
        )
    reason = f"owning app {app.short_name}"
    touched: tuple[str, ...] = ()
    playwright_dir = f"{tests_dir}/playwright"
    if first_match(path, UI_GLOBS) is not None:
        touched = (tests_dir,)
        if (project_root / playwright_dir).is_dir():
            reason += f"; playwright: {playwright_dir}"
    return Decision(path, "select", (tests_dir,), reason, touched)


def importer_decisions(
    path: str,
    app: App,
    apps: list[App],
    edges: Edges,
    project_root: Path,
    only: frozenset[str] | None = None,
) -> list[Decision]:
    """One decision per importer of `app`, or per importer named in `only`."""
    by_name = {a.short_name: a for a in apps}
    decisions: list[Decision] = []
    for name, reason in importers(app, edges):
        if only is not None and name not in only:
            continue
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
    return [
        owner_decision(path, app, project_root),
        *importer_decisions(path, app, apps, edges, project_root),
    ]


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


def matching_tooling_glob(path: str, config: TierConfig) -> str | None:
    """The glob of the first tooling entry that matches `path`."""
    posix = PurePosixPath(path)
    return next((glob for glob, _ in config.tooling if posix.full_match(glob)), None)


def decide_tooling(
    path: str, config: TierConfig, project_root: Path
) -> list[Decision] | None:
    """The test directories and files of the first tooling entry whose glob matches `path`.

    Each listed entry that does not exist selects nothing and gets its own reason.
    """
    glob = matching_tooling_glob(path, config)
    if glob is None:
        return None
    targets = next(
        entry_targets for entry, entry_targets in config.tooling if entry == glob
    )
    present = tuple(t for t in targets if is_test_target(project_root / t))
    decisions = [
        Decision(path, "none", (), f"tooling; {t} does not exist")
        for t in targets
        if t not in present
    ]
    if present:
        decisions.insert(0, Decision(path, "select", present, "tooling"))
    return decisions


def test_file_decision(path: str, project_root: Path) -> Decision | None:
    """The decision for a collected test file under a `tests` directory, or None for any
    other path. A file the checkout no longer has selects nothing."""
    posix = PurePosixPath(path)
    if not (is_collected(posix.name) and "tests" in posix.parts):
        return None
    if not (project_root / path).exists():
        return Decision(path, "none", (), "deleted test file")
    reason = "changed test file"
    touched: tuple[str, ...] = ()
    tests_root = playwright_tests_root(posix)
    if tests_root is not None:
        reason += f"; playwright: {tests_root}/playwright"
        touched = (tests_root,)
    return Decision(path, "select", (path,), reason, touched)


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

    test_file = test_file_decision(path, project_root)
    if test_file is not None:
        return [test_file]

    if first_match(path, config.dependency) is not None:
        return [Decision(path, "full", (), "dependency file")]

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


@dataclass(frozen=True)
class BranchContext:
    branch_apps: frozenset[str]
    related_apps: frozenset[str]
    # The tooling globs some path of the branch's own diff matches.
    tooling_globs: frozenset[str]


def from_main(decisions: list[Decision]) -> list[Decision]:
    """Mark decisions as made for a path main brought in."""
    return [replace(d, reason=f"from main; {d.reason}") for d in decisions]


def related_tests_decision(
    path: str,
    escalation_glob: str,
    apps: list[App],
    context: BranchContext,
    project_root: Path,
) -> Decision:
    """One decision selecting the tests directory of every related app that has one."""
    directories = tuple(
        sorted(
            tests_dir_of(app, project_root)
            for app in apps
            if app.short_name in context.related_apps
            and (project_root / tests_dir_of(app, project_root)).is_dir()
        )
    )
    kind: Literal["none", "select"] = "select" if directories else "none"
    return Decision(path, kind, directories, f"matches {escalation_glob}")


def decide_upstream(
    path: str,
    apps: list[App],
    config: TierConfig,
    edges: Edges,
    context: BranchContext,
    project_root: Path,
) -> list[Decision]:
    """The rules for a path main brought in; the first that matches decides.

    Such a path counts only where it meets the apps the branch changed or imports. A
    dependency file still forces the whole suite, since it changes what every app imports.
    """
    none_glob = first_match(path, config.none)
    if none_glob is not None:
        return from_main([Decision(path, "none", (), f"matches {none_glob}")])

    if first_match(path, config.dependency) is not None:
        return from_main([Decision(path, "full", (), "dependency file")])

    app = owning_app(apps, project_root, path)
    if app is not None and app.short_name not in context.related_apps:
        reason = f"{app.short_name} meets no branch app"
        return from_main([Decision(path, "none", (), reason)])

    test_file = test_file_decision(path, project_root)
    if test_file is not None and app is not None:
        return from_main([test_file])

    escalation_glob = first_match(path, config.escalation)
    if escalation_glob is not None:
        return from_main(
            [related_tests_decision(path, escalation_glob, apps, context, project_root)]
        )

    if app is not None:
        return from_main(
            [
                owner_decision(path, app, project_root),
                *importer_decisions(
                    path, app, apps, edges, project_root, only=context.branch_apps
                ),
            ]
        )

    tooling_glob = matching_tooling_glob(path, config)
    if tooling_glob is None:
        return from_main([Decision(path, "none", (), "unmapped path")])
    if tooling_glob not in context.tooling_globs:
        reason = f"no branch path matches {tooling_glob}"
        return from_main([Decision(path, "none", (), reason)])
    return from_main(decide_tooling(path, config, project_root) or [])


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


def upstream_range_type(value: str) -> str:
    # The range is split in two to build the branch's own diff, so it must hold exactly one
    # `..`: `a...b` and `a..b..c` pass the character check and would split into a different range.
    range_type(value)
    if "..." in value or value.count("..") != 1:
        raise argparse.ArgumentTypeError(f"not a single <rev>..<rev> range: {value!r}")
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


def working_tree_paths() -> tuple[set[str], set[str]]:
    """(uncommitted and untracked paths, the untracked subset)."""
    untracked = set(
        git_paths(["git", "ls-files", "-z", "--others", "--exclude-standard"])
    )
    tracked = set(
        git_paths(["git", "diff", "-z", "--name-only", "--no-renames", "HEAD"])
    )
    return tracked | untracked, untracked


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
        working, untracked = working_tree_paths()
        found.update(working)
    return sorted(found), untracked


@dataclass(frozen=True)
class UpstreamSplit:
    upstream: frozenset[
        str
    ]  # changed by the upstream range, absent from the branch's own diff
    own_paths: frozenset[str]  # the branch's own diff


def split_upstream(
    upstream_range: str, working_tree: set[str]
) -> tuple[set[str], UpstreamSplit]:
    """(every path the upstream range changed, how they split).

    The branch's own diff runs from the range's new end to HEAD, plus `working_tree`.
    """
    _old, new = upstream_range.split("..", 1)
    changed = set(range_paths(upstream_range))
    own_paths = set(range_paths(f"{new}..HEAD")) | working_tree
    return changed, UpstreamSplit(frozenset(changed - own_paths), frozenset(own_paths))


def branch_context(
    paths: set[str],
    apps: list[App],
    edges: Edges,
    config: TierConfig,
    project_root: Path,
) -> BranchContext:
    """The apps the branch's paths belong to, every app those apps run, and the tooling
    globs the paths match."""
    owners = (owning_app(apps, project_root, p) for p in paths)
    branch_apps = {app.short_name for app in owners if app is not None}
    related = set(branch_apps)
    for name in branch_apps:
        related |= app_dependencies(name, edges)
    matches = (matching_tooling_glob(p, config) for p in paths)
    globs = {glob for glob in matches if glob is not None}
    return BranchContext(frozenset(branch_apps), frozenset(related), frozenset(globs))


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
            *runner_prefix(project_root),
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
        "--upstream-range",
        type=upstream_range_type,
        action="append",
        default=[],
        help=(
            "the paths main brought in, <old>..<new>; one the branch's own diff does "
            "not hold counts only where it meets the apps the branch changed or imports"
        ),
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
    if len(args.upstream_range) > 1:
        parser.error("--upstream-range may be given once")

    project_root = Path.cwd()
    split: UpstreamSplit | None = None
    try:
        paths, untracked = changed_paths(args.paths, args.working_tree, args.range)
        if args.upstream_range:
            working = working_tree_paths()[0] if args.working_tree else set()
            changed, split = split_upstream(args.upstream_range[0], working)
            paths = sorted(set(paths) | changed)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        parser.error(f"git failed: {exc}")
    try:
        config = load_tier_config(project_root)
    except (tomllib.TOMLDecodeError, ConfigError) as exc:
        parser.error(str(exc))

    apps = find_apps(project_root)
    edges = parse_existing_edges(project_root / APP_MAP)
    # Without the app map the related apps cannot be computed, so every path takes the
    # branch rules and an app-owned one is `full`.
    upstream: frozenset[str] = frozenset()
    context: BranchContext | None = None
    if split is not None and edges is not None:
        upstream = split.upstream
        branch_paths = (set(paths) - upstream) | split.own_paths
        context = branch_context(branch_paths, apps, edges, config, project_root)
    decisions = [
        d
        for p in paths
        for d in (
            decide_upstream(p, apps, config, edges, context, project_root)
            if context is not None and edges is not None and p in upstream
            else decide(p, apps, config, edges, project_root, p in untracked)
        )
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
        print(f"command: {full_command(config, project_root)}")
    elif tier == "targeted":
        print(f"command: {compose_command(selected, touched, config, project_root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
