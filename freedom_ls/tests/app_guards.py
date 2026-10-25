"""Shared test guards for optionally-installed FLS apps.

An app may appear in ``INSTALLED_APPS`` by its plain dotted path or by its
``AppConfig`` path; ``apps.is_installed()`` resolves both, unlike raw
``in settings.INSTALLED_APPS`` membership.
"""

from __future__ import annotations

from django.apps import apps


def app_not_installed(app_label_dotted: str) -> bool:
    """True when the app is absent — matches plain-name and AppConfig-path installs."""
    return not apps.is_installed(app_label_dotted)


def ignore_tests_unless_installed(app_label_dotted: str) -> list[str]:
    """``collect_ignore_glob`` for a ``tests/conftest.py``: every test module below it.

    Covers subdirectories too, so ``tests/playwright/`` needs no guard of its own.
    """
    if app_not_installed(app_label_dotted):
        return ["test_*.py", "**/test_*.py"]
    return []
