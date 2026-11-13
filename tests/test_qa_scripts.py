"""The QA scripts resolve a relative spec dir against the project root, not the cwd."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.dev_tooling

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "claude_plugins/sdd/scripts"
CLEANUP = SCRIPTS_DIR / "qa_cleanup.sh"
COLLECT = SCRIPTS_DIR / "qa_collect_screenshots.sh"
SPEC_REL = "spec_dd/2. in progress/some-spec"


def run_script(
    script: Path, project: Path, cwd: Path, *args: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [str(script), *args],
        cwd=cwd,
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(project)},
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A project root with a spec dir and a subdirectory to run from."""
    root = tmp_path / "project"
    (root / SPEC_REL).mkdir(parents=True)
    (root / "subdir").mkdir()
    return root


def test_cleanup_from_a_subdirectory_removes_the_previous_run(project: Path) -> None:
    spec = project / SPEC_REL
    (spec / "qa_report.md").write_text("old report")
    (spec / "screenshots").mkdir()
    (spec / "screenshots" / "a.png").write_bytes(b"png")

    result = run_script(CLEANUP, project, project / "subdir", SPEC_REL)

    assert result.returncode == 0, result.stderr
    assert not (spec / "qa_report.md").exists()
    assert not (spec / "screenshots").exists()


def test_collect_from_a_subdirectory_moves_screenshots_into_the_spec(
    project: Path,
) -> None:
    source = project / "qa-screenshots"
    source.mkdir()
    (source / "a.png").write_bytes(b"png")

    result = run_script(
        COLLECT, project, project / "subdir", SPEC_REL, "qa-screenshots"
    )

    assert result.returncode == 0, result.stderr
    assert (project / SPEC_REL / "screenshots" / "a.png").read_bytes() == b"png"
    assert not source.exists()


@pytest.mark.parametrize("script", [CLEANUP, COLLECT], ids=["cleanup", "collect"])
def test_absolute_spec_dir_outside_the_project_is_refused(
    project: Path, tmp_path: Path, script: Path
) -> None:
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (outside / "qa_report.md").write_text("not yours")

    result = run_script(script, project, project, str(outside), "qa-screenshots")

    assert result.returncode == 1
    assert "must be inside CLAUDE_PROJECT_DIR" in result.stderr
    assert (outside / "qa_report.md").exists()


def test_collect_into_a_subfolder_moves_screenshots_under_screenshots(
    project: Path,
) -> None:
    source = project / "qa-screenshots"
    source.mkdir()
    (source / "a.png").write_bytes(b"png")

    result = run_script(COLLECT, project, project, SPEC_REL, "qa-screenshots", "fixed")

    assert result.returncode == 0, result.stderr
    assert (project / SPEC_REL / "screenshots" / "fixed" / "a.png").exists()
    assert not source.exists()


@pytest.mark.parametrize("subfolder", ["../escape", "a/b", ".", ""])
def test_collect_refuses_a_subfolder_that_is_not_a_plain_name(
    project: Path, subfolder: str
) -> None:
    source = project / "qa-screenshots"
    source.mkdir()
    (source / "a.png").write_bytes(b"png")

    result = run_script(
        COLLECT, project, project, SPEC_REL, "qa-screenshots", subfolder
    )

    assert result.returncode == 1
    assert "subfolder" in result.stderr
    assert (source / "a.png").exists()


def test_cleanup_removes_the_screenshot_subfolders(project: Path) -> None:
    spec = project / SPEC_REL
    (spec / "screenshots" / "fixed").mkdir(parents=True)
    (spec / "screenshots" / "a.png").write_bytes(b"png")
    (spec / "screenshots" / "fixed" / "b.png").write_bytes(b"png")

    result = run_script(CLEANUP, project, project, SPEC_REL)

    assert result.returncode == 0, result.stderr
    assert not (spec / "screenshots").exists()
