"""The messaging policy loader."""

from __future__ import annotations

from django.test import override_settings

from freedom_ls.comms.config import config
from freedom_ls.comms.messaging_loader import get_messaging_policy
from freedom_ls.comms.messaging_policy import MessagingPolicy


class CustomPolicy(MessagingPolicy):
    pass


def test_the_default_policy_is_the_configured_class() -> None:
    policy = get_messaging_policy()

    assert isinstance(policy, MessagingPolicy)
    assert f"{type(policy).__module__}.{type(policy).__qualname__}" == (
        config.MESSAGING_POLICY
    )


def test_an_overridden_setting_changes_the_returned_policy() -> None:
    with override_settings(MESSAGING_POLICY=f"{__name__}.CustomPolicy"):
        get_messaging_policy.cache_clear()

        policy = get_messaging_policy()

    assert type(policy) is CustomPolicy


def test_two_calls_return_the_same_instance() -> None:
    assert get_messaging_policy() is get_messaging_policy()
