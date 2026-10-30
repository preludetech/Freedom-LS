from __future__ import annotations

from django.test import override_settings

from freedom_ls.deadlines.loader import get_deadline_policy
from freedom_ls.deadlines.policy import DeadlinePolicy, LayeredDeadlinePolicy


class CustomPolicy(DeadlinePolicy):
    pass


def test_the_default_policy_is_the_layered_policy() -> None:
    assert type(get_deadline_policy()) is LayeredDeadlinePolicy


def test_an_overridden_setting_changes_the_returned_policy() -> None:
    with override_settings(DEADLINE_POLICY=f"{__name__}.CustomPolicy"):
        get_deadline_policy.cache_clear()

        policy = get_deadline_policy()

    assert type(policy) is CustomPolicy


def test_two_calls_return_the_same_instance() -> None:
    assert get_deadline_policy() is get_deadline_policy()
