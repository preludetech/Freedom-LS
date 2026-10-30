from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

pytestmark = pytest.mark.dev_tooling

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "claude_plugins/fls-dev/scripts/compress_screenshots.py"
)


def write_noise_png(directory: Path, name: str) -> Path:
    """Noise does not compress, so the file is well over 1KB."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    Image.frombytes("RGB", (64, 64), os.urandom(64 * 64 * 3)).save(path, format="PNG")
    return path


def run_script(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def test_directory_argument_scans_only_under_that_directory(tmp_path: Path) -> None:
    write_noise_png(tmp_path / "a", "in_a.png")
    untouched = write_noise_png(tmp_path / "b", "in_b.png")
    before = untouched.read_bytes()

    result = run_script(tmp_path, "--max-kb", "1", "a")

    assert "Found 1 file(s)" in result.stdout
    assert "in_a.png" in result.stdout
    assert "in_b.png" not in result.stdout
    assert untouched.read_bytes() == before


def test_missing_directory_exits_1_naming_it(tmp_path: Path) -> None:
    result = run_script(tmp_path, "no_such_dir")

    assert result.returncode == 1
    assert "no_such_dir" in result.stdout


def test_directory_outside_cwd_exits_1(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    sibling = tmp_path / "sibling"
    write_noise_png(sibling, "elsewhere.png")

    result = run_script(project, "--max-kb", "1", str(sibling))

    assert result.returncode == 1
    assert "elsewhere.png" not in result.stdout


def test_dangling_symlink_is_skipped(tmp_path: Path) -> None:
    write_noise_png(tmp_path / "shots", "real.png")
    (tmp_path / "shots" / "gone.png").symlink_to(tmp_path / "shots" / "deleted.png")

    result = run_script(tmp_path, "--max-kb", "1", "shots")

    assert result.returncode == 0
    assert "Found 1 file(s)" in result.stdout
    assert "gone.png" not in result.stdout


def test_default_directory_is_spec_dd(tmp_path: Path) -> None:
    write_noise_png(tmp_path / "spec_dd", "shot.png")

    result = run_script(tmp_path, "--max-kb", "1")

    assert "shot.png" in result.stdout
