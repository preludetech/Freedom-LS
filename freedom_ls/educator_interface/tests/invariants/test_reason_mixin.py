"""Every action with a reason field validates it through ReasonMixin.

ReasonMixin.handle_submit is the one place the posted reason is cleaned and
put on the context; an action that overrides handle_submit itself, or lists
the mixin after a base that defines it, would run its submit with an
unvalidated POST and an empty ctx.reason.
"""

from __future__ import annotations

import inspect

from freedom_ls.educator_interface import actions
from freedom_ls.educator_interface.actions import ReasonMixin


def _reason_actions() -> list[type[ReasonMixin]]:
    return [
        cls
        for _, cls in inspect.getmembers(actions, inspect.isclass)
        if issubclass(cls, ReasonMixin) and cls is not ReasonMixin
    ]


def test_every_reason_action_submits_through_the_mixin():
    found = _reason_actions()
    bypassing = [
        cls.__name__
        for cls in found
        if cls.handle_submit is not ReasonMixin.handle_submit
    ]

    assert found
    assert bypassing == []
