"""Build real git repos in tests with dulwich, so no test runs a `git` binary."""

from __future__ import annotations

from pathlib import Path

import pytest
from dulwich import porcelain
from dulwich.index import IndexEntry
from dulwich.objects import S_IFGITLINK
from dulwich.repo import Repo

AUTHOR = b"Test Author <test@example.com>"

TOPIC_UUID = "10000000-0000-0000-0000-000000000001"


def init_repo(repo_dir: Path) -> None:
    repo_dir.mkdir(parents=True, exist_ok=True)
    porcelain.init(str(repo_dir)).close()


def commit_all(repo_dir: Path, message: str = "content") -> str:
    """Stage every file and commit. Returns the full commit sha.

    The author and committer are explicit so the commit never depends on the
    machine's git config.
    """
    porcelain.add(str(repo_dir), paths=[str(repo_dir)])
    sha = porcelain.commit(
        str(repo_dir), message=message.encode(), author=AUTHOR, committer=AUTHOR
    )
    return sha.decode("ascii")


@pytest.fixture
def committed_content_repo(tmp_path: Path) -> Path:
    """A repo holding one committed topic file that carries a uuid."""
    repo_dir = tmp_path / "content_repo"
    init_repo(repo_dir)
    (repo_dir / "topic.md").write_text(
        f"---\ncontent_type: TOPIC\ntitle: A Topic\nuuid: {TOPIC_UUID}\n---\n\nBody.\n"
    )
    commit_all(repo_dir)
    return repo_dir


def add_linked_worktree(repo_dir: Path, worktree_dir: Path) -> None:
    """Add a linked worktree of `repo_dir` at `worktree_dir`, on a new branch."""
    porcelain.worktree_add(
        str(repo_dir), str(worktree_dir), branch=b"linked", commit=None
    )


def detach_head(repo_dir: Path) -> str:
    """Point HEAD at the commit it names instead of a branch. Returns that sha."""
    with Repo(str(repo_dir)) as repo:
        sha = repo.head().decode("ascii")
    (repo_dir / ".git" / "HEAD").write_text(f"{sha}\n")
    return sha


def pack_all_refs(repo_dir: Path) -> None:
    """Move every loose ref into packed-refs and delete the loose files."""
    porcelain.pack_refs(str(repo_dir), all=True)


def add_committed_submodule(repo_dir: Path, name: str) -> None:
    """Commit a nested repo at `repo_dir / name` as a submodule of `repo_dir`.

    dulwich's add skips a nested repo, so the gitlink entry goes into the index by hand.
    """
    sub_dir = repo_dir / name
    init_repo(sub_dir)
    (sub_dir / "shared.png").write_bytes(b"not really a png")
    sub_sha = commit_all(sub_dir).encode("ascii")
    (repo_dir / ".gitmodules").write_text(
        f'[submodule "{name}"]\n\tpath = {name}\n\turl = ../{name}\n'
    )
    porcelain.add(str(repo_dir), paths=[str(repo_dir / ".gitmodules")])
    with Repo(str(repo_dir)) as repo:
        index = repo.open_index()
        index[name.encode()] = IndexEntry(
            ctime=0,
            mtime=0,
            dev=0,
            ino=0,
            mode=S_IFGITLINK,
            uid=0,
            gid=0,
            size=0,
            sha=sub_sha,
        )
        index.write()
    porcelain.commit(
        str(repo_dir), message=b"submodule", author=AUTHOR, committer=AUTHOR
    )
