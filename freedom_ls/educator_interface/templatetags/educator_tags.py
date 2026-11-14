"""Template tags shared by the educator interface's templates."""

from __future__ import annotations

from django import template

from freedom_ls.educator_interface.reporting import flag_badge, progress_status_badge
from freedom_ls.educator_interface.views import (
    LearnerCourseSummary,
    learner_course_summaries,
)
from freedom_ls.learner_management.models import Learner
from freedom_ls.panel_framework.views import StatusBadge
from freedom_ls.reports.report_data import AtRiskFlag

register = template.Library()


@register.simple_tag(name="progress_status_badge")
def progress_status_badge_tag(completion_percentage: int) -> StatusBadge:
    """The progress status badge, for `{% progress_status_badge completion as badge %}`."""
    return progress_status_badge(completion_percentage)


@register.simple_tag(name="flag_badge")
def flag_badge_tag(flag: AtRiskFlag) -> StatusBadge:
    """The at-risk flag badge, for `{% flag_badge flag as badge %}`."""
    return flag_badge(flag)


@register.simple_tag(name="learner_course_summaries")
def learner_course_summaries_tag(learner: Learner) -> list[LearnerCourseSummary]:
    """The learner's courses with progress, for `{% learner_course_summaries object as summaries %}`."""
    return learner_course_summaries(learner)


@register.simple_tag(name="passed_badge")
def passed_badge_tag(passed: bool) -> StatusBadge:
    """The Passed or Failed badge for a quiz attempt that has a verdict, for `{% passed_badge attempt.passed as badge %}`."""
    return (
        StatusBadge("success", "Passed") if passed else StatusBadge("error", "Failed")
    )
