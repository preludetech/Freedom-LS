"""The educator interface's panels pass the panel framework's system checks."""

from __future__ import annotations

import copy
import gc

import pytest
from pytest_django.fixtures import SettingsWrapper

from django.core.checks import run_checks
from django.core.management import call_command

from freedom_ls.base.theming import configure_theme


@pytest.mark.django_db
def test_call_command_check_passes_under_the_project_urlconf() -> None:
    gc.collect()

    call_command("check")


@pytest.mark.django_db
@pytest.mark.parametrize("theme_slug", ["default", "first_class"])
def test_the_panel_framework_raises_no_icon_check_message_under_each_theme(
    theme_slug: str, settings: SettingsWrapper
) -> None:
    templates = copy.deepcopy(settings.TEMPLATES)
    templates[0]["DIRS"] = []
    configure_theme(
        theme_slug=theme_slug,
        themes_dirs=settings.FLS_THEMES_DIRS,
        templates=templates,
        staticfiles_dirs=[],
    )
    settings.FLS_THEME = theme_slug
    settings.TEMPLATES = templates

    messages = [
        message
        for message in run_checks()
        if message.id
        in {"freedom_ls_panel_framework.E010", "freedom_ls_panel_framework.W003"}
    ]

    assert messages == []
