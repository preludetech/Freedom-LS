from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.dev_tooling

SCRIPT = (
    Path(__file__).resolve().parents[1] / "claude_plugins/sdd/scripts/python_with.sh"
)
KEY = "Python with packages"


def write_config(project: Path, name: str, value: str) -> None:
    config = project / ".claude/sdd" / name
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(
        f"# SDD Plugin Configuration\n\n## Script Hooks\n\n- {KEY}: {value}\n",
        encoding="utf-8",
    )


def run_helper(project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [str(SCRIPT), *args],
        cwd=project,
        env={"PATH": "/usr/bin:/bin", "CLAUDE_PROJECT_DIR": str(project)},
        capture_output=True,
        text=True,
        check=False,
    )


def test_configured_runner_gets_the_package_and_the_arguments(tmp_path: Path) -> None:
    write_config(tmp_path, "config.md", "echo runner {packages} python")

    result = run_helper(tmp_path, "pillow", "script.py", "--flag", "a b")

    assert result.returncode == 0
    assert result.stdout == "runner pillow python script.py --flag a b\n"


def test_local_config_wins(tmp_path: Path) -> None:
    write_config(tmp_path, "config.md", "echo shared {packages}")
    write_config(tmp_path, "config.local.md", "echo local {packages}")

    result = run_helper(tmp_path, "pillow")

    assert result.stdout == "local pillow\n"


def test_blank_local_value_falls_back_to_the_shared_config(tmp_path: Path) -> None:
    write_config(tmp_path, "config.md", "echo shared {packages}")
    write_config(tmp_path, "config.local.md", "")

    result = run_helper(tmp_path, "pillow")

    assert result.stdout == "shared pillow\n"


@pytest.mark.parametrize("configured", [True, False])
def test_blank_or_missing_key_runs_plain_python(
    tmp_path: Path, configured: bool
) -> None:
    if configured:
        write_config(tmp_path, "config.md", "")

    result = run_helper(tmp_path, "pillow", "-c", "print('plain')")

    assert result.returncode == 0
    assert result.stdout == "plain\n"


def test_missing_package_argument_is_a_usage_error(tmp_path: Path) -> None:
    result = run_helper(tmp_path)

    assert result.returncode == 64
    assert "Usage" in result.stderr
