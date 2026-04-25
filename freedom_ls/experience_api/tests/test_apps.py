"""Tests for AppConfig startup validation.

Boot-time validation catches operator misconfiguration where it is easy
to spot, rather than at the moment ``erase_actor`` runs against an
irreversible flow.
"""

from __future__ import annotations

import pytest

from django.core.exceptions import ImproperlyConfigured

from freedom_ls.experience_api.apps import ExperienceApiConfig


def _config() -> ExperienceApiConfig:
    """Return a non-installed AppConfig instance for direct method calls."""
    instance = ExperienceApiConfig.create("freedom_ls.experience_api")
    assert isinstance(instance, ExperienceApiConfig)
    return instance


def test_check_erasure_blockers_accepts_empty_list(settings) -> None:
    settings.EXPERIENCE_API_ERASURE_BLOCKERS = []
    _config()._check_erasure_blockers()


def test_check_erasure_blockers_accepts_valid_callable(settings) -> None:
    settings.EXPERIENCE_API_ERASURE_BLOCKERS = [
        "freedom_ls.experience_api.tests.test_apps._sample_blocker"
    ]
    _config()._check_erasure_blockers()


def test_check_erasure_blockers_rejects_unparseable_path(settings) -> None:
    settings.EXPERIENCE_API_ERASURE_BLOCKERS = ["no_dot_here"]
    with pytest.raises(ImproperlyConfigured, match="Invalid"):
        _config()._check_erasure_blockers()


def test_check_erasure_blockers_rejects_unimportable_module(settings) -> None:
    settings.EXPERIENCE_API_ERASURE_BLOCKERS = [
        "freedom_ls.experience_api.does_not_exist.some_func"
    ]
    with pytest.raises(ImproperlyConfigured, match="could not be imported"):
        _config()._check_erasure_blockers()


def test_check_erasure_blockers_rejects_non_callable(settings) -> None:
    settings.EXPERIENCE_API_ERASURE_BLOCKERS = [
        "freedom_ls.experience_api.tests.test_apps._not_callable"
    ]
    with pytest.raises(ImproperlyConfigured, match="not resolve to a callable"):
        _config()._check_erasure_blockers()


def _sample_blocker(user_id: int) -> bool:
    """Module-level callable used by the happy-path test."""
    return False


_not_callable = "not a callable"
