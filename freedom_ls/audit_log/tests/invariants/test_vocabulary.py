"""The names of changes: one `noun.verb` vocabulary shared by audit actions
and webhook event types, as the domain glossary's "Changes" section lays it
out. A code outside these sets is a new word, and the glossary is where a new
word is agreed first."""

from freedom_ls.audit_log.actions import FLS_AUDIT_ACTIONS
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
        "member",
        "user",
        "course",
        "bulk_action",
        "import",
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
    }
)

# Verbs that may carry a qualifier before them, as in `setup_email_resent`.
QUALIFIED_VERBS = frozenset({"setup_email_resent"})

#: Events integrators hear about that no audit entry records.
WEBHOOK_ONLY = frozenset({"user.signed_up", "course.completed"})


def _split(code: str) -> tuple[str, str]:
    noun, verb = code.split(".")
    return noun, verb


def test_every_audit_action_uses_a_glossary_noun_and_verb():
    for action in FLS_AUDIT_ACTIONS:
        noun, verb = _split(action.code)
        assert noun in NOUNS, action.code
        assert verb in VERBS or verb in QUALIFIED_VERBS, action.code


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
    for code in [a.code for a in FLS_AUDIT_ACTIONS] + [
        c for c, _ in FLS_WEBHOOK_EVENT_TYPES
    ]:
        assert not any(word in code for word in retired), code
