import re

import pytest

from freedom_ls.audit_log.actions import (
    FLS_AUDIT_ACTIONS,
    SUMMARY_ACTIONS,
    get_audit_action,
    validate_action,
)


def test_get_audit_action_returns_the_registered_action():
    action = get_audit_action("learner.deactivated")

    assert (action.code, action.label) == ("learner.deactivated", "Learner deactivated")


def test_get_audit_action_falls_back_to_a_label_of_the_code():
    action = get_audit_action("widget.exploded")

    assert (action.code, action.label, action.describe) == (
        "widget.exploded",
        "widget.exploded",
        None,
    )


def test_every_fls_code_is_noun_dot_verb():
    for action in FLS_AUDIT_ACTIONS:
        assert re.fullmatch(r"[a-z_]+\.[a-z_]+", action.code), action.code


def test_fls_codes_are_unique():
    codes = [action.code for action in FLS_AUDIT_ACTIONS]

    assert len(codes) == len(set(codes))


def test_summary_actions_are_registered():
    assert {a.code for a in FLS_AUDIT_ACTIONS} >= SUMMARY_ACTIONS


def test_validate_action_names_the_valid_codes_for_an_unknown_one():
    with pytest.raises(ValueError, match="learner\\.added"):
        validate_action("widget.exploded")
