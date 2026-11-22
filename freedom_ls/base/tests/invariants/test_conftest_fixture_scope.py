"""Proves FLS's conftest leaves a concrete project's own tests alone.

A concrete project runs FLS's suite and its own in one pytest session, with
`freedom_ls/conftest.py` as a subdirectory conftest. A session-scoped fixture
there stays set up after FLS's tests finish, so a settings override it holds
reaches every project test that runs later in the same process. Proving that
needs a layout FLS's own repo does not have, built in a fresh subprocess.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest_plugins = ["pytester"]

REPO_ROOT = Path(__file__).resolve().parents[4]

pytestmark = pytest.mark.fls_internal


def test_force_site_name_override_ends_with_fls_tests(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A project test run after an FLS test sees the project's FORCE_SITE_NAME."""
    (pytester.path / "freedom_ls").symlink_to(REPO_ROOT / "freedom_ls")
    pytester.makepyfile(
        settings_probe=(
            "from config.settings_dev import *\nFORCE_SITE_NAME = 'Probe Site'\n"
        )
    )
    probe_dir = pytester.mkdir("project_tests")
    (probe_dir / "test_probe.py").write_text(
        "from django.conf import settings\n\n\n"
        "def test_project_setting_survives():\n"
        "    assert settings.FORCE_SITE_NAME == 'Probe Site'\n"
    )
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "settings_probe")
    monkeypatch.setenv("PYTHONPATH", f"{pytester.path}:{REPO_ROOT}")

    result = pytester.runpytest_subprocess(
        "-q",
        "-p",
        "no:cov",
        "-p",
        "no:playwright",
        "-p",
        "no:randomly",
        "-p",
        "no:xdist",
        "-p",
        "no:cacheprovider",
        "-o",
        "addopts=",
        f"--rootdir={pytester.path}",
        "freedom_ls/icons/tests/test_config.py::test_new_name_alone_is_returned",
        "project_tests/test_probe.py",
    )

    result.assert_outcomes(passed=4)
