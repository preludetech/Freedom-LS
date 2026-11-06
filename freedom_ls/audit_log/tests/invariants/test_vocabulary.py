"""The names of changes: one `noun.verb` vocabulary shared by audit actions
and webhook event types, as the domain glossary's "Changes" section lays it
out. A code outside these sets is a new word, and the glossary is where a new
word is agreed first."""

from freedom_ls.audit_log.actions import AUDIT_ACTION_GROUPS, FLS_AUDIT_ACTIONS
from freedom_ls.base.webhook_event_types import (
    FLS_WEBHOOK_EVENT_TYPES,
    WEBHOOK_EVENT_TYPE_SAMPLES,
)

NOUNS = frozenset(
    {
        "learner",
        "cohort",
        "cohort_membership",
        "registration",
        "cohort_registration",
        "role",
        "staff_member",
        "user",
        "course",
        "bulk_action",
        "import",
        "conversation",
        "api_key",
    }
)

VERBS = frozenset(
    {
        "created",
        "added",
        "deactivated",
        "reactivated",
        "removed",
        "deleted",
        "assigned",
        "moved",
        "renamed",
        "resent",
        "completed",
        "committed",
        "signed_up",
        "viewed",
        "issued",
        "revoked",
    }
)

# Verbs that may carry a qualifier before them, as in `setup_email_resent`.
QUALIFIED_VERBS = frozenset({"setup_email_resent"})

#: Events integrators hear about that no audit entry records.
WEBHOOK_ONLY = frozenset({"user.signed_up", "course.completed"})


#: The "What" filter's heading for each noun, so a new action lands with its kind.
NOUN_GROUPS = {
    "learner": "Learners",
    "cohort_membership": "Cohort membership",
    "registration": "Course registrations",
    "cohort": "Cohorts",
    "cohort_registration": "Cohorts",
    "role": "Staff and roles",
    "staff_member": "Staff and roles",
}


def _split(code: str) -> tuple[str, str]:
    noun, verb = code.split(".")
    return noun, verb


def test_every_audit_action_uses_a_glossary_noun_and_verb():
    for action in FLS_AUDIT_ACTIONS:
        noun, verb = _split(action.code)
        assert noun in NOUNS, action.code
        assert verb in VERBS or verb in QUALIFIED_VERBS, action.code


def test_every_audit_action_belongs_to_a_named_group():
    for action in FLS_AUDIT_ACTIONS:
        assert action.group in AUDIT_ACTION_GROUPS, action.code


def test_an_actions_group_follows_its_noun():
    for action in FLS_AUDIT_ACTIONS:
        noun, _verb = _split(action.code)
        assert action.group == NOUN_GROUPS.get(noun, "Other"), action.code


def test_every_webhook_event_type_uses_a_glossary_noun_and_verb():
    for code, _label in FLS_WEBHOOK_EVENT_TYPES:
        noun, verb = _split(code)
        assert noun in NOUNS, code
        assert verb in VERBS, code


def test_a_webhook_event_type_shared_with_the_audit_log_is_the_same_string_and_label():
    audit_labels = {action.code: action.label for action in FLS_AUDIT_ACTIONS}
    shared = [
        (code, label)
        for code, label in FLS_WEBHOOK_EVENT_TYPES
        if code not in WEBHOOK_ONLY
    ]

    assert shared, "every change that fires a webhook is also audited"
    for code, label in shared:
        assert code in audit_labels, code
        assert label == audit_labels[code], code


def test_webhook_only_event_types_are_exactly_the_ones_listed():
    audit_codes = {action.code for action in FLS_AUDIT_ACTIONS}
    webhook_only = {code for code, _ in FLS_WEBHOOK_EVENT_TYPES} - audit_codes

    assert webhook_only == WEBHOOK_ONLY


def test_every_webhook_event_type_has_a_sample_payload():
    assert {code for code, _ in FLS_WEBHOOK_EVENT_TYPES} == set(
        WEBHOOK_EVENT_TYPE_SAMPLES
    )


def test_no_code_uses_a_word_the_glossary_has_retired():
    retired = ("unregister", "suspend", "revoke", "granted", "reregister")
    # The one-way end of an API key, agreed in the glossary.
    allowed_verbs = {"revoked"}
    codes = [a.code for a in FLS_AUDIT_ACTIONS] + [
        c for c, _ in FLS_WEBHOOK_EVENT_TYPES
    ]
    offending = [
        code
        for code in codes
        if _split(code)[1] not in allowed_verbs
        and any(word in code for word in retired)
    ]
    assert offending == []
