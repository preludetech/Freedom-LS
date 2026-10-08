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
from generate_app_map import App, find_apps

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


def glob_list(table: dict[str, object], key: str) -> tuple[str, ...]:
    value = table.get(key, [])
    if not isinstance(value, list) or not all(isinstance(g, str) for g in value):
        raise ConfigError(f"[tool.test_tiers] '{key}' must be a list of strings")
    return tuple(value)


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
        tooling=(),
    )


def first_match(path: str, globs: tuple[str, ...]) -> str | None:
    """The first glob that matches `path`, so the reason can name it."""
    posix = PurePosixPath(path)
    return next((glob for glob in globs if posix.full_match(glob)), None)


def decide(
    path: str, apps: list[App], config: TierConfig, project_root: Path
) -> Decision:
    """Apply the rules in order; the first one that matches `path` decides."""
    none_glob = first_match(path, config.none)
    if none_glob is not None:
        return Decision(path, "none", (), f"matches {none_glob}")

    posix = PurePosixPath(path)
    if is_collected(posix.name) and "tests" in posix.parts:
        if not (project_root / path).exists():
            return Decision(path, "none", (), "deleted test file")
        return Decision(path, "select", (path,), "changed test file")

    escalation_glob = first_match(path, config.escalation)
    if escalation_glob is not None:
        return Decision(path, "full", (), f"matches {escalation_glob}")

    app = owning_app(apps, project_root, path)
    if app is not None:
        tests_dir = (app.directory / "tests").relative_to(project_root).as_posix()
        if (project_root / tests_dir).is_dir():
            return Decision(
                path, "select", (tests_dir,), f"owning app {app.short_name}"
            )
        return Decision(
            path,
            "none",
            (),
            f"owning app {app.short_name} has no tests directory",
        )

    return Decision(path, "full", (), "unmapped path")


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
        if d.endswith("/tests")
        and d not in touched
        and (project_root / d / "playwright").is_dir()
    ]
    return " ".join(
        [TARGETED_PREFIX, *ignores, *(shlex.quote(p) for p in sorted(selected))]
    )


def minimal_selection(selects: set[str]) -> set[str]:
    """Drop every selected file whose containing directory is also selected."""
    directories = {s for s in selects if s.endswith("/tests")}
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
    decisions = [decide(p, apps, config, project_root) for p in paths]

    selected = minimal_selection({s for d in decisions for s in d.selects})
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
        print(f"command: {compose_command(selected, set(), project_root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
