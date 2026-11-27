"""Every educator action with a reason field validates it through ReasonMixin.

ReasonMixin.handle_submit is the one place the posted reason is cleaned and
put on the context; an action that overrides handle_submit itself, or lists
the mixin after a base that defines it, would run its submit with an
unvalidated POST and an empty ctx.reason.
"""

from __future__ import annotations

import inspect

from panel_framework.actions import ReasonMixin

from freedom_ls.educator_interface.panels.cohort import actions as cohort_actions
from freedom_ls.educator_interface.panels.common import actions as common_actions
from freedom_ls.educator_interface.panels.learner import actions as learner_module
from freedom_ls.educator_interface.panels.staff import actions as staff_actions


def _reason_actions() -> set[type[ReasonMixin]]:
    return {
        cls
        for module in (cohort_actions, learner_module, staff_actions)
        for _, cls in inspect.getmembers(module, inspect.isclass)
        if issubclass(cls, ReasonMixin)
        and cls is not ReasonMixin
        and cls is not common_actions.EducatorReasonMixin
    }


def test_every_reason_action_submits_through_the_mixin() -> None:
    found = _reason_actions()
    bypassing = [
        cls.__name__
        for cls in found
        if cls.handle_submit is not ReasonMixin.handle_submit
    ]

    assert len(found) == 9
    assert bypassing == []
