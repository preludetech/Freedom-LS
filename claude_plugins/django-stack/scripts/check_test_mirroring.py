#!/usr/bin/env python3
# ruff: noqa: T201
"""Check that every collected app test file mirrors a production module.

Reads `[tool.test_organisation]` from `pyproject.toml` (see `generate_app_map.py`,
this script's sibling). With no table, there is nothing to check.

Usage:
    python check_test_mirroring.py [--print-violations]

Stdlib only; no third-party dependencies.
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from generate_app_map import (
    App,
    ConfigError,
    TestOrganisationConfig,
    find_apps,
    in_skipped_dir,
    iter_entries,
    load_config,
)

# pytest's default `python_files` patterns, the files pytest actually collects.
COLLECTED: tuple[str, ...] = ("test_*.py", "*_tests.py", "tests.py")

MIRRORING_DOC = 'See "Mirroring" in claude_plugins/django-stack/resources/testing.md.'
THREE_WAYS_OUT = (
    "rename or move the file so it mirrors its production module, add a reasoned "
    "line for it to mirroring_exemptions.txt, or delete the stale line from "
    "mirroring_baseline.txt"
)


@dataclass(frozen=True)
class Violation:
    path: str
    expected: str


def is_collected(name: str) -> bool:
    return any(fnmatch.fnmatch(name, pattern) for pattern in COLLECTED)


def mirrored_test_path(app: App, within: Path) -> Path:
    """Where a misnamed or misplaced test file should live, under `<app>/tests/`."""
    sub = within.parts[1:-1] if within.parts[0] == "tests" else within.parts[:-1]
    if within.name == "tests.py":
        return app.directory.joinpath("tests", *sub, "test_<module>.py")
    stem = within.stem.removesuffix("_tests").removeprefix("test_")
    return app.directory.joinpath("tests", *sub, f"test_{stem}.py")


def expected_module_path(app: App, within: Path) -> Path:
    """The production module `within` should mirror, whether or not it exists.

    Only a `<app>/tests/<sub...>/test_<name>.py` shape can be a colocated test of
    a real module; everything else (a misnamed file, or one outside `tests/`)
    names where the test itself belongs instead.
    """
    if within.parts[0] == "tests" and within.name.startswith("test_"):
        sub = within.parts[1:-1]
        name = within.stem.removeprefix("test_")
        return app.directory.joinpath(*sub, f"{name}.py")
    return mirrored_test_path(app, within)


def conforms(app: App, within: Path) -> bool:
    """Whether `<app>/tests/<sub...>/test_<name>.py` mirrors a real module or package."""
    sub = within.parts[1:-1]
    name = within.stem.removeprefix("test_")
    module = app.directory.joinpath(*sub, f"{name}.py")
    package_init = app.directory.joinpath(*sub, name, "__init__.py")
    return module.exists() or package_init.exists()


def find_violations(apps: list[App], project_root: Path) -> list[Violation]:
    violations: list[Violation] = []
    for app in apps:
        for path in app.directory.rglob("*.py"):
            if in_skipped_dir(path, app.directory):
                continue
            if not is_collected(path.name):
                continue
            within = path.relative_to(app.directory)
            if within.parts[:2] == ("tests", "playwright"):
                continue
            if (
                within.parts[0] == "tests"
                and path.name.startswith("test_")
                and conforms(app, within)
            ):
                continue
            expected = expected_module_path(app, within)
            violations.append(
                Violation(
                    path=path.relative_to(project_root).as_posix(),
                    expected=expected.relative_to(project_root).as_posix(),
                )
            )
    return violations


def owning_app(apps: list[App], project_root: Path, path: str) -> App | None:
    absolute = project_root / path
    for app in apps:
        try:
            absolute.relative_to(app.directory)
        except ValueError:
            continue
        return app
    return None


def render_baseline(apps: list[App], project_root: Path, paths: Iterable[str]) -> str:
    """Render `paths` in the shared `test_organisation/` baseline format.

    A `# <app>` header per owning app, apps and lines sorted, matching
    `import_baseline.txt`'s grouping so both files read the same way.
    """
    grouped: dict[str, list[str]] = {}
    for path in paths:
        app = owning_app(apps, project_root, path)
        key = app.short_name if app is not None else ""
        grouped.setdefault(key, []).append(path)
    blocks = [
        f"# {app_name}\n" + "\n".join(sorted(grouped[app_name]))
        for app_name in sorted(grouped)
    ]
    return "\n\n".join(blocks) + "\n" if blocks else ""


def read_baseline(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line for _, line in iter_entries(path)]


EXEMPTION_RE = re.compile(r"^(\S+)  # (\S.*)$")


def read_exemptions(path: Path) -> list[str]:
    """Repo-relative paths exempted from mirroring, from `mirroring_exemptions.txt`.

    A missing file means no exemptions, matching `read_baseline`'s tolerance for
    a project that names the file in its config before the file exists.
    """
    if not path.exists():
        return []
    exemptions: list[str] = []
    for line_no, line in iter_entries(path):
        match = EXEMPTION_RE.match(line)
        if not match:
            raise ConfigError(f"{line_no}: {line} has no reason")
        exemptions.append(match.group(1))
    return exemptions


def covers(exemption: str, path: str) -> bool:
    return path.startswith(exemption) if exemption.endswith("/") else path == exemption


def unbaselined_message(path: str, expected: str) -> str:
    return (
        f"{path} does not mirror {expected}. Fix it: {THREE_WAYS_OUT}. {MIRRORING_DOC}"
    )


def stale_baseline_message(path: str) -> str:
    return (
        f"{path} is a mirroring_baseline.txt line that no longer matches a "
        f"violation (the file is gone, now conforms, or sits under "
        f"tests/playwright/). Fix it: {THREE_WAYS_OUT}. {MIRRORING_DOC}"
    )


def stale_exemption_message(exemption: str) -> str:
    return (
        f"{exemption} is a mirroring_exemptions.txt line that covers no "
        f"violation (the file is gone or now conforms). Fix it: delete the "
        f"stale line. {MIRRORING_DOC}"
    )


def exempted_baseline_message(path: str) -> str:
    return (
        f"{path} is in both mirroring_baseline.txt and mirroring_exemptions.txt. "
        f"Fix it: delete the mirroring_baseline.txt line; the exemption already "
        f"covers it. {MIRRORING_DOC}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--print-violations",
        action="store_true",
        help=(
            "Print every current violation in baseline format and exit; writes nothing."
        ),
    )
    args = parser.parse_args()

    project_root = Path.cwd()
    try:
        config: TestOrganisationConfig | None = load_config(project_root)
    except ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if config is None:
        print("[tool.test_organisation] is not configured; nothing to check.")
        return 0

    apps = find_apps(project_root)
    violations = find_violations(apps, project_root)
    violation_paths = {v.path for v in violations}

    try:
        exemptions = read_exemptions(config.mirroring_exemptions)
    except ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    exempted_violations = {
        path for path in violation_paths if any(covers(e, path) for e in exemptions)
    }

    if args.print_violations:
        remaining = (v.path for v in violations if v.path not in exempted_violations)
        print(render_baseline(apps, project_root, remaining), end="")
        return 0

    baseline = read_baseline(config.mirroring_baseline)
    baseline_set = set(baseline)
    expected_by_path = {v.path: v.expected for v in violations}

    exempted_baseline = {
        path for path in baseline_set if any(covers(e, path) for e in exemptions)
    }
    stale_exemptions = [
        exemption
        for exemption in exemptions
        if not any(covers(exemption, path) for path in violation_paths)
    ]

    failures = (
        [
            unbaselined_message(path, expected_by_path[path])
            for path in sorted(violation_paths - exempted_violations - baseline_set)
        ]
        + [
            stale_baseline_message(path)
            for path in sorted(baseline_set - violation_paths - exempted_baseline)
        ]
        + [exempted_baseline_message(path) for path in sorted(exempted_baseline)]
        + [stale_exemption_message(exemption) for exemption in sorted(stale_exemptions)]
    )

    if failures:
        for message in failures:
            print(message, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
