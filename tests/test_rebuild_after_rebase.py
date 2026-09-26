"""Tests for the rebuild script the fls-dev plugin runs after every rebase.

This test assumes `claude_plugins/` and `.claude/fls-dev/scripts/` sit at the project
root, so it exercises both the plugin's own
`claude_plugins/fls-dev/scripts/rebuild_after_rebase.sh` and the generated wrapper at
`.claude/fls-dev/scripts/rebuild_after_rebase.sh`. No database is needed: `uv` and `npm`
are replaced with stub executables that only log their own invocation, so the real
`uv sync` / `npm i` / `npm run tailwind_build` never runs.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SCRIPT = (
    REPO_ROOT / "claude_plugins" / "fls-dev" / "scripts" / "rebuild_after_rebase.sh"
)
WRAPPER_SCRIPT = (
    REPO_ROOT / ".claude" / "fls-dev" / "scripts" / "rebuild_after_rebase.sh"
)

STUB_TEMPLATE = """#!/bin/sh
printf '%s %s\\n' "$(basename "$0")" "$*" >> "$STUB_LOG_FILE"
exit "${{{exit_var}:-0}}"
"""


@dataclass
class StubTools:
    bin_dir: Path
    log_file: Path

    def env(self, *, uv_exit: int = 0, npm_exit: int = 0) -> dict[str, str]:
        child_env = dict(os.environ)
        child_env["PATH"] = f"{self.bin_dir}{os.pathsep}{child_env.get('PATH', '')}"
        child_env["STUB_LOG_FILE"] = str(self.log_file)
        child_env["STUB_UV_EXIT_CODE"] = str(uv_exit)
        child_env["STUB_NPM_EXIT_CODE"] = str(npm_exit)
        return child_env

    def log_lines(self) -> list[str]:
        if not self.log_file.exists():
            return []
        return self.log_file.read_text().splitlines()


def _write_stub(path: Path, exit_var: str) -> None:
    path.write_text(STUB_TEMPLATE.format(exit_var=exit_var))
    path.chmod(0o755)


@pytest.fixture
def stub_tools(tmp_path: Path) -> StubTools:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_stub(bin_dir / "uv", "STUB_UV_EXIT_CODE")
    _write_stub(bin_dir / "npm", "STUB_NPM_EXIT_CODE")
    return StubTools(bin_dir=bin_dir, log_file=tmp_path / "log.txt")


def _run_script(
    script: Path, cwd: Path, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [str(script)],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_plugin_script_runs_sync_install_and_tailwind_build_in_order(
    stub_tools: StubTools, tmp_path: Path
) -> None:
    # Arrange
    env = stub_tools.env()

    # Act
    result = _run_script(PLUGIN_SCRIPT, tmp_path, env)

    # Assert
    assert result.returncode == 0
    assert stub_tools.log_lines() == ["uv sync", "npm i", "npm run tailwind_build"]


def test_failing_npm_i_stops_the_script_before_tailwind_build(
    stub_tools: StubTools, tmp_path: Path
) -> None:
    # Arrange
    env = stub_tools.env(npm_exit=7)

    # Act
    result = _run_script(PLUGIN_SCRIPT, tmp_path, env)

    # Assert
    assert result.returncode == 7
    assert stub_tools.log_lines() == ["uv sync", "npm i"]


def test_wrapper_script_produces_the_same_log(
    stub_tools: StubTools, tmp_path: Path
) -> None:
    # Arrange
    env = stub_tools.env()

    # Act
    result = _run_script(WRAPPER_SCRIPT, tmp_path, env)

    # Assert
    assert result.returncode == 0
    assert stub_tools.log_lines() == ["uv sync", "npm i", "npm run tailwind_build"]
