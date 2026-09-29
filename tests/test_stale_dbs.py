"""Tests for the pure stale-database classifier in `dev_db.stale_dbs`.

No database access: `classify` takes worktree stamps, database names and a parsed
`git worktree list --porcelain` output as plain data, so none of this needs Postgres or git.
"""

from __future__ import annotations

import json

import pytest

from dev_db.stale_dbs import Worktree, classify, parse_stamp, parse_worktree_list

REPO = "/home/dev/.git/worktrees/common"
WORKTREE = "/home/dev/lms/feature-x"


def _stamp(repo: str = REPO, worktree: str = WORKTREE) -> str:
    return json.dumps({"repo": repo, "worktree": worktree})


def test_stamped_database_whose_worktree_is_gone_is_stale() -> None:
    comments = {"db_feature_x": _stamp()}

    report = classify(comments, worktrees=[], repo=REPO)

    assert report.stale == ["db_feature_x"]


def test_stamped_database_whose_worktree_is_prunable_is_stale() -> None:
    comments = {"db_feature_x": _stamp()}
    worktrees = [Worktree(path=WORKTREE, branch="feature-x", prunable=True)]

    report = classify(comments, worktrees, repo=REPO)

    assert report.stale == ["db_feature_x"]


def test_stamped_database_whose_worktree_switched_branch_is_stale() -> None:
    comments = {"db_feature_x": _stamp()}
    worktrees = [Worktree(path=WORKTREE, branch="other-branch", prunable=False)]

    report = classify(comments, worktrees, repo=REPO)

    assert report.stale == ["db_feature_x"]


def test_stamped_database_whose_worktree_is_live_on_its_branch_is_kept() -> None:
    comments = {"db_feature_x": _stamp()}
    worktrees = [Worktree(path=WORKTREE, branch="feature-x", prunable=False)]

    report = classify(comments, worktrees, repo=REPO)

    assert report.stale == []


def test_stamped_database_whose_worktree_is_on_a_detached_head_is_kept() -> None:
    comments = {"db_feature_x": _stamp()}
    worktrees = [Worktree(path=WORKTREE, branch=None, prunable=False)]

    report = classify(comments, worktrees, repo=REPO)

    assert report.stale == []


def test_database_stamped_by_another_repository_is_kept() -> None:
    comments = {"db_feature_x": _stamp(repo="/other/repo/.git")}

    report = classify(comments, worktrees=[], repo=REPO)

    assert report.stale == []


def test_unstamped_database_is_kept_and_counted() -> None:
    comments = {"db_fcweb_x": ""}

    report = classify(comments, worktrees=[], repo=REPO)

    assert report.stale == []
    assert report.unstamped_count == 1


@pytest.mark.parametrize("name", ["test_db_feature_x", "test_db_feature_x_gw3"])
def test_test_database_follows_its_stale_parent(name: str) -> None:
    comments = {"db_feature_x": _stamp(), name: ""}

    report = classify(comments, worktrees=[], repo=REPO)

    assert name in report.stale


@pytest.mark.parametrize(
    "name", ["db", "test_db", "postgres", "template0", "template1"]
)
def test_non_per_branch_database_is_kept(name: str) -> None:
    comments = {name: ""}

    report = classify(comments, worktrees=[], repo=REPO)

    assert report.stale == []


def test_parse_worktree_list_reads_branch_detached_and_prunable_entries() -> None:
    porcelain = (
        "worktree /home/dev/lms/main\n"
        "HEAD aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n"
        "branch refs/heads/main\n"
        "\n"
        "worktree /home/dev/lms/rebase-in-progress\n"
        "HEAD bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n"
        "detached\n"
        "\n"
        "worktree /home/dev/lms/old-feature\n"
        "HEAD cccccccccccccccccccccccccccccccccccccccc\n"
        "branch refs/heads/old-feature\n"
        "prunable gitdir file points to non-existent location\n"
    )

    worktrees = parse_worktree_list(porcelain)

    assert worktrees == [
        Worktree(path="/home/dev/lms/main", branch="main", prunable=False),
        Worktree(path="/home/dev/lms/rebase-in-progress", branch=None, prunable=False),
        Worktree(path="/home/dev/lms/old-feature", branch="old-feature", prunable=True),
    ]


def test_parse_stamp_returns_none_for_non_json() -> None:
    assert parse_stamp("not json") is None


def test_parse_stamp_returns_none_when_repo_is_missing() -> None:
    assert parse_stamp(json.dumps({"worktree": WORKTREE})) is None
