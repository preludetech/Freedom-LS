"""Tests for the full-run record the checkpoint tier reads and writes.

This test assumes `claude_plugins/` sits at the project root, so the script it exercises is
`claude_plugins/sdd/scripts/full_run_record.py`. Every case builds a throwaway project with a
bare origin under `tmp_path`, holding a copy of the repository's own tier selector, and runs the
script as a subprocess from inside it.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import pytest

from tests._script_trees import run_command, run_script, write_tree
from tests.test_select_tests import alpha_app

pytestmark = pytest.mark.dev_tooling

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "claude_plugins" / "sdd" / "scripts" / "full_run_record.py"
SELECTOR_SOURCES = tuple(
    (REPO_ROOT / "claude_plugins" / "django-stack" / "scripts" / name)
    for name in ("select_tests.py", "check_test_mirroring.py", "generate_app_map.py")
)
SELECTOR = ".claude/ds/scripts/select_tests.sh"
TIER_CONFIG = '[tool.test_tiers]\nnone = ["spec_dd/**"]\n'

GIT_ENV_OVERRIDES = {
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Record Test",
    "GIT_AUTHOR_EMAIL": "record-test@example.com",
    "GIT_COMMITTER_NAME": "Record Test",
    "GIT_COMMITTER_EMAIL": "record-test@example.com",
}


@dataclass
class Project:
    path: Path
    git_env: dict[str, str]

    def git(self, *args: str, cwd: Path | None = None) -> str:
        result = run_command(["git", *args], cwd or self.path, self.git_env)
        assert result.returncode == 0, result.stderr
        return result.stdout.strip()

    def write(self, relative_path: str, content: str) -> None:
        write_tree(self.path, {relative_path: content})

    def commit(self, message: str) -> str:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD")

    def record_file(self, branch: str) -> Path:
        return self.path / ".sdd-work" / f"full_run_record_{quote(branch, safe='')}.txt"

    def script(self, *args: str) -> str:
        result = run_script(SCRIPT, self.path, *args, environment=self.git_env)
        assert result.returncode == 0, result.stderr
        return result.stdout

    def resolve(self) -> dict[str, str]:
        return parse(self.script("resolve", "--selector", SELECTOR))

    def record_green(self) -> None:
        self.script("write", "--verdict", "pass")


def parse(output: str) -> dict[str, str]:
    """The `key: value` lines a verb prints."""
    return {
        key: value.strip()
        for key, _, value in (line.partition(":") for line in output.splitlines())
    }


@pytest.fixture
def project(tmp_path: Path) -> Project:
    git_env = {**os.environ, **GIT_ENV_OVERRIDES, "HOME": str(tmp_path)}
    origin = tmp_path / "origin.git"
    path = tmp_path / "work"
    path.mkdir()
    created = Project(path=path, git_env=git_env)
    created.git("init", "-q", "--bare", "-b", "main", str(origin), cwd=tmp_path)
    created.git("init", "-q", "-b", "main")
    created.git("remote", "add", "origin", str(origin))
    write_tree(
        path,
        alpha_app() | {"pyproject.toml": TIER_CONFIG, ".gitignore": ".sdd-work/\n"},
    )
    for source in SELECTOR_SOURCES:
        created.write(f".claude/ds/scripts/{source.name}", source.read_text())
    created.write(
        SELECTOR,
        f'#!/bin/sh\nexec {sys.executable} "$(dirname "$0")/select_tests.py" "$@"\n',
    )
    (path / SELECTOR).chmod(0o755)
    created.commit("base")
    created.git("push", "-q", "origin", "main")
    created.git("checkout", "-q", "-b", "feature")
    return created


def commit_app_change(project: Project, content: str = "one\n") -> str:
    project.write("pkg/alpha/services.py", content)
    return project.commit("app change")


def commit_spec_change(project: Project) -> str:
    project.write("spec_dd/2. in progress/x/spec.md", "text\n")
    return project.commit("spec change")


def test_branch_with_no_record_resolves_to_full(project: Project) -> None:
    # Arrange
    commit_app_change(project)

    # Act
    resolution = project.resolve()

    # Assert
    assert resolution == {"tier": "full", "diff": "", "why": "no full-run record"}


def test_spec_only_branch_with_no_record_resolves_to_none(project: Project) -> None:
    # Arrange
    commit_spec_change(project)

    # Act
    resolution = project.resolve()

    # Assert
    assert resolution["tier"] == "none"
    assert resolution["why"] == "the branch holds no test-visible change"


def test_spec_only_change_after_a_record_resolves_to_none_naming_the_commit(
    project: Project,
) -> None:
    # Arrange
    recorded = commit_app_change(project)
    project.record_green()
    commit_spec_change(project)

    # Act
    resolution = project.resolve()

    # Assert
    assert resolution == {
        "tier": "none",
        "diff": "",
        "why": f"no test-visible change since full green at {recorded[:7]}",
    }


def test_app_change_after_a_record_resolves_to_targeted_over_the_range(
    project: Project,
) -> None:
    # Arrange
    recorded = commit_app_change(project)
    project.record_green()
    commit_app_change(project, "two\n")

    # Act
    resolution = project.resolve()

    # Assert
    assert resolution["tier"] == "targeted"
    assert resolution["diff"] == f"--range {recorded}..HEAD --working-tree"
    assert resolution["why"] == f"range {recorded[:7]}..HEAD"


def test_uncommitted_app_edit_after_a_record_resolves_to_targeted(
    project: Project,
) -> None:
    # Arrange
    commit_app_change(project)
    project.record_green()
    project.write("pkg/alpha/services.py", "edited\n")

    # Act
    resolution = project.resolve()

    # Assert
    assert resolution["tier"] == "targeted"


def test_lock_file_change_after_a_record_resolves_to_full(project: Project) -> None:
    # Arrange
    recorded = commit_app_change(project)
    project.record_green()
    project.write("uv.lock", "locked\n")
    project.commit("lock")

    # Act
    resolution = project.resolve()

    # Assert
    assert resolution == {
        "tier": "full",
        "diff": "",
        "why": f"the selector escalates over {recorded[:7]}..HEAD",
    }


@pytest.mark.parametrize("contents", ["0" * 40, "--help"])
def test_unusable_record_resolves_to_full(project: Project, contents: str) -> None:
    # Arrange
    commit_app_change(project)
    record = project.record_file("feature")
    record.parent.mkdir()
    record.write_text(f"{contents}\n")

    # Act
    resolution = project.resolve()

    # Assert
    assert resolution["tier"] == "full"


def test_record_taken_before_a_rebase_onto_a_moved_main_sees_what_main_changed(
    project: Project,
) -> None:
    # Arrange
    commit_app_change(project)
    project.record_green()
    project.git("checkout", "-q", "main")
    project.write("uv.lock", "locked\n")
    project.commit("main moves")
    project.git("push", "-q", "origin", "main")
    project.git("checkout", "-q", "feature")
    project.git("rebase", "-q", "main")

    # Act
    resolution = project.resolve()

    # Assert
    assert resolution["tier"] == "full"


def test_missing_selector_resolves_to_full(project: Project) -> None:
    # Arrange
    commit_app_change(project)

    # Act
    resolution = parse(project.script("resolve"))

    # Assert
    assert resolution == {"tier": "full", "diff": "", "why": "no tier selector"}


def test_selector_outside_the_project_root_is_a_usage_error(
    project: Project, tmp_path: Path
) -> None:
    # Arrange
    outside = tmp_path / "outside.sh"
    outside.write_text("#!/bin/sh\n")

    # Act
    result = run_script(
        SCRIPT,
        project.path,
        "resolve",
        "--selector",
        str(outside),
        environment=project.git_env,
    )

    # Assert
    assert result.returncode == 64


def test_read_prints_the_recorded_commit(project: Project) -> None:
    # Arrange
    recorded = commit_app_change(project)
    project.record_green()

    # Act
    output = project.script("read")

    # Assert
    assert output == f"{recorded}\n"


def test_branches_that_differ_only_by_slash_or_underscore_get_separate_records(
    project: Project,
) -> None:
    # Arrange
    project.git("checkout", "-q", "-b", "a/b")
    project.record_green()
    project.git("checkout", "-q", "-b", "a_b")

    # Act
    project.record_green()

    # Assert
    assert project.record_file("a/b") != project.record_file("a_b")
    assert project.record_file("a/b").is_file()
    assert project.record_file("a_b").is_file()


@pytest.mark.parametrize("scenario", ["fail", "incomplete", "dirty", "detached"])
def test_write_leaves_no_record_unless_the_run_passed_on_a_clean_branch(
    project: Project, scenario: str
) -> None:
    # Arrange
    commit_app_change(project)
    verdict = scenario if scenario in ("fail", "incomplete") else "pass"
    if scenario == "dirty":
        project.write("pkg/alpha/services.py", "uncommitted\n")
    if scenario == "detached":
        project.git("checkout", "-q", "--detach")

    # Act
    output = project.script("write", "--verdict", verdict)

    # Assert
    assert output.startswith("not recorded")
    assert not (project.path / ".sdd-work").exists()


@pytest.mark.parametrize("stray_untracked_file", [False, True])
def test_write_records_head_on_a_clean_tracked_tree(
    project: Project, stray_untracked_file: bool
) -> None:
    # Arrange
    head = commit_app_change(project)
    if stray_untracked_file:
        project.write("scratch.txt", "stray\n")

    # Act
    output = project.script("write", "--verdict", "pass")

    # Assert
    assert output == f"recorded: {head}\n"
    assert project.record_file("feature").read_text() == f"{head}\n"
