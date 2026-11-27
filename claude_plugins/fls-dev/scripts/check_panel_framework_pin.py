"""Check that the installed django-panel-framework is the commit uv.lock records.

usage: check_panel_framework_pin.py [--lock uv.lock] [--direct-url direct_url.json]

A git install records its commit. An editable install records only a directory, so its
commit and cleanliness are read from that worktree. Exits 0 when the installed copy is the
locked commit with no uncommitted changes; otherwise prints both commits and the next step
and exits 1.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import subprocess
import sys
import tomllib
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

DISTRIBUTION = "django-panel-framework"


def locked_commit(lock_path: Path) -> str:
    """The commit uv.lock records for the framework: the part of its git source after '#'."""
    packages = tomllib.loads(lock_path.read_text(encoding="utf-8"))["package"]
    source = next(p["source"] for p in packages if p["name"] == DISTRIBUTION)
    return str(source["git"]).rpartition("#")[2]


def installed_direct_url() -> str:
    """The installed copy's PEP 610 record, as text."""
    text = importlib.metadata.distribution(DISTRIBUTION).read_text("direct_url.json")
    if text is None:
        raise SystemExit(
            f"{DISTRIBUTION} was not installed from a git URL or a directory"
        )
    return text


def _git(directory: Path, *args: str) -> str:
    result = subprocess.run(  # noqa: S603
        ["git", "-C", str(directory), *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def installed_state(direct_url: dict[str, object]) -> tuple[str, bool]:
    """(commit, has uncommitted changes) of the installed copy."""
    vcs_info = direct_url.get("vcs_info")
    if isinstance(vcs_info, dict):
        commit = vcs_info.get("commit_id")
        if isinstance(commit, str):
            return commit, False
    url = direct_url.get("url")
    if not isinstance(url, str):
        raise SystemExit("direct_url.json has no url")
    directory = Path(url2pathname(urlparse(url).path))
    head = _git(directory, "rev-parse", "HEAD")
    return head, bool(_git(directory, "status", "--porcelain"))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, default=Path("uv.lock"))
    parser.add_argument("--direct-url", type=Path, default=None)
    return parser


def main(argv: list[str]) -> int:
    args = _parser().parse_args(argv[1:])
    locked = locked_commit(args.lock)
    try:
        text = (
            args.direct_url.read_text() if args.direct_url else installed_direct_url()
        )
    except importlib.metadata.PackageNotFoundError:
        print(f"{DISTRIBUTION} is not installed")  # noqa: T201
        return 1
    commit, dirty = installed_state(json.loads(text))
    if commit == locked and not dirty:
        return 0
    print(f"installed: {commit}{' (uncommitted changes)' if dirty else ''}")  # noqa: T201
    print(f"locked:    {locked}")  # noqa: T201
    print(  # noqa: T201
        "Commit and tag in the package worktree, bump the pin in pyproject.toml, "
        "run `uv lock`, then re-run."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
