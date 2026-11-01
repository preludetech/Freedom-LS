from __future__ import annotations

from datetime import timedelta

from django.test import override_settings

from freedom_ls.deadlines.config import config


def test_a_project_override_is_returned_over_the_default() -> None:
    override = {"grace_window": timedelta(days=9)}

    with override_settings(DEADLINE_POLICY_DEFAULTS=override):
        assert override == config.DEADLINE_POLICY_DEFAULTS


def test_mutating_the_returned_defaults_does_not_change_the_next_read() -> None:
    first = config.DEADLINE_POLICY_DEFAULTS
    first["close_items"] = "mutated"

    assert config.DEADLINE_POLICY_DEFAULTS["close_items"] != "mutated"
