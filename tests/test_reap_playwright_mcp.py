"""Tests for the ds plugin's orphaned-Playwright-MCP reaper.

This test assumes `claude_plugins/` and `.claude/ds/scripts/` sit at the project root, so it
exercises both `claude_plugins/django-stack/scripts/reap_playwright_mcp.sh` and the generated
wrapper at `.claude/ds/scripts/reap_playwright_mcp.sh`. No process is ever signalled: `ps` and
`id` are replaced with stub executables that print a fixed process table and a fixed uid, so
the script never sees or touches a real process. `--kill` is not exercised here, because it
would signal real PIDs.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from tests.stub_tools import StubTools, run_script, write_stub

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SCRIPT = (
    REPO_ROOT / "claude_plugins" / "django-stack" / "scripts" / "reap_playwright_mcp.sh"
)
WRAPPER_SCRIPT = REPO_ROOT / ".claude" / "ds" / "scripts" / "reap_playwright_mcp.sh"

CURRENT_UID = "1000"
OTHER_UID = "1001"

# pid ppid uid etime rss command
# - 100: the current user's own systemd --user, the subreaper.
# - 200/201/202: an old MCP server re-parented to PID 1, with a browser child and grandchild.
# - 300: an old MCP server re-parented to the subreaper, matching the "playwright-mcp" spelling.
# - 400: an orphaned MCP server too young to be a candidate.
# - 500/600: an MCP server whose parent (600, "claude") is still alive.
# - 700: an old orphaned MCP server owned by another uid.
# - 800: an unrelated old orphan that is not a Playwright MCP server.
# - 900: an old MCP server whose etime is reported in mm:ss form.
PROCESS_TABLE = "\n".join(
    [
        f"100 1 {CURRENT_UID} 3-00:00:00 4000 systemd --user",
        f"200 1 {CURRENT_UID} 02:00:00 15000 "
        "npx @playwright/mcp@0.0.83 --isolated --idle-timeout 600000",
        f"201 200 {CURRENT_UID} 01:59:00 90000 "
        "/usr/bin/chromium --headless --type=browser --user-data-dir=/tmp/x",
        f"202 201 {CURRENT_UID} 01:58:30 45000 "
        "/usr/bin/chromium --type=renderer --field-trial-handle=1,2,3",
        f"300 100 {CURRENT_UID} 1-02:00:00 15000 npx playwright-mcp@0.0.83 --headless",
        f"400 1 {CURRENT_UID} 45:00 15000 npx @playwright/mcp@0.0.83 --isolated",
        f"600 50 {CURRENT_UID} 03:00:00 20000 claude",
        f"500 600 {CURRENT_UID} 02:00:00 15000 npx @playwright/mcp@0.0.83 --isolated",
        f"700 1 {OTHER_UID} 02:00:00 15000 npx @playwright/mcp@0.0.83 --isolated",
        f"800 1 {CURRENT_UID} 02:00:00 8000 some-other-daemon --flag",
        f"900 1 {CURRENT_UID} 65:00 9000 npx @playwright/mcp@0.0.83 --isolated",
    ]
)

EMPTY_PROCESS_TABLE = "\n".join(
    [
        f"100 1 {CURRENT_UID} 3-00:00:00 4000 systemd --user",
        f"800 1 {CURRENT_UID} 02:00:00 8000 some-other-daemon --flag",
    ]
)


def listed_pids(stdout: str) -> set[str]:
    """The pids on the candidate lines, ignoring the header row."""
    lines = stdout.splitlines()[1:]
    return {line.split()[0] for line in lines if line}


def age_of(stdout: str, pid: str) -> str:
    """The age field of the candidate line for `pid`."""
    fields_by_pid = {line.split()[0]: line.split() for line in stdout.splitlines()[1:]}
    return fields_by_pid[pid][1]


@pytest.fixture(params=[PLUGIN_SCRIPT, WRAPPER_SCRIPT], ids=["plugin", "wrapper"])
def reaper_script(request: pytest.FixtureRequest) -> Path:
    return cast(Path, request.param)


@pytest.fixture
def stub_tools(tmp_path: Path) -> StubTools:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    write_stub(
        bin_dir / "ps", exit_var="STUB_PS_EXIT_CODE", output_var="STUB_PS_OUTPUT"
    )
    write_stub(
        bin_dir / "id", exit_var="STUB_ID_EXIT_CODE", output_var="STUB_ID_OUTPUT"
    )
    return StubTools(bin_dir=bin_dir, log_file=tmp_path / "log.txt")


def test_old_orphan_reparented_to_pid_1_is_listed_with_its_descendants(
    reaper_script: Path, stub_tools: StubTools, tmp_path: Path
) -> None:
    # Arrange
    env = stub_tools.env(STUB_PS_OUTPUT=PROCESS_TABLE, STUB_ID_OUTPUT=CURRENT_UID)

    # Act
    result = run_script(reaper_script, tmp_path, env)

    # Assert
    assert listed_pids(result.stdout) >= {"200", "201", "202"}


def test_old_orphan_reparented_to_the_subreaper_is_listed(
    reaper_script: Path, stub_tools: StubTools, tmp_path: Path
) -> None:
    # Arrange
    env = stub_tools.env(STUB_PS_OUTPUT=PROCESS_TABLE, STUB_ID_OUTPUT=CURRENT_UID)

    # Act
    result = run_script(reaper_script, tmp_path, env)

    # Assert
    assert "300" in listed_pids(result.stdout)


@pytest.mark.parametrize(
    "excluded_pid",
    ["400", "500", "600", "700", "800"],
    ids=[
        "too-young",
        "live-parent",
        "the-live-parent-itself",
        "other-uid",
        "unrelated",
    ],
)
def test_non_candidate_processes_are_not_listed(
    excluded_pid: str, reaper_script: Path, stub_tools: StubTools, tmp_path: Path
) -> None:
    # Arrange
    env = stub_tools.env(STUB_PS_OUTPUT=PROCESS_TABLE, STUB_ID_OUTPUT=CURRENT_UID)

    # Act
    result = run_script(reaper_script, tmp_path, env)

    # Assert
    assert excluded_pid not in listed_pids(result.stdout)


def test_a_command_line_with_spaces_is_printed_whole(
    reaper_script: Path, stub_tools: StubTools, tmp_path: Path
) -> None:
    # Arrange
    env = stub_tools.env(STUB_PS_OUTPUT=PROCESS_TABLE, STUB_ID_OUTPUT=CURRENT_UID)

    # Act
    result = run_script(reaper_script, tmp_path, env)

    # Assert
    assert (
        "npx @playwright/mcp@0.0.83 --isolated --idle-timeout 600000" in result.stdout
    )


@pytest.mark.parametrize(
    ("pid", "expected_age"),
    [("900", 3900), ("200", 7200), ("300", 93600)],
    ids=["mm:ss", "hh:mm:ss", "dd-hh:mm:ss"],
)
def test_age_is_parsed_from_each_etime_format(
    pid: str,
    expected_age: int,
    reaper_script: Path,
    stub_tools: StubTools,
    tmp_path: Path,
) -> None:
    # Arrange
    env = stub_tools.env(STUB_PS_OUTPUT=PROCESS_TABLE, STUB_ID_OUTPUT=CURRENT_UID)

    # Act
    result = run_script(reaper_script, tmp_path, env)

    # Assert
    assert age_of(result.stdout, pid) == str(expected_age)


def test_no_candidates_prints_the_no_orphans_line_and_exits_0(
    reaper_script: Path, stub_tools: StubTools, tmp_path: Path
) -> None:
    # Arrange
    env = stub_tools.env(STUB_PS_OUTPUT=EMPTY_PROCESS_TABLE, STUB_ID_OUTPUT=CURRENT_UID)

    # Act
    result = run_script(reaper_script, tmp_path, env)

    # Assert
    assert result.returncode == 0
    assert result.stdout == "No orphaned Playwright MCP processes\n"
