"""The messaging policy contract: the decision value and the base class."""

from __future__ import annotations

import pytest

from freedom_ls.comms.messaging_policy import (
    MessagingDecision,
    MessagingPolicy,
    MessagingRefusal,
)


def test_a_decision_cannot_be_used_as_a_boolean() -> None:
    with pytest.raises(TypeError):
        bool(MessagingDecision.allow())


def test_an_allowed_decision_with_a_reason_is_rejected() -> None:
    with pytest.raises(ValueError, match="reason"):
        MessagingDecision(allowed=True, reason=MessagingRefusal.SAME_USER)


def test_a_refusal_without_a_reason_is_rejected() -> None:
    with pytest.raises(ValueError, match="reason"):
        MessagingDecision(allowed=False)


def test_refuse_carries_its_reason() -> None:
    decision = MessagingDecision.refuse(MessagingRefusal.NO_RELATIONSHIP)

    assert (decision.allowed, decision.reason) == (
        False,
        MessagingRefusal.NO_RELATIONSHIP,
    )


def test_allow_carries_no_reason() -> None:
    decision = MessagingDecision.allow()

    assert (decision.allowed, decision.reason) == (True, None)


def test_base_can_start_is_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        MessagingPolicy().can_start(sender=None, recipient=None, site=None)


def test_base_can_reply_is_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        MessagingPolicy().can_reply(
            sender=None,
            recipient=None,
            site=None,
            conversation=None,
        )


def test_base_recipients_for_is_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        MessagingPolicy().recipients_for(sender=None, site=None)
