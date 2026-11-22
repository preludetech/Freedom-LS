"""FreedomLS's own test-tier configuration, checked against this repository.

`[tool.test_tiers]` in `pyproject.toml` turns on narrowing and maps `demo_content/**` to the
test targets that read it. These tests read the real `pyproject.toml`, the tracked tests and the
git history, so they only make sense inside FreedomLS's own checkout.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path

import pytest

from tests._script_trees import run_command, run_script

pytestmark = [pytest.mark.dev_tooling, pytest.mark.fls_internal]

REPO_ROOT = Path(__file__).resolve().parents[1]
THIS_FILE = Path(__file__).resolve().relative_to(REPO_ROOT).as_posix()
SELECTOR = Path("claude_plugins") / "django-stack" / "scripts" / "select_tests.py"

DEMO_CONTENT_TARGETS = (
    "freedom_ls/content_engine/tests/demo_content",
    "freedom_ls/learner_interface/tests/demo_content",
    "freedom_ls/blog/tests/demo_content",
    "freedom_ls/content_engine/tests/test_validate.py",
    "claude_plugins/fls-content/validate/tests/test_validator.py",
)
RECENT_COMMIT_COUNT = 5
NARROW_SETTING = "narrow = true\n"


def git_output(*args: str) -> str:
    result = run_command(["git", *args], REPO_ROOT)
    result.check_returncode()
    return result.stdout


def tracked_demo_content_file() -> str:
    return next(
        path
        for path in git_output("ls-files", "demo_content").splitlines()
        if path.endswith(".yaml")
    )


def demo_content_readers_outside_targets() -> list[str]:
    """Tracked test files that mention `demo_content` and sit under none of the targets."""
    offenders: list[str] = []
    for path in git_output("ls-files").splitlines():
        if not fnmatch.fnmatch(Path(path).name, "test_*.py"):
            continue
        # This file names `demo_content` to check the selector's rule for it, not to read the content.
        if path == THIS_FILE:
            continue
        if "demo_content" not in (REPO_ROOT / path).read_text(encoding="utf-8"):
            continue
        if not any(path == t or path.startswith(f"{t}/") for t in DEMO_CONTENT_TARGETS):
            offenders.append(path)
    return offenders


def recent_commit(project: Path, index: int) -> str:
    """The commit `index` steps back along first parents from `project`'s HEAD. Resolved when
    the test runs, not at collection, so every xdist worker collects the same test ids even
    when a commit lands mid-run."""
    result = run_command(["git", "rev-parse", f"HEAD~{index}"], project)
    result.check_returncode()
    return result.stdout.strip()


def selection(project: Path, *args: str) -> tuple[str, str]:
    """The `tier:` and `command:` lines the selector prints."""
    result = run_script(project / SELECTOR, project, *args)
    result.check_returncode()
    printed = result.stdout.splitlines()
    return (
        next(line for line in printed if line.startswith("tier:")),
        next((line for line in printed if line.startswith("command:")), ""),
    )


@pytest.fixture
def clone(tmp_path: Path) -> Path:
    if git_output("rev-parse", "--is-shallow-repository").strip() == "true":
        pytest.skip("a shallow checkout has no history to select over")
    destination = tmp_path / "clone"
    run_command(
        ["git", "clone", "--quiet", "--shared", str(REPO_ROOT), str(destination)],
        tmp_path,
    ).check_returncode()
    return destination


def test_demo_content_path_selects_exactly_the_five_targets() -> None:
    # Arrange
    path = tracked_demo_content_file()

    # Act
    result = run_script(REPO_ROOT / SELECTOR, REPO_ROOT, path)

    # Assert
    result.check_returncode()
    why = next(line for line in result.stdout.splitlines() if line.startswith("why:"))
    assert why == f"why: {path} -> {', '.join(DEMO_CONTENT_TARGETS)} (tooling)"


def test_test_files_reading_demo_content_sit_under_the_demo_content_targets() -> None:
    # Act
    offenders = demo_content_readers_outside_targets()

    # Assert
    assert offenders == []


@pytest.mark.parametrize("index", range(RECENT_COMMIT_COUNT))
def test_wide_selection_matches_no_narrow_key_for_recent_commit(
    clone: Path, index: int
) -> None:
    # Arrange
    commit = recent_commit(clone, index)
    configured = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    without_key = configured.replace(NARROW_SETTING, "")
    with_key = without_key.replace(
        "[tool.test_tiers]\n", f"[tool.test_tiers]\n{NARROW_SETTING}", 1
    )
    range_args = ("--range", f"{commit}^..{commit}")
    (clone / "pyproject.toml").write_text(without_key, encoding="utf-8")
    expected = selection(clone, *range_args)
    (clone / "pyproject.toml").write_text(with_key, encoding="utf-8")

    # Act
    actual = selection(clone, "--wide", *range_args)

    # Assert
    assert actual == expected
