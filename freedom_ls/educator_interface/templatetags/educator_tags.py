"""Template tags shared by the educator interface's templates."""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import cast
from uuid import UUID

from django import template

from freedom_ls.content_engine.models import Course
from freedom_ls.educator_interface.avatars import PersonAvatar
from freedom_ls.educator_interface.panels.common.report import (
    flag_badge,
    progress_status_badge,
)
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
)
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


@register.simple_tag(takes_context=True, name="course_shared_by")
def course_shared_by_tag(context: template.Context, course: Course) -> str | None:
    """The other organisations that own `course`, as the request's organisation
    sees it, for `{% course_shared_by course as sharers %}`."""
    organisation = cast(OrganisationScopedRequest, context["request"]).organisation
    return course.shared_by(organisation)


@register.simple_tag(takes_context=True, name="course_label")
def course_label_tag(context: template.Context, course: Course) -> str:
    """The course's title with its other owners in brackets, as the request's
    organisation sees it, for `{% course_label course as label %}`."""
    organisation = cast(OrganisationScopedRequest, context["request"]).organisation
    return course.label_for(organisation)


@dataclasses.dataclass(frozen=True)
class RowAvatar:
    """An id-only row's avatar, ready to bind: the colour key as a plain
    (never localized) string, and the picture URL, empty for initials."""

    user_id: str
    picture_url: str


@register.simple_tag(name="learner_avatar")
def learner_avatar_tag(avatars: object, learner_id: UUID) -> RowAvatar:
    """The avatar for a row that holds only a learner id, for
    `{% learner_avatar avatars row.learner_id as avatar %}`.

    `avatars` maps learner id to PersonAvatar. An unresolved learner, or no
    `avatars` in the context at all, gives the learner id as the colour key
    and initials.
    """
    avatar = avatars.get(learner_id) if isinstance(avatars, Mapping) else None
    if not isinstance(avatar, PersonAvatar):
        return RowAvatar(str(learner_id), "")
    return RowAvatar(str(avatar.user_pk), avatar.picture_url or "")
