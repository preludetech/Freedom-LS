"""Proves collection survives when `course_applications` is absent.

Django's app registry is populated once per process, so proving that pytest
collection does not abort under a different `INSTALLED_APPS` genuinely
requires a fresh subprocess. This module must NOT import
`freedom_ls.course_applications` at module scope — that would defeat the
point of the test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest_plugins = ["pytester"]

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_collection_survives_without_course_applications(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Removing course_applications from INSTALLED_APPS degrades to skips, not an abort."""
    pytester.makepyfile(
        settings_no_ca=(
            "from config.settings_dev import *\n"
            "INSTALLED_APPS = [a for a in INSTALLED_APPS "
            "if a != 'freedom_ls.course_applications']\n"
        )
    )
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "settings_no_ca")
    monkeypatch.setenv("PYTHONPATH", str(REPO_ROOT))

    result = pytester.runpytest_subprocess(
        "--co",
        "-q",
        "-p",
        "no:cov",
        "-p",
        "no:playwright",
        "-p",
        "no:cacheprovider",
        "-o",
        "addopts=",
        f"--rootdir={REPO_ROOT}",
        str(REPO_ROOT / "freedom_ls" / "course_applications"),
        str(REPO_ROOT / "freedom_ls" / "student_interface"),
        str(REPO_ROOT / "freedom_ls" / "course_access"),
    )

    # exit 2 == "errors during collection" (the bug). 0 (items collected) or 5
    # (none collected) both mean collection did not abort.
    assert result.ret in (0, 5)


def test_appconfig_path_install_is_recognised_by_guards(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Installing course_applications by its AppConfig path must not skip its guarded tests."""
    pytester.makepyfile(
        settings_ca_appconfig=(
            "from config.settings_dev import *\n"
            "INSTALLED_APPS = ["
            "'freedom_ls.course_applications.apps.CourseApplicationsConfig' "
            "if a == 'freedom_ls.course_applications' else a "
            "for a in INSTALLED_APPS]\n"
        )
    )
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "settings_ca_appconfig")
    monkeypatch.setenv("PYTHONPATH", str(REPO_ROOT))

    # A guarded module outside course_applications/tests (so the conftest
    # collect_ignore_glob is not what keeps it — only its own app-installed guard).
    guarded_module = (
        REPO_ROOT / "freedom_ls" / "course_access" / "tests" / "test_access_override.py"
    )
    result = pytester.runpytest_subprocess(
        "--co",
        "-q",
        "-p",
        "no:cov",
        "-p",
        "no:playwright",
        "-p",
        "no:cacheprovider",
        "-o",
        "addopts=",
        f"--rootdir={REPO_ROOT}",
        str(guarded_module),
    )

    # exit 0 == items collected: the guard recognised the AppConfig-path install.
    # A raw `in INSTALLED_APPS` guard would module-skip here and yield 5 (none collected).
    assert result.ret == 0
