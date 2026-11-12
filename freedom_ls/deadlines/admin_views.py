"""Admin pages that pause, resume and extend a learner's course progress."""

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
from freedom_ls.content_engine.models import ContentCollectionItem
from freedom_ls.deadlines.actions import (
    DeadlineActionError,
    extend_deadline,
    pause_course,
    resume_course,
)
from freedom_ls.deadlines.forms import (
    ExtendDeadlineForm,
    PauseCourseForm,
    ResumeCourseForm,
)
from freedom_ls.deadlines.models import ExtensionTarget
from freedom_ls.deadlines.queries import open_pause
from freedom_ls.deadlines.resolver import course_deadlines
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.site_aware_models.admin import admin_page_context
from freedom_ls.site_aware_models.time_zones import site_time_zone, site_zone_text

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


def _extendable_targets(record: CourseProgress) -> list[tuple[str, str]]:
    """Each deadline the form can extend with its current effective date: every item that
    has one, then the time limit end."""
    deadlines = course_deadlines(record)
    targets: list[tuple[str, str]] = []
    for item in record.course.viewable_collection_items():
        resolved = deadlines.items.get(item.pk)
        if resolved is None or resolved.due_at is None:
            continue
        title = item.child.title if item.child is not None else str(item.pk)
        targets.append((title, site_zone_text(resolved.due_at)))
    if deadlines.time_limit.due_at is not None:
        targets.append(
            ("Course time limit", site_zone_text(deadlines.time_limit.due_at))
        )
    return targets


def _extended_message(
    record: CourseProgress,
    target_kind: str,
    item: ContentCollectionItem | None,
    days: int,
) -> str:
    learner, course = record.learner, record.course
    if target_kind == ExtensionTarget.COURSE:
        return f"Moved {learner}'s deadlines in {course} by {_days_text(days)}."
    deadlines = course_deadlines(record)
    if item is not None:
        target = item.child.title if item.child is not None else str(item.pk)
        due_at = deadlines.items[item.pk].due_at
    else:
        target, due_at = "the course time limit", deadlines.time_limit.due_at
    return (
        f"Extended {target} for {learner} by {_days_text(days)}. "
        f"Its deadline is now {site_zone_text(due_at) if due_at else 'none'}."
    )


def extend_view(
    request: HttpRequest, object_id: str, *, model_admin: ModelAdmin
) -> HttpResponse:
    record = _record_or_404(request, model_admin, object_id)
    learner, course = record.learner, record.course
    form = ExtendDeadlineForm(record, request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            extension = extend_deadline(
                record, actor=_actor(request), **form.cleaned_data
            )
        except DeadlineActionError as error:
            form.add_error(None, str(error))
        else:
            model_admin.message_user(
                request,
                _extended_message(
                    record,
                    extension.target_kind,
                    extension.collection_item,
                    extension.days,
                ),
            )
            return redirect(_change_url(record))
    return TemplateResponse(
        request,
        "admin/deadlines/extend_deadline.html",
        {
            "form": form,
            "record": record,
            "intro": f"Add days to a deadline for {learner} on {course}.",
            "targets": _extendable_targets(record),
            "cancel_url": _change_url(record),
            **admin_page_context(
                request, model_admin, f"Extend a deadline for {learner}"
            ),
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
