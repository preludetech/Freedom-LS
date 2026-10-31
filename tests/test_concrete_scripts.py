"""Tests for the wrapper scripts `/fls-dev:update_concrete_projects` runs against a concrete project.

No database is needed: every case builds a bare FLS origin, a concrete project that vendors it as
`submodules/Freedom-LS`, and an FLS config listing that project, all under `tmp_path`. `uv` and
`npm` are stubs on `PATH` that log their arguments.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

pytestmark = pytest.mark.dev_tooling

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "claude_plugins" / "fls-dev" / "scripts"
POINTER_MOVE = SCRIPTS / "concrete_pointer_move.sh"
ROLLBACK = SCRIPTS / "concrete_rollback.sh"

GIT_ENV_OVERRIDES = {
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_NOSYSTEM": "1",
    # A submodule cloned from a local path needs the file protocol.
    "GIT_CONFIG_COUNT": "1",
    "GIT_CONFIG_KEY_0": "protocol.file.allow",
    "GIT_CONFIG_VALUE_0": "always",
    "GIT_AUTHOR_NAME": "Concrete Test",
    "GIT_AUTHOR_EMAIL": "concrete-test@example.com",
    "GIT_COMMITTER_NAME": "Concrete Test",
    "GIT_COMMITTER_EMAIL": "concrete-test@example.com",
}

STUB = '#!/bin/bash\necho "$(basename "$0") $*" >> "$STUB_LOG"\n'


def _git(args: list[str], cwd: Path, env: dict[str, str]) -> str:
    return subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _commit(path: Path, env: dict[str, str], name: str) -> str:
    (path / name).write_text(f"{name}\n")
    _git(["add", "-A"], path, env)
    _git(["commit", "-q", "-m", name], path, env)
    return _git(["rev-parse", "HEAD"], path, env)


@dataclass
class Layout:
    env: dict[str, str]
    fls_home: Path
    project: Path
    on_main: list[str]
    off_main: str
    stub_log: Path

    @property
    def submodule(self) -> Path:
        return self.project / "submodules" / "Freedom-LS"

    def run(self, script: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603
            [str(script), *args],
            cwd=self.fls_home,
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
        )

    def write_config(self, name: str, *paths: Path, section: bool = True) -> None:
        lines = ["# FLS dev config", ""]
        if section:
            lines += ["## Concrete Projects", "", *[f"- {p}" for p in paths], ""]
        lines += ["## QA Dev Data", "", "- Content reset:", ""]
        (self.fls_home / ".claude" / "fls-dev" / name).write_text("\n".join(lines))

    def git(self, *args: str) -> str:
        return _git(list(args), self.project, self.env)

    def stub_calls(self) -> list[str]:
        if not self.stub_log.exists():
            return []
        return self.stub_log.read_text().splitlines()


@pytest.fixture
def layout(tmp_path: Path) -> Layout:
    stub_bin = tmp_path / "bin"
    stub_bin.mkdir()
    for tool in ("uv", "npm"):
        stub = stub_bin / tool
        stub.write_text(STUB)
        stub.chmod(0o755)
    stub_log = tmp_path / "stub.log"
    env = {
        **os.environ,
        **GIT_ENV_OVERRIDES,
        "HOME": str(tmp_path),
        "PATH": f"{stub_bin}{os.pathsep}{os.environ['PATH']}",
        "STUB_LOG": str(stub_log),
    }

    origin = tmp_path / "fls.git"
    _git(["init", "-q", "--bare", "-b", "main", str(origin)], tmp_path, env)
    work = tmp_path / "fls-work"
    _git(["clone", "-q", str(origin), str(work)], tmp_path, env)
    _git(["checkout", "-q", "-b", "main"], work, env)
    on_main = [_commit(work, env, "first.txt"), _commit(work, env, "second.txt")]
    _git(["push", "-q", "origin", "main"], work, env)
    _git(["checkout", "-q", "-b", "side"], work, env)
    off_main = _commit(work, env, "side.txt")
    _git(["push", "-q", "origin", "side"], work, env)

    project = tmp_path / "project"
    _git(["init", "-q", "-b", "main", str(project)], tmp_path, env)
    _git(["submodule", "add", "-q", str(origin), "submodules/Freedom-LS"], project, env)
    _git(["-C", "submodules/Freedom-LS", "checkout", "-q", on_main[0]], project, env)
    (project / "package.json").write_text("{}\n")
    _git(["add", "-A"], project, env)
    _git(["commit", "-q", "-m", "base"], project, env)

    fls_home = tmp_path / "fls-home"
    (fls_home / ".claude" / "fls-dev").mkdir(parents=True)
    env["CLAUDE_PROJECT_DIR"] = str(fls_home)

    result = Layout(
        env=env,
        fls_home=fls_home,
        project=project,
        on_main=on_main,
        off_main=off_main,
        stub_log=stub_log,
    )
    result.write_config("config.local.md", project)
    return result


def test_pointer_move_checks_out_a_commit_on_origin_main(layout: Layout) -> None:
    # Act
    result = layout.run(POINTER_MOVE, [str(layout.project), layout.on_main[1]])

    # Assert
    assert result.returncode == 0, result.stdout + result.stderr
    assert (
        _git(["rev-parse", "HEAD"], layout.submodule, layout.env) == (layout.on_main[1])
    )
    assert f"{layout.on_main[0]} -> {layout.on_main[1]}" in result.stdout


def test_pointer_move_accepts_origin_main(layout: Layout) -> None:
    # Act
    result = layout.run(POINTER_MOVE, [str(layout.project), "origin/main"])

    # Assert
    assert result.returncode == 0, result.stdout + result.stderr
    assert (
        _git(["rev-parse", "HEAD"], layout.submodule, layout.env) == (layout.on_main[1])
    )


def test_pointer_move_refuses_a_commit_off_origin_main(layout: Layout) -> None:
    # Act
    result = layout.run(POINTER_MOVE, [str(layout.project), layout.off_main])

    # Assert
    assert result.returncode != 0
    assert "not on FLS origin/main" in result.stderr
    assert (
        _git(["rev-parse", "HEAD"], layout.submodule, layout.env) == (layout.on_main[0])
    )


@pytest.mark.parametrize("target", ["main", "--upload-pack=touch", "HEAD~1", "abc"])
def test_pointer_move_refuses_a_target_that_is_not_a_sha(
    layout: Layout, target: str
) -> None:
    # Act
    result = layout.run(POINTER_MOVE, [str(layout.project), target])

    # Assert
    assert result.returncode != 0
    assert "must be a hex SHA or origin/main" in result.stderr


def test_pointer_move_refuses_an_unlisted_project(layout: Layout) -> None:
    # Arrange
    layout.write_config("config.local.md", layout.fls_home)

    # Act
    result = layout.run(POINTER_MOVE, [str(layout.project), layout.on_main[1]])

    # Assert
    assert result.returncode != 0
    assert "not a listed concrete project" in result.stderr


def test_shared_config_lists_the_project_when_local_has_no_section(
    layout: Layout,
) -> None:
    # Arrange
    layout.write_config("config.local.md", section=False)
    layout.write_config("config.md", layout.project)

    # Act
    result = layout.run(POINTER_MOVE, [str(layout.project), layout.on_main[1]])

    # Assert
    assert result.returncode == 0, result.stdout + result.stderr


def test_local_section_replaces_the_shared_one(layout: Layout) -> None:
    # Arrange
    layout.write_config("config.local.md", layout.fls_home)
    layout.write_config("config.md", layout.project)

    # Act
    result = layout.run(POINTER_MOVE, [str(layout.project), layout.on_main[1]])

    # Assert
    assert result.returncode != 0
    assert "not a listed concrete project" in result.stderr


def test_rollback_restores_the_tree_and_removes_untracked_files(
    layout: Layout,
) -> None:
    # Arrange
    last_good = layout.git("rev-parse", "HEAD")
    _git(["checkout", "-q", layout.on_main[1]], layout.submodule, layout.env)
    (layout.project / "first.txt").write_text("edited\n")
    (layout.project / "new" / "deep").mkdir(parents=True)
    (layout.project / "new" / "deep" / "file.txt").write_text("left behind\n")
    (layout.project / "top.txt").write_text("left behind\n")

    # Act
    result = layout.run(ROLLBACK, [str(layout.project), last_good])

    # Assert
    assert result.returncode == 0, result.stdout + result.stderr
    assert layout.git("status", "--porcelain", "--untracked-files=all") == ""
    assert not (layout.project / "new").exists()
    assert layout.project.is_dir()
    assert (
        _git(["rev-parse", "HEAD"], layout.submodule, layout.env) == (layout.on_main[0])
    )
    assert layout.stub_calls() == [f"uv sync --directory {layout.project}"]


def test_rollback_reinstalls_npm_when_package_files_changed(layout: Layout) -> None:
    # Arrange
    last_good = layout.git("rev-parse", "HEAD")
    (layout.project / "package.json").write_text('{"dependencies": {"x": "1"}}\n')

    # Act
    result = layout.run(ROLLBACK, [str(layout.project), last_good])

    # Assert
    assert result.returncode == 0, result.stdout + result.stderr
    assert (layout.project / "package.json").read_text() == "{}\n"
    assert f"npm --prefix {layout.project} install" in layout.stub_calls()


def test_rollback_refuses_a_commit_that_is_not_an_ancestor(layout: Layout) -> None:
    # Arrange
    base = layout.git("rev-parse", "HEAD")
    layout.git("checkout", "-q", "-b", "other")
    other = _commit(layout.project, layout.env, "other.txt")
    layout.git("checkout", "-q", "main")
    (layout.project / "top.txt").write_text("left behind\n")

    # Act
    result = layout.run(ROLLBACK, [str(layout.project), other])

    # Assert
    assert result.returncode != 0
    assert "not HEAD or an ancestor of HEAD" in result.stderr
    assert layout.git("rev-parse", "HEAD") == base
    assert (layout.project / "top.txt").exists()


def test_rollback_refuses_an_unlisted_project(layout: Layout) -> None:
    # Arrange
    last_good = layout.git("rev-parse", "HEAD")
    layout.write_config("config.local.md", layout.fls_home)
    (layout.project / "top.txt").write_text("left behind\n")

    # Act
    result = layout.run(ROLLBACK, [str(layout.project), last_good])

    # Assert
    assert result.returncode != 0
    assert "not a listed concrete project" in result.stderr
    assert (layout.project / "top.txt").exists()
