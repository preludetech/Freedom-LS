from __future__ import annotations

from datetime import timedelta

import pytest

from django.test import override_settings

from freedom_ls.deadlines.checks import check_policy_defaults, check_policy_imports
from freedom_ls.deadlines.config import config


def _defaults(**changes: object) -> dict[str, object]:
    return {**config.DEADLINE_POLICY_DEFAULTS, **changes}


def _without(key: str) -> dict[str, object]:
    defaults = _defaults()
    del defaults[key]
    return defaults


def test_the_default_defaults_produce_no_error() -> None:
    assert check_policy_defaults(None) == []


@pytest.mark.parametrize(
    "defaults",
    [
        _without("close_items"),
        _defaults(extra=True),
        _defaults(close_items=None),
        _defaults(close_items="on"),
        _defaults(grace_window=timedelta(seconds=-1)),
        _defaults(grace_window=None),
        _defaults(grace_window=3),
        _defaults(after_access_ended="inherit"),
        _defaults(after_access_ended="everything"),
    ],
)
def test_invalid_defaults_produce_an_error(defaults) -> None:
    with override_settings(DEADLINE_POLICY_DEFAULTS=defaults):
        errors = check_policy_defaults(None)

    assert {error.id for error in errors} == {"freedom_ls_deadlines.E001"}


def test_each_failing_condition_gets_its_own_error() -> None:
    defaults = _defaults(close_items=None, after_access_ended="inherit")

    with override_settings(DEADLINE_POLICY_DEFAULTS=defaults):
        errors = check_policy_defaults(None)

    assert len(errors) == 2


def test_the_default_policy_produces_no_import_error() -> None:
    assert check_policy_imports(None) == []


@pytest.mark.parametrize(
    "dotted",
    [
        "nowhere.Missing",
        "freedom_ls.deadlines.config.DeadlinesConfig",
        "freedom_ls.not_installed.policy.Policy",
    ],
)
def test_a_policy_path_that_is_not_a_policy_class_produces_an_error(dotted) -> None:
    with override_settings(DEADLINE_POLICY=dotted):
        errors = check_policy_imports(None)

    assert [error.id for error in errors] == ["freedom_ls_deadlines.E002"]
