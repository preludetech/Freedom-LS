"""Every action with a reason field validates it through ReasonMixin.

ReasonMixin.handle_submit is the one place the posted reason is cleaned and
put on the context; an action that overrides handle_submit itself, or lists
the mixin after a base that defines it, would run its submit with an
unvalidated POST and an empty ctx.reason.
"""

from __future__ import annotations

from freedom_ls.panel_framework.actions import ReasonMixin


def _all_subclasses(cls: type[ReasonMixin]) -> list[type[ReasonMixin]]:
    found: list[type[ReasonMixin]] = []
    for sub in cls.__subclasses__():
        found.append(sub)
        found.extend(_all_subclasses(sub))
    return found


def test_every_reason_action_submits_through_the_mixin() -> None:
    found = _all_subclasses(ReasonMixin)
    bypassing = [
        cls.__name__
        for cls in found
        if cls.handle_submit is not ReasonMixin.handle_submit
    ]

    assert "handle_submit" in vars(ReasonMixin)
    assert bypassing == []
