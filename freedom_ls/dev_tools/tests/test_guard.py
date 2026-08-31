"""The dev_tools gate: demo and destructive commands must not run unguarded."""

from __future__ import annotations

import click.exceptions
import pytest

from django.conf import settings
from django.core.management import CommandError, call_command

if "freedom_ls.dev_tools" not in settings.INSTALLED_APPS:  # pragma: no cover
    pytest.skip("dev_tools not installed", allow_module_level=True)

from freedom_ls.dev_tools.guard import require_dev_tools_enabled

pytestmark = pytest.mark.django_db

GUARD_MESSAGE = "disabled outside development"


def test_guard_raises_when_debug_is_false_and_setting_is_unset(settings):
    settings.DEBUG = False
    settings.DEV_TOOLS_ENABLED = False

    with pytest.raises(CommandError, match=GUARD_MESSAGE):
        require_dev_tools_enabled()


def test_guard_passes_when_debug_is_true(settings):
    settings.DEBUG = True
    settings.DEV_TOOLS_ENABLED = False

    require_dev_tools_enabled()


def test_guard_passes_when_debug_is_false_and_setting_is_enabled(settings):
    settings.DEBUG = False
    settings.DEV_TOOLS_ENABLED = True

    require_dev_tools_enabled()


@pytest.mark.parametrize(
    "command_name", ["danger_content_delete", "danger_clear_all_course_progress"]
)
def test_djclick_command_refuses_to_run_when_gate_is_closed(
    settings, capsys, command_name
):
    """djclick turns a raised CommandError into a styled stderr message plus exit(1)."""
    settings.DEBUG = False
    settings.DEV_TOOLS_ENABLED = False

    with pytest.raises(click.exceptions.Exit):
        call_command(command_name, "--yes")

    assert GUARD_MESSAGE in capsys.readouterr().err


def test_create_demo_data_raises_command_error_when_gate_is_closed(settings):
    settings.DEBUG = False
    settings.DEV_TOOLS_ENABLED = False

    with pytest.raises(CommandError, match=GUARD_MESSAGE):
        call_command("create_demo_data", "--yes")
