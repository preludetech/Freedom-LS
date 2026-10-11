"""Template tags shared by the educator interface's templates."""

from __future__ import annotations

from django import template

from freedom_ls.educator_interface.views import learner_status_badge
from freedom_ls.learner_management.models import Learner
from freedom_ls.panel_framework.views import StatusBadge

register = template.Library()


@register.simple_tag(name="learner_status_badge")
def learner_status_badge_tag(learner: Learner) -> StatusBadge:
    """The learner's status badge, for `{% learner_status_badge learner as badge %}`."""
    return learner_status_badge(learner)
