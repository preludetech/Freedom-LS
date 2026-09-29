"""Lists and drops this repository's per-branch databases whose worktree is gone.

Only a worktree stamp can tell one of this repository's per-branch databases apart from a
downstream project's, since name prefixes alone can't: `db_fcweb_x` follows the same
convention. `classify` is the pure part -- it takes stamps, database names and a parsed
`git worktree list --porcelain` and decides which names are stale, with no I/O of its own.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass

from dev_db import server
from freedom_ls.base.git_utils import branch_to_db_name

_GW_SUFFIX = re.compile(r"_gw\d+$")


@dataclass(frozen=True)
class WorktreeStamp:
    repo: str
    worktree: str


@dataclass(frozen=True)
class Worktree:
    path: str
    branch: str | None  # None on a detached HEAD
    prunable: bool


@dataclass(frozen=True)
class StaleReport:
    stale: list[str]
    unstamped_count: int


def parse_stamp(comment: str) -> WorktreeStamp | None:
    try:
        data = json.loads(comment)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    repo = data.get("repo")
    worktree = data.get("worktree")
    if not isinstance(repo, str) or not isinstance(worktree, str):
        return None
    return WorktreeStamp(repo=repo, worktree=worktree)


def parse_worktree_list(porcelain: str) -> list[Worktree]:
    worktrees: list[Worktree] = []
    path: str | None = None
    branch: str | None = None
    prunable = False

    def flush() -> None:
        if path is not None:
            worktrees.append(Worktree(path=path, branch=branch, prunable=prunable))

    for line in porcelain.splitlines():
        if not line:
            flush()
            path, branch, prunable = None, None, False
            continue
        if line.startswith("worktree "):
            path = line.removeprefix("worktree ")
        elif line.startswith("branch refs/heads/"):
            branch = line.removeprefix("branch refs/heads/")
        elif line.startswith("prunable"):
            prunable = True
    flush()
    return worktrees


def _test_db_parent(name: str) -> str | None:
    """Return the `db_<branch>` name a `test_db_<branch>` / `test_db_<branch>_gwN` follows."""
    if not name.startswith("test_"):
        return None
    candidate = _GW_SUFFIX.sub("", name.removeprefix("test_"))
    return candidate if candidate.startswith("db_") else None


def _is_stale(
    stamp: WorktreeStamp, name: str, worktrees_by_path: dict[str, Worktree]
) -> bool:
    worktree = worktrees_by_path.get(stamp.worktree)
    if worktree is None or worktree.prunable:
        return True
    if worktree.branch is None:
        return False
    return branch_to_db_name(worktree.branch) != name


def classify(
    comments: dict[str, str], worktrees: list[Worktree], repo: str
) -> StaleReport:
    """Classify every `db_*`/`test_db_*` name in `comments` as stale, kept or unstamped.

    `comments` maps every database name known to the server to its `COMMENT ON DATABASE`
    text (empty when there is none).
    """
    worktrees_by_path = {worktree.path: worktree for worktree in worktrees}

    stamps: dict[str, WorktreeStamp | None] = {}
    stale_parents: set[str] = set()
    unstamped_count = 0

    for name, comment in comments.items():
        if not name.startswith("db_"):
            continue
        stamp = parse_stamp(comment)
        stamps[name] = stamp
        if stamp is None:
            unstamped_count += 1
        elif stamp.repo == repo and _is_stale(stamp, name, worktrees_by_path):
            stale_parents.add(name)

    stale = sorted(stale_parents)
    for name in comments:
        parent = _test_db_parent(name)
        if parent is None:
            continue
        if parent in stale_parents:
            stale.append(name)
        elif stamps.get(parent) is None:
            unstamped_count += 1

    return StaleReport(stale=stale, unstamped_count=unstamped_count)


def fetch_databases() -> tuple[dict[str, str], dict[str, str]]:
    """Return (comments by database name, pretty sizes by database name)."""
    rows = server.psql(
        "SELECT datname, pg_size_pretty(pg_database_size(oid)), "
        "coalesce(shobj_description(oid, 'pg_database'), '') "
        "FROM pg_database WHERE NOT datistemplate"
    )
    comments = {row[0]: row[2] for row in rows}
    sizes = {row[0]: row[1] for row in rows}
    return comments, sizes


def current_repo() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def current_worktrees() -> list[Worktree]:
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    )
    return parse_worktree_list(result.stdout)


def find_stale() -> tuple[StaleReport, dict[str, str]]:
    comments, sizes = fetch_databases()
    report = classify(comments, current_worktrees(), current_repo())
    return report, sizes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="List, or with --drop remove, this repository's stale per-branch databases."
    )
    parser.add_argument(
        "--drop",
        action="store_true",
        help="Drop the stale databases instead of listing them.",
    )
    args = parser.parse_args(argv)

    try:
        report, sizes = find_stale()
    except server.ServerUnavailable as exc:
        print(exc, file=sys.stderr)
        return 1

    if args.drop:
        for name in report.stale:
            server.psql(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
            print(f"Dropped {name}")
        return 0

    for name in report.stale:
        print(f"{name}  {sizes.get(name, '')}")
    print(f"{report.unstamped_count} unstamped db_*/test_db_* databases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
