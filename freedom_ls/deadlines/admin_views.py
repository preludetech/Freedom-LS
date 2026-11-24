"""The admin page that resumes a learner's paused course."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import formats, timezone

from freedom_ls.accounts.models import User
from freedom_ls.base.date_display import DATE_DISPLAY_FORMAT, days_text
from freedom_ls.deadlines.actions import DeadlineActionError, resume_course
from freedom_ls.deadlines.forms import ResumeCourseForm
from freedom_ls.deadlines.models import CoursePause
from freedom_ls.site_aware_models.admin import admin_page_context
from freedom_ls.site_aware_models.time_zones import site_time_zone

if TYPE_CHECKING:
    from freedom_ls.deadlines.admin import CoursePauseAdmin

NOT_PAUSED = "No change: this course is not paused."


def _change_url(pause: CoursePause) -> str:
    return reverse("admin:freedom_ls_deadlines_coursepause_change", args=[pause.pk])


def resume_view(
    request: HttpRequest, object_id: str, *, model_admin: CoursePauseAdmin
) -> HttpResponse:
    # The permission is checked here: the URL can be typed by hand.
    if not model_admin.has_resume_permission(request):
        raise PermissionDenied
    # The admin queryset is the host site's, so another site's pause is a 404.
    pause: CoursePause = get_object_or_404(
        model_admin.get_queryset(request).select_related(
            "course_progress__learner__user", "course_progress__course", "site"
        ),
        pk=object_id,
    )
    record = pause.course_progress
    learner, course = record.learner, record.course
    now = timezone.now()
    tz = site_time_zone(pause.site)
    if not pause.is_open(now, tz):
        return _not_paused(request, model_admin, pause)
    form = ResumeCourseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            resumed = resume_course(
                record, actor=cast(User, request.user), now=now, **form.cleaned_data
            )
        except DeadlineActionError as error:
            form.add_error(None, str(error))
        else:
            if resumed is None:
                return _not_paused(request, model_admin, pause)
            days = days_text(resumed.paused_days(now, tz))
            model_admin.message_user(
                request, f"Resumed {learner} on {course}. Deadlines moved by {days}."
            )
            return redirect(_change_url(pause))
    since = formats.date_format(
        pause.started_at.astimezone(tz).date(), DATE_DISPLAY_FORMAT
    )
    intro = (
        f"Paused since {since}. Resuming moves the time limit and every unmet "
        f"deadline forward by {days_text(pause.paused_days(now, tz))}."
    )
    return TemplateResponse(
        request,
        "admin/deadlines/resume_course.html",
        {
            "form": form,
            "intro": intro,
            "cancel_url": _change_url(pause),
            **admin_page_context(request, model_admin, f"Resume {learner} on {course}"),
        },
    )


def _not_paused(
    request: HttpRequest, model_admin: CoursePauseAdmin, pause: CoursePause
) -> HttpResponse:
    model_admin.message_user(request, NOT_PAUSED, level=messages.WARNING)
    return redirect(_change_url(pause))
