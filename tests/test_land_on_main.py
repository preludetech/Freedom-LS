"""Tests for the script `/sdd:finish_worktree` uses to land a finished branch on main.

This test assumes `claude_plugins/` sits at the project root, so the script it exercises is
`claude_plugins/sdd/scripts/land_on_main.sh`. No database is needed: every case builds its own
bare origin, a main checkout and a feature worktree by hand under `tmp_path`, then runs the script
from the feature worktree the way the command does.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "claude_plugins" / "sdd" / "scripts" / "land_on_main.sh"

GIT_ENV_OVERRIDES = {
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Landing Test",
    "GIT_AUTHOR_EMAIL": "landing-test@example.com",
    "GIT_COMMITTER_NAME": "Landing Test",
    "GIT_COMMITTER_EMAIL": "landing-test@example.com",
}


def _run_git(
    args: list[str], cwd: Path, env: dict[str, str], check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=check,
    )


def _run_script(
    args: list[str], cwd: Path, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [str(SCRIPT), *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@dataclass
class Checkout:
    path: Path
    env: dict[str, str]

    def write_text(self, relative_path: str, content: str) -> None:
        target = self.path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    def commit(self, message: str) -> str:
        _run_git(["add", "-A"], self.path, self.env)
        _run_git(["commit", "-q", "-m", message], self.path, self.env)
        return self.rev_parse("HEAD")

    def rev_parse(self, ref: str) -> str:
        return _run_git(["rev-parse", ref], self.path, self.env).stdout.strip()

    def status(self) -> str:
        return _run_git(["status", "--porcelain"], self.path, self.env).stdout

    def push(self, refspec: str) -> None:
        _run_git(["push", "-q", "origin", refspec], self.path, self.env)


@dataclass
class Layout:
    """A bare origin, a checkout on `main` and a linked worktree on `feature`."""

    origin: Path
    main: Checkout
    feature: Checkout

    def origin_main(self) -> str:
        return _run_git(
            ["rev-parse", "refs/heads/main"], self.origin, self.main.env
        ).stdout.strip()


@pytest.fixture
def env(tmp_path: Path) -> dict[str, str]:
    return {**os.environ, **GIT_ENV_OVERRIDES, "HOME": str(tmp_path)}


@pytest.fixture
def layout(tmp_path: Path, env: dict[str, str]) -> Layout:
    origin = tmp_path / "origin.git"
    _run_git(["init", "-q", "--bare", "-b", "main", str(origin)], tmp_path, env)
    main_path = tmp_path / "main"
    _run_git(["init", "-q", "-b", "main", str(main_path)], tmp_path, env)
    main = Checkout(path=main_path, env=env)
    main.write_text("README.md", "base\n")
    main.commit("base")
    _run_git(["remote", "add", "origin", str(origin)], main_path, env)
    _run_git(["push", "-q", "-u", "origin", "main"], main_path, env)
    feature_path = tmp_path / "feature"
    _run_git(
        ["worktree", "add", "-q", "-b", "feature", str(feature_path)], main_path, env
    )
    return Layout(
        origin=origin, main=main, feature=Checkout(path=feature_path, env=env)
    )


@pytest.fixture
def layout_without_main(tmp_path: Path, env: dict[str, str]) -> Layout:
    """A single checkout on `feature` whose origin already has `main`, but no local `main`."""
    origin = tmp_path / "origin.git"
    _run_git(["init", "-q", "--bare", "-b", "main", str(origin)], tmp_path, env)
    feature_path = tmp_path / "feature"
    _run_git(["init", "-q", "-b", "feature", str(feature_path)], tmp_path, env)
    feature = Checkout(path=feature_path, env=env)
    feature.write_text("README.md", "base\n")
    feature.commit("base")
    _run_git(["remote", "add", "origin", str(origin)], feature_path, env)
    feature.push("HEAD:refs/heads/main")
    _run_git(["fetch", "-q", "origin"], feature_path, env)
    return Layout(origin=origin, main=feature, feature=feature)


def add_feature_commit(layout: Layout, name: str = "feature.txt") -> str:
    layout.feature.write_text(name, f"{name}\n")
    return layout.feature.commit(f"feature: add {name}")


def add_main_commit(layout: Layout, name: str = "main.txt") -> str:
    layout.main.write_text(name, f"{name}\n")
    return layout.main.commit(f"main: add {name}")


def test_sync_on_clean_layout_reports_main_worktree(layout: Layout) -> None:
    # Act
    result = _run_script(["sync"], layout.feature.path, layout.feature.env)

    # Assert
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"main-worktree: {layout.main.path}" in result.stdout


def test_sync_blocks_on_tracked_change_in_main_worktree(layout: Layout) -> None:
    # Arrange
    layout.main.write_text("README.md", "edited but not committed\n")

    # Act
    result = _run_script(["sync"], layout.feature.path, layout.feature.env)

    # Assert
    assert result.returncode == 3
    assert "parked:  M README.md" in result.stdout
    assert (layout.main.path / "README.md").read_text() == "edited but not committed\n"


def test_sync_ignores_untracked_files_in_main_worktree(layout: Layout) -> None:
    # Arrange
    layout.main.write_text("notes.md", "scratch\n")

    # Act
    result = _run_script(["sync"], layout.feature.path, layout.feature.env)

    # Assert
    assert result.returncode == 0, result.stdout + result.stderr
    assert "untracked: 1 file(s) on main, left alone" in result.stdout
    assert (layout.main.path / "notes.md").exists()


def test_sync_blocks_on_merge_in_progress_and_leaves_it_alone(layout: Layout) -> None:
    # Arrange
    layout.feature.write_text("conflict.txt", "feature side\n")
    layout.feature.commit("feature side")
    layout.main.write_text("conflict.txt", "main side\n")
    layout.main.commit("main side")
    merge = _run_git(
        ["merge", "feature"], layout.main.path, layout.main.env, check=False
    )
    assert merge.returncode != 0
    merge_head = layout.main.rev_parse("MERGE_HEAD")

    # Act
    result = _run_script(["sync"], layout.feature.path, layout.feature.env)

    # Assert
    assert result.returncode == 3
    assert f"parked: merge in progress (MERGE_HEAD {merge_head})" in result.stdout
    assert layout.main.rev_parse("MERGE_HEAD") == merge_head


def test_sync_pushes_main_when_it_is_ahead_of_origin(layout: Layout) -> None:
    # Arrange
    local_tip = add_main_commit(layout)

    # Act
    result = _run_script(["sync"], layout.feature.path, layout.feature.env)

    # Assert
    assert result.returncode == 0, result.stdout + result.stderr
    assert layout.origin_main() == local_tip
    assert "synced: pushed 1 local commit(s) on main to origin" in result.stdout


def test_sync_fast_forwards_main_when_it_is_behind_origin(layout: Layout) -> None:
    # Arrange
    pushed_tip = add_feature_commit(layout)
    layout.feature.push("HEAD:refs/heads/main")

    # Act
    result = _run_script(["sync"], layout.feature.path, layout.feature.env)

    # Assert
    assert result.returncode == 0, result.stdout + result.stderr
    assert layout.main.rev_parse("HEAD") == pushed_tip
    assert layout.main.status() == ""


def test_sync_blocks_when_main_has_diverged_from_origin(layout: Layout) -> None:
    # Arrange
    local_tip = add_main_commit(layout)
    remote_tip = add_feature_commit(layout)
    layout.feature.push("HEAD:refs/heads/main")

    # Act
    result = _run_script(["sync"], layout.feature.path, layout.feature.env)

    # Assert
    assert result.returncode == 3
    assert "parked: main has diverged from origin/main" in result.stdout
    assert layout.main.rev_parse("HEAD") == local_tip
    assert layout.origin_main() == remote_tip


def test_land_fast_forwards_origin_and_main_worktree(layout: Layout) -> None:
    # Arrange
    tip = add_feature_commit(layout)

    # Act
    result = _run_script(["land"], layout.feature.path, layout.feature.env)

    # Assert
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"landed: {tip}" in result.stdout
    assert layout.origin_main() == tip
    assert layout.main.rev_parse("HEAD") == tip
    assert layout.main.status() == ""


def test_land_refuses_when_branch_is_behind_origin(layout: Layout) -> None:
    # Arrange
    main_tip = add_main_commit(layout)
    layout.main.push("main")
    add_feature_commit(layout)

    # Act
    result = _run_script(["land"], layout.feature.path, layout.feature.env)

    # Assert
    assert result.returncode == 7
    assert "behind: feature is behind origin/main" in result.stdout
    assert layout.origin_main() == main_tip


def test_land_again_has_nothing_to_land(layout: Layout) -> None:
    # Arrange
    tip = add_feature_commit(layout)
    first = _run_script(["land"], layout.feature.path, layout.feature.env)
    assert first.returncode == 0, first.stdout + first.stderr

    # Act
    result = _run_script(["land"], layout.feature.path, layout.feature.env)

    # Assert
    assert result.returncode == 0, result.stdout + result.stderr
    assert "landed: nothing to land" in result.stdout
    assert layout.origin_main() == tip


def test_land_leaves_main_alone_when_origin_rejects_the_push(layout: Layout) -> None:
    # Arrange
    base = layout.main.rev_parse("HEAD")
    add_feature_commit(layout)
    hook = layout.origin / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\necho 'main is protected' >&2\nexit 1\n")
    hook.chmod(0o755)

    # Act
    result = _run_script(["land"], layout.feature.path, layout.feature.env)

    # Assert
    assert result.returncode == 6
    assert "rejected: origin refused the fast-forward of main" in result.stdout
    assert layout.origin_main() == base
    assert layout.main.rev_parse("HEAD") == base


def test_land_without_a_main_worktree_still_updates_origin(
    layout_without_main: Layout,
) -> None:
    # Arrange
    tip = add_feature_commit(layout_without_main)

    # Act
    result = _run_script(
        ["land"], layout_without_main.feature.path, layout_without_main.feature.env
    )

    # Assert
    assert result.returncode == 0, result.stdout + result.stderr
    assert "main-worktree: none" in result.stdout
    assert layout_without_main.origin_main() == tip


def test_run_from_main_is_a_usage_error(layout: Layout) -> None:
    # Act
    result = _run_script(["land"], layout.main.path, layout.main.env)

    # Assert
    assert result.returncode == 64
    assert "run this from a feature branch" in result.stdout
    assert layout.main.status() == ""


def test_unknown_verb_is_a_usage_error(layout: Layout) -> None:
    # Act
    result = _run_script(["merge"], layout.feature.path, layout.feature.env)

    # Assert
    assert result.returncode == 64


def test_missing_origin_is_a_usage_error(layout: Layout) -> None:
    # Arrange
    _run_git(["remote", "remove", "origin"], layout.main.path, layout.main.env)

    # Act
    result = _run_script(["sync"], layout.feature.path, layout.feature.env)

    # Assert
    assert result.returncode == 64
    assert "no origin remote" in result.stdout
