from __future__ import annotations

from unfold.admin import TabularInline
from unfold.contrib.filters.admin import (
    RelatedDropdownFilter,
    SliderNumericFilter,
)
from unfold.decorators import display

from django.contrib import admin
from django.db import models
from django.http import HttpRequest
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from freedom_ls.accounts.admin import USER_ERASURE_CASCADE_MODELS
from freedom_ls.accounts.admin import UserAdmin as AccountsUserAdmin
from freedom_ls.accounts.models import User
from freedom_ls.form_engine.enums import FormStrategy
from freedom_ls.form_engine.models import FormProgress
from freedom_ls.learner_management.models import Learner
from freedom_ls.site_aware_models.admin import ReadOnlyAdminMixin, SiteAwareModelAdmin
from freedom_ls.site_aware_models.admin_filters import (
    CompletionListFilter,
    InclusiveRangeDateTimeFilter,
)

from .force_delete_admin import LEARNER_TARGET, USER_TARGET, ForceDeleteAdminMixin
from .models import CourseFormAttempt, CourseProgress, TopicProgress

admin.site.unregister(User)

# A user force delete takes these rows, though their admins refuse delete.
USER_ERASURE_CASCADE_MODELS.update({CourseProgress, TopicProgress, CourseFormAttempt})


@admin.register(User)
class UserAdmin(ForceDeleteAdminMixin, AccountsUserAdmin):
    """The accounts user admin plus force delete, registered here because
    force delete reaches course progress, which accounts cannot import."""

    force_delete_target = USER_TARGET
    actions = ["force_delete_selected"]
    actions_detail = ["force_delete_one"]


# A learner force delete takes the learner's rows, whose admins refuse delete.
USER_ERASURE_CASCADE_MODELS.add(Learner)


@admin.register(Learner)
class LearnerAdmin(ReadOnlyAdminMixin, ForceDeleteAdminMixin, SiteAwareModelAdmin):
    """Learners are managed in the educator interface. This admin exists to
    carry learner force delete, so it changes nothing else."""

    force_delete_target = LEARNER_TARGET
    list_display = ["email", "display_name", "organisation", "is_active", "created_at"]
    list_select_related = ["user", "organisation"]
    search_fields = ["user__email", "user__first_name", "user__last_name"]
    list_filter = [("organisation", RelatedDropdownFilter), "is_active"]
    fields = ["email", "display_name", "organisation", "is_active", "created_at"]
    readonly_fields = fields
    actions = ["force_delete_selected"]
    actions_detail = ["force_delete_one"]

    @admin.display(description="Email", ordering="user__email")
    def email(self, obj: Learner) -> str:
        return obj.user.email

    @admin.display(description="Name", ordering="user__last_name")
    def display_name(self, obj: Learner) -> str:
        return obj.user.display_name


class TopicCompletionFilter(CompletionListFilter):
    completion_field = "complete_time"


class AttemptCompletionFilter(CompletionListFilter):
    completion_field = "form_progress__completed_time"


class CourseProgressStatusFilter(CompletionListFilter):
    """Complete, not complete, or never opened.

    A record exists from registration onward, so "not complete" holds both the
    learner who is halfway through and the one who has never opened the course.
    Monitoring wants those apart, and `started_at` is what separates them.
    """

    title = _("status")
    parameter_name = "status"
    completion_field = "completed_time"

    def lookups(
        self, request: HttpRequest, model_admin: admin.ModelAdmin
    ) -> list[tuple[str, str]]:
        return [
            *super().lookups(request, model_admin),
            ("not_started", gettext("Not started")),
        ]

    def queryset(
        self, request: HttpRequest, queryset: models.QuerySet[CourseProgress]
    ) -> models.QuerySet[CourseProgress]:
        if self.value() == "not_started":
            return queryset.filter(started_at__isnull=True)
        return super().queryset(request, queryset)


def quiz_result(attempt: FormProgress) -> str | None:
    """This attempt's quiz score and verdict, or None when it has neither.

    `FormProgress.quiz_percentage` and `passed` raise ValueError for a form that
    is not a quiz, one with no pass mark set, an attempt that was never scored
    or was scored under another strategy, and a quiz with no questions. Every
    one of those is an ordinary row on these changelists, so the conditions are
    checked up front rather than caught.
    """
    form = attempt.form
    if form.strategy != FormStrategy.QUIZ or form.quiz_pass_percentage is None:
        return None
    scores = attempt.scores or {}
    if "score" not in scores or not scores.get("max_score"):
        return None
    verdict = gettext("passed") if attempt.passed() else gettext("failed")
    return f"{attempt.quiz_percentage()}% {verdict}"


class CourseProgressItemInline(ReadOnlyAdminMixin, TabularInline):
    """One kind of item a learner worked through, listed on their record.

    Read-only and paginated: a course has more items than a change page should
    render at once, each row has its own page, and a completion timestamp drives
    the record's percentage recalculation, so it must not be rewritten from here.
    """

    extra = 0
    per_page = 25
    show_count = True
    show_change_link = True
    tab = True


class CourseProgressTopicInline(CourseProgressItemInline):
    """The topics opened under this record, and which of them are finished."""

    model = TopicProgress
    fields = ["topic", "start_time", "last_accessed_time", "complete_time"]
    readonly_fields = fields
    ordering = ["-last_accessed_time"]

    verbose_name = "Topic"
    verbose_name_plural = "Topics"

    def get_queryset(self, request: HttpRequest) -> models.QuerySet[TopicProgress]:
        # Every row renders its topic, and the row title renders it again.
        records: models.QuerySet[TopicProgress] = super().get_queryset(request)
        return records.select_related("topic")


class CourseProgressFormAttemptInline(CourseProgressItemInline):
    """The forms sat under this record, with each attempt's outcome."""

    model = CourseFormAttempt
    fields = ["form_title", "started_at", "finished_at", "result"]
    readonly_fields = fields
    ordering = ["-form_progress__start_time"]

    verbose_name = "Form attempt"
    verbose_name_plural = "Form attempts"

    def get_queryset(self, request: HttpRequest) -> models.QuerySet[CourseFormAttempt]:
        attempts: models.QuerySet[CourseFormAttempt] = super().get_queryset(request)
        return attempts.select_related("form_progress__form")

    @admin.display(description="Form")
    def form_title(self, obj: CourseFormAttempt) -> str:
        return str(obj.form_progress.form)

    @admin.display(description="Started")
    def started_at(self, obj: CourseFormAttempt) -> object:
        return obj.form_progress.start_time

    @admin.display(description="Completed")
    def finished_at(self, obj: CourseFormAttempt) -> object:
        return obj.form_progress.completed_time

    @admin.display(description="Result")
    def result(self, obj: CourseFormAttempt) -> str | None:
        return quiz_result(obj.form_progress)


@admin.register(TopicProgress)
class TopicProgressAdmin(ReadOnlyAdminMixin, SiteAwareModelAdmin):
    list_display = [
        "learner",
        "course_progress",
        "collection_item",
        "topic",
        "start_time",
        "last_accessed_time",
        "complete_time",
        "is_complete",
    ]
    list_filter = [
        TopicCompletionFilter,
        ("topic", RelatedDropdownFilter),
        ("course_progress__course", RelatedDropdownFilter),
        ("course_progress__learner__organisation", RelatedDropdownFilter),
        ("course_progress__cohort_registration__cohort", RelatedDropdownFilter),
        ("complete_time", InclusiveRangeDateTimeFilter),
    ]
    # The date and range filters only narrow anything once they are applied.
    list_filter_submit = True
    date_hierarchy = "complete_time"
    search_fields = ("course_progress__learner__user__email", "topic__title")
    ordering = ("-last_accessed_time",)
    readonly_fields = ("start_time", "last_accessed_time")
    list_select_related = (
        "course_progress__learner__user",
        "course_progress__course",
        "collection_item",
        "topic",
    )

    fieldsets = (
        (None, {"fields": ("course_progress", "collection_item", "topic")}),
        (
            "Progress",
            {"fields": ("start_time", "last_accessed_time", "complete_time")},
        ),
    )

    @admin.display(
        description="Learner", ordering="course_progress__learner__user__email"
    )
    def learner(self, obj: TopicProgress) -> str:
        return str(obj.course_progress.learner)

    @admin.display(boolean=True, description="Complete")
    def is_complete(self, obj: TopicProgress) -> bool:
        return obj.complete_time is not None


@admin.register(CourseProgress)
class CourseProgressAdmin(ReadOnlyAdminMixin, SiteAwareModelAdmin):
    list_display = [
        "learner",
        "course",
        "status",
        "progress_percentage",
        "learner_registration",
        "cohort_registration",
        "created_at",
        "started_at",
        "last_accessed_time",
        "completed_time",
    ]
    list_filter = [
        CourseProgressStatusFilter,
        ("course", RelatedDropdownFilter),
        ("learner__organisation", RelatedDropdownFilter),
        ("cohort_registration__cohort", RelatedDropdownFilter),
        ("progress_percentage", SliderNumericFilter),
        ("completed_time", InclusiveRangeDateTimeFilter),
        ("last_accessed_time", InclusiveRangeDateTimeFilter),
    ]
    list_filter_submit = True
    date_hierarchy = "created_at"
    search_fields = ("learner__user__email", "course__title")
    ordering = ("-created_at",)
    # created_at is auto_now_add; last_accessed_time is written by the player,
    # so editing either by hand would only ever misreport what happened.
    readonly_fields = ("created_at", "last_accessed_time")
    list_select_related = (
        "learner__user",
        "course",
        "learner_registration__course",
        "cohort_registration__cohort",
    )
    inlines = [CourseProgressTopicInline, CourseProgressFormAttemptInline]

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "learner",
                    "course",
                    "learner_registration",
                    "cohort_registration",
                )
            },
        ),
        (
            "Progress",
            {
                "fields": (
                    "created_at",
                    "started_at",
                    "last_accessed_time",
                    "last_accessed_item",
                    "completed_time",
                    "progress_percentage",
                )
            },
        ),
    )

    @display(
        description="Status",
        ordering="completed_time",
        label={"complete": "success", "in_progress": "info", "not_started": "warning"},
    )
    def status(self, obj: CourseProgress) -> tuple[str, str]:
        # The first half picks the badge colour, the second is what it reads.
        if obj.completed_time is not None:
            return "complete", gettext("Complete")
        if obj.started_at is None:
            return "not_started", gettext("Not started")
        return "in_progress", gettext("In progress")


@admin.register(CourseFormAttempt)
class CourseFormAttemptAdmin(ReadOnlyAdminMixin, SiteAwareModelAdmin):
    """The course side of an attempt. The attempt itself is viewed in form_engine."""

    # `form` and `start_time` would shadow ModelAdmin.form and the attempt's own
    # field names, so the display callables carry their own names.
    list_display = [
        "learner",
        "course_progress",
        "collection_item",
        "form_title",
        "started_at",
        "finished_at",
        "result",
        "is_complete",
    ]
    list_filter = [
        AttemptCompletionFilter,
        ("form_progress__form", RelatedDropdownFilter),
        ("course_progress__course", RelatedDropdownFilter),
        ("course_progress__learner__organisation", RelatedDropdownFilter),
        ("course_progress__cohort_registration__cohort", RelatedDropdownFilter),
        ("form_progress__completed_time", InclusiveRangeDateTimeFilter),
    ]
    list_filter_submit = True
    search_fields = (
        "course_progress__learner__user__email",
        "form_progress__form__title",
    )
    ordering = ("-form_progress__start_time",)
    # Each row renders its record, its learner and the attempt's form, so the
    # changelist would otherwise issue three queries per row.
    list_select_related = (
        "course_progress__learner__user",
        "course_progress__course",
        "collection_item",
        "form_progress__form",
    )

    @admin.display(
        description="Learner", ordering="course_progress__learner__user__email"
    )
    def learner(self, obj: CourseFormAttempt) -> str:
        return str(obj.course_progress.learner)

    @admin.display(description="Form")
    def form_title(self, obj: CourseFormAttempt) -> str:
        return str(obj.form_progress.form)

    @admin.display(description="Started")
    def started_at(self, obj: CourseFormAttempt) -> object:
        return obj.form_progress.start_time

    @admin.display(description="Completed")
    def finished_at(self, obj: CourseFormAttempt) -> object:
        return obj.form_progress.completed_time

    @admin.display(description="Result")
    def result(self, obj: CourseFormAttempt) -> str | None:
        return quiz_result(obj.form_progress)

    @admin.display(boolean=True, description="Complete")
    def is_complete(self, obj: CourseFormAttempt) -> bool:
        return obj.form_progress.completed_time is not None
