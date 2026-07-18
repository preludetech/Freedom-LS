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
