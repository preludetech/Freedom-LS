"""Meta-tests proving the conformance probes have teeth.

Each probe contains a runtime `pytest.skip(...)` gate, which is a deliberate
exception to the "no conditionals in test bodies" convention (the gates are
what makes the suite override-friendly). These tests exercise those gates
directly by calling the probe functions with hand-built inputs, proving the
gates skip when they should and still fail when a seam is genuinely broken.

The probe functions are imported under aliases: importing them under their
real `test_*` names would make pytest additionally collect them as top-level
tests in *this* module (pytest matches any module-level callable named
`test_*`, regardless of where it was defined), duplicating the whole probe
table under this file's node IDs.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.state import ProjectState
from django.test import override_settings
from django.urls import NoReverseMatch

if TYPE_CHECKING:
    from collections.abc import Iterator

from freedom_ls.contrib.conformance._registry import _DROPPED, drop
from freedom_ls.contrib.conformance.test_migrations import (
    test_migration_state_consistent as probe_migration_state_consistent,
)
from freedom_ls.contrib.conformance.test_settings import (
    test_configured_backend_instantiates as probe_backend_instantiates,
)
from freedom_ls.contrib.conformance.test_theme import (
    test_active_theme_resolves as probe_theme_resolves,
)
from freedom_ls.contrib.conformance.test_urls import _Probe
from freedom_ls.contrib.conformance.test_urls import (
    test_fls_namespace_reverses as probe_namespace_reverses,
)
from freedom_ls.course_access.loader import get_course_access_backend

pytestmark = pytest.mark.fls_internal


@pytest.fixture(autouse=True)
def _reset_dropped_probes() -> Iterator[None]:
    yield
    _DROPPED.clear()


def test_namespace_probe_fails_for_unresolvable_viewname() -> None:
    broken = _Probe(
        "freedom_ls.student_interface", "student_interface:does_not_exist", True
    )

    with pytest.raises(NoReverseMatch):
        probe_namespace_reverses(broken)


def test_namespace_probe_skips_when_its_app_is_not_installed() -> None:
    remaining_apps = [
        app for app in settings.INSTALLED_APPS if app != "freedom_ls.student_interface"
    ]
    probe = _Probe("freedom_ls.student_interface", "student_interface:dashboard", True)

    with (
        override_settings(INSTALLED_APPS=remaining_apps),
        pytest.raises(pytest.skip.Exception),
    ):
        probe_namespace_reverses(probe)


def test_namespace_probe_treats_appconfig_path_install_as_installed() -> None:
    apps_via_config_path = [
        "freedom_ls.student_interface.apps.StudentInterfaceConfig"
        if app == "freedom_ls.student_interface"
        else app
        for app in settings.INSTALLED_APPS
    ]
    probe = _Probe("freedom_ls.student_interface", "student_interface:dashboard", True)

    with override_settings(INSTALLED_APPS=apps_via_config_path):
        probe_namespace_reverses(probe)


def test_dropped_internal_probe_skips() -> None:
    drop("student_interface:courses")
    probe = _Probe("freedom_ls.student_interface", "student_interface:courses", False)

    with pytest.raises(pytest.skip.Exception):
        probe_namespace_reverses(probe)


def test_drop_does_not_exempt_contract_tier_probes() -> None:
    drop("student_interface:removed_route")
    broken_contract_probe = _Probe(
        "freedom_ls.student_interface", "student_interface:removed_route", True
    )

    with pytest.raises(NoReverseMatch):
        probe_namespace_reverses(broken_contract_probe)


def test_configured_backend_instantiates_raises_for_unimportable_backend() -> None:
    with override_settings(COURSE_ACCESS_BACKEND="does.not.Exist"):
        get_course_access_backend.cache_clear()

        with pytest.raises(ImportError):
            probe_backend_instantiates()


def test_migration_state_consistent_passes_on_clean_tree() -> None:
    probe_migration_state_consistent()


def test_migration_state_consistent_detects_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _empty_project_state(
        self: MigrationLoader, *args: object, **kwargs: object
    ) -> ProjectState:
        return ProjectState()

    monkeypatch.setattr(MigrationLoader, "project_state", _empty_project_state)

    with pytest.raises(AssertionError):
        probe_migration_state_consistent()


def test_active_theme_probe_fails_when_active_theme_missing_from_dirs(
    tmp_path: Path,
) -> None:
    empty_themes_dir = tmp_path / "themes"
    empty_themes_dir.mkdir()

    with (
        override_settings(FLS_THEMES_DIRS=[empty_themes_dir]),
        pytest.raises(ImproperlyConfigured),
    ):
        probe_theme_resolves()
