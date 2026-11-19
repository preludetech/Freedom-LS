#!/usr/bin/env python3
"""Record the commit a passing full test run covered, and pick the tier for the next checkpoint.

Verbs:
    read                          print the recorded commit SHA, or nothing
    resolve [--selector CMD]      print the `tier:`, `diff:` and `why:` lines for a checkpoint
    start                         print `sha: <HEAD>` before a full run, or `sha:` on a dirty tree
    write --verdict VERDICT --sha SHA
                                  record SHA, the commit `start` printed, after a passing full run

A full run takes minutes and other processes commit to the same worktree meanwhile, so the record
names the commit the run started on. `write` records nothing when HEAD moved or the tree changed
during the run.

The record is one file per branch under `.sdd-work/`. A checkpoint compares HEAD with the
recorded commit through the project's tier selector, so a branch that has not changed anything a
test can see since its last green full run runs nothing, and a small change runs a targeted tier.
A missing, unreadable or stale record always resolves to a full run.

Stdlib only. Every verb exits 0; a usage error exits 64.
"""

from __future__ import annotations

import argparse
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, NoReturn
from urllib.parse import quote

RECORD_DIR = ".sdd-work"
FULL_SHA = re.compile(r"[0-9a-f]{40}")
EXIT_USAGE = 64

Tier = Literal["none", "targeted", "full"]
Verdict = Literal["pass", "fail", "incomplete"]
TIERS: tuple[Tier, ...] = ("none", "targeted", "full")


class UsageParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        sys.stderr.write(f"{self.prog}: error: {message}\n")
        sys.exit(EXIT_USAGE)


def git(project_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )


def current_branch(project_root: Path) -> str | None:
    """The checked-out branch, or None when HEAD is detached."""
    result = git(project_root, "symbolic-ref", "--quiet", "--short", "HEAD")
    branch = result.stdout.strip()
    return branch if result.returncode == 0 and branch else None


def record_path(project_root: Path, branch: str) -> Path:
    # Percent-encoding keeps "/" out of the file name without letting two branch names
    # ("a/b" and "a_b") share one record.
    return project_root / RECORD_DIR / f"full_run_record_{quote(branch, safe='')}.txt"


def read(project_root: Path) -> str | None:
    """The recorded commit SHA.

    None when HEAD is detached, when there is no record, or when the file holds anything but
    one full-length SHA: the value reaches git and the selector as an argument, so nothing
    else is let through.
    """
    branch = current_branch(project_root)
    if branch is None:
        return None
    try:
        text = record_path(project_root, branch).read_text(encoding="utf-8").strip()
    except (FileNotFoundError, UnicodeDecodeError):
        return None
    return text if FULL_SHA.fullmatch(text) else None


def commit_exists(project_root: Path, sha: str) -> bool:
    return (
        git(
            project_root, "rev-parse", "--verify", "--quiet", f"{sha}^{{commit}}"
        ).returncode
        == 0
    )


@dataclass(frozen=True)
class Resolution:
    tier: Tier
    diff: str  # the selector's diff arguments for a targeted run, else ""
    why: str


def selected_tier(project_root: Path, selector: list[str], *diff: str) -> Tier:
    """The tier the selector prints for a diff.

    A selector that fails, or prints no tier line, counts as full: an unknown change is never
    skipped.
    """
    try:
        result = subprocess.run(  # noqa: S603
            [*selector, *diff],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return "full"
    if result.returncode != 0:
        return "full"
    for line in result.stdout.splitlines():
        if line.startswith("tier:"):
            value = line.removeprefix("tier:").strip()
            return next((tier for tier in TIERS if tier == value), "full")
    return "full"


def resolve(project_root: Path, selector: list[str] | None) -> Resolution:
    if selector is None:
        return Resolution("full", "", "no tier selector")
    # --working-tree adds uncommitted edits, which a range alone would leave out of a "nothing
    # changed" answer.
    branch_diff = ("--range", "origin/main..HEAD", "--working-tree")
    if selected_tier(project_root, selector, *branch_diff) == "none":
        return Resolution("none", "", "the branch holds no test-visible change")
    sha = read(project_root)
    if sha is None:
        return Resolution("full", "", "no full-run record")
    if not commit_exists(project_root, sha):
        return Resolution("full", "", f"recorded commit {sha[:7]} no longer resolves")
    # `git diff A..HEAD` compares two trees, so the range still works after a rebase moved
    # the recorded commit off the branch.
    diff = ("--range", f"{sha}..HEAD", "--working-tree")
    tier = selected_tier(project_root, selector, *diff)
    if tier == "none":
        return Resolution(
            "none", "", f"no test-visible change since full green at {sha[:7]}"
        )
    if tier == "targeted":
        return Resolution("targeted", " ".join(diff), f"range {sha[:7]}..HEAD")
    return Resolution("full", "", f"the selector escalates over {sha[:7]}..HEAD")


def tracked_tree_is_clean(project_root: Path) -> bool:
    # Untracked files do not count: a stray one would otherwise force a full run at every
    # checkpoint.
    status = git(project_root, "status", "--porcelain", "--untracked-files=no")
    return not status.stdout.strip()


def head(project_root: Path) -> str:
    return git(project_root, "rev-parse", "HEAD").stdout.strip()


def start(project_root: Path) -> str:
    """The commit a full run is about to test, or "" when the tracked tree is dirty."""
    return head(project_root) if tracked_tree_is_clean(project_root) else ""


def write(project_root: Path, verdict: Verdict, sha: str) -> str:
    """Record `sha`, the commit `start` printed before a passing full run.

    Nothing is recorded unless HEAD is still that commit and the tree is still clean, so the
    record never names a commit the run did not test. Returns what happened.
    """
    if verdict != "pass":
        return f"not recorded: verdict {verdict}"
    branch = current_branch(project_root)
    if branch is None:
        return "not recorded: HEAD is detached"
    if not sha:
        return "not recorded: the run started on a dirty tree"
    if not FULL_SHA.fullmatch(sha):
        return "not recorded: --sha is not a full commit SHA"
    if head(project_root) != sha:
        return "not recorded: HEAD moved during the run"
    if not tracked_tree_is_clean(project_root):
        return "not recorded: working tree not clean"
    path = record_path(project_root, branch)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{sha}\n", encoding="utf-8")
    return f"recorded: {sha}"


def parse_selector(
    parser: argparse.ArgumentParser, project_root: Path, value: str
) -> list[str]:
    """The selector command split into words, its first word made an absolute path.

    The first word must be a file under the project root, so the argument cannot name an
    arbitrary program.
    """
    try:
        words = shlex.split(value)
    except ValueError as exc:
        parser.error(f"--selector is not a valid command: {exc}")
    if not words:
        parser.error("--selector is empty")
    root = project_root.resolve()
    executable = (root / words[0]).resolve()
    if not executable.is_relative_to(root) or not executable.is_file():
        parser.error(f"--selector must start with a file under {root}: {words[0]}")
    return [str(executable), *words[1:]]


def build_parser() -> argparse.ArgumentParser:
    parser = UsageParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    verbs = parser.add_subparsers(dest="verb", required=True)
    verbs.add_parser("read")
    verbs.add_parser("start")
    resolve_parser = verbs.add_parser("resolve")
    resolve_parser.add_argument("--selector")
    write_parser = verbs.add_parser("write")
    write_parser.add_argument(
        "--verdict", required=True, choices=["pass", "fail", "incomplete"]
    )
    write_parser.add_argument("--sha", required=True)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    project_root: Path = args.project_root
    if args.verb == "read":
        sha = read(project_root)
        if sha is not None:
            sys.stdout.write(f"{sha}\n")
    elif args.verb == "resolve":
        selector = (
            None
            if args.selector is None
            else parse_selector(parser, project_root, args.selector)
        )
        resolution = resolve(project_root, selector)
        sys.stdout.write(
            f"tier: {resolution.tier}\ndiff: {resolution.diff}\nwhy: {resolution.why}\n"
        )
    elif args.verb == "start":
        sys.stdout.write(f"sha: {start(project_root)}".rstrip() + "\n")
    else:
        sys.stdout.write(f"{write(project_root, args.verdict, args.sha.strip())}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
