import re

import pytest

from django.test import override_settings

from freedom_ls.audit_log.actions import (
    FLS_AUDIT_ACTIONS,
    SUMMARY_ACTIONS,
    get_audit_action,
    validate_action,
)
from freedom_ls.audit_log.factories import AuditLogEntryFactory
from freedom_ls.audit_log.writer import record_entry
from freedom_ls.organisations.factories import OrganisationFactory


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


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("action", "details", "expected"),
    [
        ("cohort_membership.added", {"cohort": "Year 10"}, "Year 10"),
        ("cohort_membership.removed", {"cohort": "Year 10"}, "Year 10"),
        (
            "cohort_membership.moved",
            {"source": "A", "destination": "B"},
            "From A to B",
        ),
        (
            "learner.added",
            {"outcome": "created"},
            "Account created and setup email sent",
        ),
        ("learner.added", {"outcome": "joined"}, "Joined the organisation"),
        ("learner.added", {"outcome": "reactivated"}, "Reactivated"),
        (
            "learner.added",
            {"outcome": "joined", "cohort": "Year 10"},
            "Joined the organisation, added to Year 10",
        ),
    ],
)
def test_membership_actions_describe_themselves_from_their_details(
    mock_site_context, action, details, expected
):
    entry = AuditLogEntryFactory(action=action, details=details)

    assert entry.description == expected


@pytest.mark.django_db
def test_record_entry_accepts_an_extra_action_from_settings(mock_site_context):
    organisation = OrganisationFactory()

    with override_settings(AUDIT_LOG_EXTRA_ACTIONS={"invoice.sent": "Invoice sent"}):
        entry = record_entry(
            action="invoice.sent",
            actor=None,
            target=organisation,
            target_label=organisation.name,
            organisation=organisation,
        )
        label = get_audit_action("invoice.sent").label

    assert (entry.action, label) == ("invoice.sent", "Invoice sent")


def test_an_fls_code_wins_a_collision_with_an_extra_code():
    with override_settings(AUDIT_LOG_EXTRA_ACTIONS={"cohort.created": "Mine"}):
        label = get_audit_action("cohort.created").label

    assert label == "Cohort created"
