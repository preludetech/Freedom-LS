"""The educator interface's panels pass the panel framework's system checks."""

from __future__ import annotations

import gc

from django.core.management import call_command


def test_call_command_check_passes_under_the_project_urlconf() -> None:
    gc.collect()

    call_command("check")
