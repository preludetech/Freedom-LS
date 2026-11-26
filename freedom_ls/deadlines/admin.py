from __future__ import annotations

from datetime import timedelta
from functools import partial
from zoneinfo import ZoneInfo

from unfold.admin import ModelAdmin
from unfold.contrib.filters.admin import (
    RelatedDropdownFilter,
)
from unfold.dataclasses import UnfoldAction
from unfold.decorators import action as unfold_action

from django import forms
from django.contrib import admin
from django.contrib.admin.utils import unquote
from django.contrib.auth import get_permission_codename
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.db import models
from django.http import HttpRequest, HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import URLPattern, URLResolver, path, reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from django.utils.safestring import SafeString

from freedom_ls.accounts.admin import USER_ERASURE_CASCADE_MODELS
from freedom_ls.base.date_display import days_text, display_date
from freedom_ls.deadlines.admin_views import resume_view
from freedom_ls.deadlines.consequences import access_end_instant
from freedom_ls.deadlines.loader import get_deadline_policy
from freedom_ls.deadlines.models import (
    CONFIG_FIELDS,
    LIMIT_FIELDS,
    SWITCH_FIELDS,
    CohortCourseRegistrationDeadlineConfig,
    CohortDeadlineConfig,
    CourseDeadlineConfig,
    CoursePause,
    DeadlineExtension,
    LearnerCourseRegistrationDeadlineConfig,
    OrganisationDeadlineConfig,
    SiteDeadlineConfig,
)
from freedom_ls.deadlines.resolver import (
    CourseDeadlines,
    DeadlineSource,
    ResolvedDeadline,
    course_deadlines,
)
from freedom_ls.learner_management.admin_forms import (
    CohortRegistrationPickerAdmin,
    LearnerRegistrationPickerForm,
)
from freedom_ls.learner_progress.admin import CourseProgressAdmin
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.site_aware_models.admin import (
    ReadOnlyAdminMixin,
    ReadOnlyInline,
    SiteAwareModelAdmin,
)
from freedom_ls.site_aware_models.admin_filters import InclusiveRangeDateTimeFilter
from freedom_ls.site_aware_models.forms import ConstraintValidationFormMixin
from freedom_ls.site_aware_models.time_zones import site_time_zone, site_zone_text

SOURCE_LABELS: dict[DeadlineSource, str] = {
    DeadlineSource.CONTENT: "Content default",
    DeadlineSource.COHORT_REGISTRATION: "Cohort override",
    DeadlineSource.LEARNER: "Learner override",
}


def _deadline_line(label: str, resolved: ResolvedDeadline) -> tuple[str, str, str]:
    source = SOURCE_LABELS[resolved.source] if resolved.source is not None else ""
    text = site_zone_text(resolved.due_at) if resolved.due_at else ""
    if resolved.shift_days:
        text += f" (+{days_text(resolved.shift_days)})"
    return (label, text, source)


def _paused_line(pause: CoursePause | None, tz: ZoneInfo) -> SafeString:
    if pause is None:
        return format_html("{}", "")
    text = f"Paused since {site_zone_text(pause.started_at.astimezone(tz))}"
    # The pause shown is the open one, so it ends on its planned resume day, a date.
    if pause.planned_resume_on is not None:
        text += f", until {display_date(pause.planned_resume_on)}"
    return format_html("<p>{}</p>", text)


_DEADLINES_ATTR = "_admin_course_deadlines"


def _record_deadlines(record: CourseProgress) -> CourseDeadlines:
    """The record's resolved deadlines, resolved once per instance: the change page renders
    each read-only field several times and two of them read the deadlines."""
    cached = record.__dict__.get(_DEADLINES_ATTR)
    if isinstance(cached, CourseDeadlines):
        return cached
    deadlines = course_deadlines(record, include_retired=True)
    record.__dict__[_DEADLINES_ATTR] = deadlines
    return deadlines


@admin.display(description="Effective deadlines")
def effective_deadlines(model_admin: ModelAdmin, record: CourseProgress) -> SafeString:
    """Every collection item with a deadline, its due instant in the site zone and its source,
    then the time limit end; one line each, built from the same resolver the learner sees.
    Titles are author text, so every line goes through format_html."""
    if record._state.adding:
        return format_html("{}", "")
    deadlines = _record_deadlines(record)
    lines: list[tuple[str, str, str]] = []
    for item in record.course.viewable_collection_items(include_retired=True):
        resolved = deadlines.items.get(item.pk)
        if resolved is None or resolved.due_at is None:
            continue
        title = item.child.title if item.child is not None else str(item.pk)
        lines.append(_deadline_line(title, resolved))
    if deadlines.time_limit.due_at is not None:
        lines.append(_deadline_line("Course time limit end", deadlines.time_limit))
    paused = _paused_line(deadlines.pause, deadlines.zone)
    if not lines:
        return format_html("{}<p>{}</p>", paused, "No deadlines.")
    return format_html(
        "{}<ul>{}</ul>",
        paused,
        format_html_join("", "<li>{}: {} ({})</li>", lines),
    )


def _policy_value_text(field: str, value: bool | int | timedelta | str) -> str:
    if isinstance(value, bool):
        return "On" if value else "Off"
    if isinstance(value, int):
        return "No limit" if value == 0 and field in LIMIT_FIELDS else str(value)
    if isinstance(value, timedelta):
        return str(value)
    return value.replace("_", " ").capitalize()


@admin.display(description="Effective deadline policy")
def effective_deadline_policy(
    model_admin: ModelAdmin, record: CourseProgress
) -> SafeString:
    """Each setting, its resolved value and the layer that set it, from the same resolver
    the learner pages read. Values are plain text, so every line goes through format_html."""
    if record._state.adding:
        return format_html("{}", "")
    policy = get_deadline_policy().resolve(record)
    lines = [
        (
            field,
            _policy_value_text(field, getattr(policy, field)),
            policy.sources[field],
        )
        for field in CONFIG_FIELDS
    ]
    ends_at = access_end_instant(_record_deadlines(record).time_limit, policy)
    ends_line = (
        format_html("<li>Access ends: {}</li>", site_zone_text(ends_at))
        if ends_at is not None
        else ""
    )
    return format_html(
        "<ul>{}{}</ul>",
        format_html_join("", "<li>{}: {} ({})</li>", lines),
        ends_line,
    )


class CoursePauseInline(ReadOnlyInline):
    """A record's pauses, newest first. Read-only: a pause is started and ended by the pause
    and resume services, which write the audit entry and the webhook with it. Staff resume an
    open pause from its own page in the pause admin."""

    model = CoursePause
    fields = [
        "started_at",
        "planned_resume_on",
        "ended_at",
        "state",
        "paused_days_text",
        "reason",
        "started_by",
        "ended_by",
    ]
    readonly_fields = fields
    verbose_name = "pause"

    def get_queryset(self, request: HttpRequest) -> models.QuerySet[CoursePause]:
        rows: models.QuerySet[CoursePause] = super().get_queryset(request)
        return rows.select_related(
            "site",
            "started_by",
            "ended_by",
            "course_progress__learner__user",
            "course_progress__learner__organisation",
            "course_progress__course",
        ).order_by("-started_at")

    @admin.display(description="State")
    def state(self, obj: CoursePause) -> str:
        return (
            "Paused"
            if obj.is_open(timezone.now(), site_time_zone(obj.site))
            else "Ended"
        )

    @admin.display(description="Paused days")
    def paused_days_text(self, obj: CoursePause) -> int:
        return obj.paused_days(timezone.now(), site_time_zone(obj.site))


class PauseStateFilter(admin.SimpleListFilter):
    """Paused or ended, by the same rule the learner pages use: a pause whose planned
    resume day has begun is ended even before anything writes its end."""

    title = "state"
    parameter_name = "state"

    def lookups(
        self, request: HttpRequest, model_admin: admin.ModelAdmin
    ) -> list[tuple[str, str]]:
        return [("paused", "Paused"), ("ended", "Ended")]

    def queryset(
        self, request: HttpRequest, queryset: models.QuerySet[CoursePause]
    ) -> models.QuerySet[CoursePause]:
        if self.value() not in {"paused", "ended"}:
            return queryset
        today = (
            timezone.now()
            .astimezone(site_time_zone(Site.objects.get_current(request)))
            .date()
        )
        is_open = models.Q(ended_at__isnull=True) & (
            models.Q(planned_resume_on__isnull=True)
            | models.Q(planned_resume_on__gt=today)
        )
        return queryset.filter(is_open if self.value() == "paused" else ~is_open)


RESUME_URL_NAME = "freedom_ls_deadlines_coursepause_resume"


@admin.register(CoursePause)
class CoursePauseAdmin(ReadOnlyAdminMixin, SiteAwareModelAdmin):
    """Every pause on the site, for finding who is paused and who paused them. An open
    pause's page offers Resume, the one way to end a pause that has no planned resume day."""

    list_display = [
        "course_progress",
        "started_at",
        "planned_resume_on",
        "ended_at",
        "started_by",
        "ended_by",
    ]
    list_filter = [
        ("course_progress__course", RelatedDropdownFilter),
        PauseStateFilter,
        ("started_by", RelatedDropdownFilter),
        ("started_at", InclusiveRangeDateTimeFilter),
    ]
    list_filter_submit = True
    list_select_related = (
        "course_progress__learner__user",
        "course_progress__course",
        "started_by",
        "ended_by",
    )
    search_fields = (
        "course_progress__learner__user__email",
        "course_progress__learner__user__first_name",
        "course_progress__learner__user__last_name",
    )

    actions_detail = ["resume_course_action"]

    def has_resume_permission(
        self, request: HttpRequest, object_id: str | None = None
    ) -> bool:
        """The model's change permission, read directly: has_change_permission is always
        False, since no pause field is edited by hand."""
        opts = self.opts
        allowed: bool = request.user.has_perm(
            f"{opts.app_label}.{get_permission_codename('change', opts)}"
        )
        return allowed

    @unfold_action(
        description="Resume course",
        url_path="resume-course-action",
        permissions=["resume"],
    )
    def resume_course_action(
        self, request: HttpRequest, object_id: str
    ) -> HttpResponseRedirect:
        return redirect(reverse(f"admin:{RESUME_URL_NAME}", args=[object_id]))

    def get_urls(self) -> list[URLPattern | URLResolver]:
        return [
            path(
                "<path:object_id>/resume/",
                self.admin_site.admin_view(partial(resume_view, model_admin=self)),
                name=RESUME_URL_NAME,
            ),
            *super().get_urls(),
        ]

    def get_actions_detail(
        self, request: HttpRequest, object_id: str
    ) -> list[UnfoldAction]:
        """Resume shows only on an open pause."""
        actions: list[UnfoldAction] = super().get_actions_detail(request, object_id)
        try:
            pause = CoursePause.objects.filter(pk=unquote(object_id)).first()
        except ValidationError:
            return []
        tz = site_time_zone(Site.objects.get_current(request))
        if pause is None or not pause.is_open(timezone.now(), tz):
            return []
        return actions


class DeadlineExtensionInline(ReadOnlyInline):
    """A record's extensions, newest first. Read-only: an extension is added by the extend
    service, which writes the audit entry, the webhook and the notification with it."""

    model = DeadlineExtension
    fields = [
        "created_at",
        "target_kind",
        "collection_item",
        "days",
        "requested_date",
        "reason",
        "set_by",
    ]
    readonly_fields = fields
    verbose_name = "deadline extension"

    def get_queryset(self, request: HttpRequest) -> models.QuerySet[DeadlineExtension]:
        rows: models.QuerySet[DeadlineExtension] = super().get_queryset(request)
        return (
            rows.select_related("site", "set_by", "collection_item")
            .prefetch_related("collection_item__child")
            .order_by("-created_at")
        )


@admin.register(DeadlineExtension)
class DeadlineExtensionAdmin(ReadOnlyAdminMixin, SiteAwareModelAdmin):
    """Every extension on the site, for finding who was given more time and by whom."""

    list_display = [
        "course_progress",
        "created_at",
        "target_kind",
        "collection_item",
        "days",
        "set_by",
    ]
    list_filter = [
        ("course_progress__course", RelatedDropdownFilter),
        "target_kind",
        ("set_by", RelatedDropdownFilter),
        ("created_at", InclusiveRangeDateTimeFilter),
    ]
    list_filter_submit = True
    list_select_related = (
        "course_progress__learner__user",
        "course_progress__course",
        "collection_item",
        "set_by",
    )
    search_fields = (
        "course_progress__learner__user__email",
        "course_progress__learner__user__first_name",
        "course_progress__learner__user__last_name",
    )

    def get_queryset(self, request: HttpRequest) -> models.QuerySet[DeadlineExtension]:
        rows: models.QuerySet[DeadlineExtension] = super().get_queryset(request)
        return rows.prefetch_related("collection_item__child")


# CourseProgressAdmin's change page belongs to a lower app in docs/app_structure.md, so the
# inlines, the read-only fields and their fieldset are added from here. Each seam adds rather
# than replaces.
CourseProgressAdmin.inlines = [
    *CourseProgressAdmin.inlines,
    CoursePauseInline,
    DeadlineExtensionInline,
]
setattr(CourseProgressAdmin, "effective_deadlines", effective_deadlines)  # noqa: B010
setattr(  # noqa: B010
    CourseProgressAdmin, "effective_deadline_policy", effective_deadline_policy
)
setattr(  # noqa: B010
    CourseProgressAdmin,
    "readonly_fields",
    (
        *CourseProgressAdmin.readonly_fields,
        "effective_deadlines",
        "effective_deadline_policy",
    ),
)
setattr(  # noqa: B010
    CourseProgressAdmin,
    "fieldsets",
    (
        *CourseProgressAdmin.fieldsets,
        (
            "Deadlines",
            {"fields": ("effective_deadlines", "effective_deadline_policy")},
        ),
    ),
)


class DeadlineConfigForm(forms.ModelForm):
    """Refuses a negative grace window as an error on that field, in place of the
    database constraint's name."""

    def clean_grace_window(self) -> timedelta | None:
        grace_window: timedelta | None = self.cleaned_data["grace_window"]
        if grace_window is not None and grace_window < timedelta(0):
            raise ValidationError("The grace window cannot be negative.")
        return grace_window


class SiteDeadlineConfigForm(DeadlineConfigForm, ConstraintValidationFormMixin):
    # site is not a form field: SiteAwareModelAdmin fills it from the request before
    # validation, and un-excluding it here only lets the one-per-site constraint run.
    constraint_fields = ("site",)

    class Meta:
        model = SiteDeadlineConfig
        fields = list(CONFIG_FIELDS)


class _DeadlineConfigAdmin(SiteAwareModelAdmin):
    """Attributes every deadline config admin shares. Not registered itself."""

    form = DeadlineConfigForm
    list_display = ["__str__", *CONFIG_FIELDS]
    list_filter = list(SWITCH_FIELDS)


@admin.register(SiteDeadlineConfig)
class SiteDeadlineConfigAdmin(_DeadlineConfigAdmin):
    form = SiteDeadlineConfigForm
    list_select_related = ["site"]


@admin.register(OrganisationDeadlineConfig)
class OrganisationDeadlineConfigAdmin(_DeadlineConfigAdmin):
    list_select_related = ["organisation"]
    autocomplete_fields = ["organisation"]
    search_fields = ["organisation__name"]


@admin.register(CourseDeadlineConfig)
class CourseDeadlineConfigAdmin(_DeadlineConfigAdmin):
    list_select_related = ["course"]
    search_fields = ["course__title"]


@admin.register(CohortDeadlineConfig)
class CohortDeadlineConfigAdmin(_DeadlineConfigAdmin):
    list_select_related = ["cohort"]
    search_fields = ["cohort__name"]


@admin.register(CohortCourseRegistrationDeadlineConfig)
class CohortCourseRegistrationDeadlineConfigAdmin(
    CohortRegistrationPickerAdmin, _DeadlineConfigAdmin
):
    cohort_registration_field = "cohort_registration"
    list_select_related = ["cohort_registration__cohort", "cohort_registration__course"]
    search_fields = ["cohort_registration__cohort__name"]


class LearnerRegistrationDeadlineConfigForm(
    LearnerRegistrationPickerForm, DeadlineConfigForm
):
    learner_field = "learner_registration"


@admin.register(LearnerCourseRegistrationDeadlineConfig)
class LearnerCourseRegistrationDeadlineConfigAdmin(_DeadlineConfigAdmin):
    form = LearnerRegistrationDeadlineConfigForm
    fields = ["learner_email", "organisation", "course", *CONFIG_FIELDS]
    list_select_related = [
        "learner_registration__learner__user",
        "learner_registration__course",
    ]
    search_fields = ["learner_registration__learner__user__email"]


# A user force delete takes these rows, though their admins refuse delete.
USER_ERASURE_CASCADE_MODELS.update({CoursePause, DeadlineExtension})
