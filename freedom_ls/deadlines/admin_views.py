"""Admin pages that pause and resume a learner's course progress."""

from __future__ import annotations

from typing import cast

from django.contrib import messages
from django.contrib.admin import ModelAdmin
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import formats, timezone
from django.utils.translation import ngettext

from freedom_ls.accounts.models import User
from freedom_ls.base.date_display import DATE_DISPLAY_FORMAT
from freedom_ls.deadlines.actions import (
    DeadlineActionError,
    pause_course,
    resume_course,
)
from freedom_ls.deadlines.forms import PauseCourseForm, ResumeCourseForm
from freedom_ls.deadlines.queries import open_pause
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.site_aware_models.admin import admin_page_context
from freedom_ls.site_aware_models.time_zones import site_time_zone

NOT_PAUSED = "No change: this course is not paused."


def _record_or_404(
    request: HttpRequest, model_admin: ModelAdmin, object_id: str
) -> CourseProgress:
    # The change permission is checked here: the URL can be typed by hand.
    if not model_admin.has_change_permission(request):
        raise PermissionDenied
    # The admin queryset is the host site's, so another site's record is a 404.
    record: CourseProgress = get_object_or_404(
        model_admin.get_queryset(request).select_related(
            "learner__user", "course", "site"
        ),
        pk=object_id,
    )
    return record


def _change_url(record: CourseProgress) -> str:
    return reverse(
        "admin:freedom_ls_learner_progress_courseprogress_change", args=[record.pk]
    )


def _days_text(days: int) -> str:
    return ngettext("%(count)d day", "%(count)d days", days) % {"count": days}


def pause_view(
    request: HttpRequest, object_id: str, *, model_admin: ModelAdmin
) -> HttpResponse:
    record = _record_or_404(request, model_admin, object_id)
    learner, course = record.learner, record.course
    form = PauseCourseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            pause_course(record, actor=_actor(request), **form.cleaned_data)
        except DeadlineActionError as error:
            form.add_error(None, str(error))
        else:
            model_admin.message_user(request, f"Paused {learner} on {course}.")
            return redirect(_change_url(record))
    intro = (
        f"{learner} can open this course now. After pausing, nothing in it can be "
        "opened; past results stay visible."
    )
    return TemplateResponse(
        request,
        "admin/deadlines/pause_course.html",
        {
            "form": form,
            "record": record,
            "intro": intro,
            "cancel_url": _change_url(record),
            **admin_page_context(request, model_admin, f"Pause {learner} on {course}"),
        },
    )


def resume_view(
    request: HttpRequest, object_id: str, *, model_admin: ModelAdmin
) -> HttpResponse:
    record = _record_or_404(request, model_admin, object_id)
    learner, course = record.learner, record.course
    now = timezone.now()
    tz = site_time_zone(record.site)
    pause = open_pause(record, now)
    if pause is None:
        return _not_paused(request, model_admin, record)
    form = ResumeCourseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            resumed = resume_course(
                record, actor=_actor(request), now=now, **form.cleaned_data
            )
        except DeadlineActionError as error:
            form.add_error(None, str(error))
        else:
            if resumed is None:
                return _not_paused(request, model_admin, record)
            days = _days_text(resumed.paused_days(now, tz))
            model_admin.message_user(
                request, f"Resumed {learner} on {course}. Deadlines moved by {days}."
            )
            return redirect(_change_url(record))
    since = formats.date_format(
        pause.started_at.astimezone(tz).date(), DATE_DISPLAY_FORMAT
    )
    intro = (
        f"Paused since {since}. Resuming moves the time limit and every unmet "
        f"deadline forward by {_days_text(pause.paused_days(now, tz))}."
    )
    return TemplateResponse(
        request,
        "admin/deadlines/resume_course.html",
        {
            "form": form,
            "record": record,
            "intro": intro,
            "cancel_url": _change_url(record),
            **admin_page_context(request, model_admin, f"Resume {learner} on {course}"),
        },
    )


def _not_paused(
    request: HttpRequest, model_admin: ModelAdmin, record: CourseProgress
) -> HttpResponse:
    model_admin.message_user(request, NOT_PAUSED, level=messages.WARNING)
    return redirect(_change_url(record))


def _actor(request: HttpRequest) -> User:
    # admin_view only lets a signed-in staff user reach these pages.
    return cast(User, request.user)
