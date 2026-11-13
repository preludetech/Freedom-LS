from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING, cast
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, QuerySet

from freedom_ls.content_engine.models import ContentCollectionItem, Course
from freedom_ls.deadlines import shifts
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    LearnerCourseRegistration,
)
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.organisations.models import Organisation
from freedom_ls.site_aware_models.models import (
    SiteAwareManager,
    SiteAwareModel,
    TimestampedModel,
)
from freedom_ls.site_aware_models.time_zones import site_time_zone

if TYPE_CHECKING:
    from freedom_ls.deadlines.resolver import DeadlineValue


class DeadlineKind(models.TextChoices):
    FIXED = "fixed", "Fixed date"
    RELATIVE = "relative", "Days after registration"
    NONE = "none", "No deadline"


def _validate_deadline_override(
    kind: str,
    due_date: date | None,
    due_time: time | None,
    due_days_after_registration: int | None,
    collection_item: ContentCollectionItem | None,
    course: Course,
) -> None:
    """The shape rules every override row obeys, raised as one ValidationError."""
    errors: dict[str, str] = {}
    if kind == DeadlineKind.FIXED:
        if due_date is None:
            errors["due_date"] = "A fixed deadline needs a date."
        if due_days_after_registration is not None:
            errors["due_days_after_registration"] = "A fixed deadline takes no days."
    if kind == DeadlineKind.RELATIVE:
        if due_days_after_registration is None:
            errors["due_days_after_registration"] = (
                "A relative deadline needs a number of days."
            )
        if due_date is not None:
            errors["due_date"] = "A relative deadline takes no date."
    if kind == DeadlineKind.NONE and (
        due_date or due_time or due_days_after_registration is not None
    ):
        errors["kind"] = "No deadline takes no date, time or days."
    if collection_item is None:
        if due_time is not None:
            errors["due_time"] = "The course time limit ends at the end of its day."
    elif collection_item not in course.viewable_collection_items():
        errors["collection_item"] = "Pick an item of this course."
    if errors:
        raise ValidationError(errors)


class CohortDeadlineOverride(SiteAwareModel, TimestampedModel):
    """A deadline set for every learner registered for a course through a cohort."""

    cohort_registration = models.ForeignKey(
        CohortCourseRegistration,
        on_delete=models.CASCADE,
        related_name="deadline_overrides",
    )
    collection_item = models.ForeignKey(
        ContentCollectionItem,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="+",
    )
    kind = models.CharField(max_length=8, choices=DeadlineKind.choices)
    due_date = models.DateField(
        null=True, blank=True, help_text="Read in the site's time zone."
    )
    due_time = models.TimeField(null=True, blank=True)
    due_days_after_registration = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="days after registration"
    )
    replaced_value = models.CharField(max_length=64, blank=True)
    set_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    reason = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["cohort_registration", "collection_item"],
                condition=Q(collection_item__isnull=False),
                name="unique_cohort_override_per_item",
            ),
            models.UniqueConstraint(
                fields=["cohort_registration"],
                condition=Q(collection_item__isnull=True),
                name="unique_cohort_time_limit_override",
            ),
        ]
        verbose_name = "deadline override"

    @property
    def course(self) -> Course | None:
        # The parent is unset while the admin add page is still being validated.
        return self.cohort_registration.course if self.cohort_registration_id else None

    def value(self) -> DeadlineValue:
        from freedom_ls.deadlines.resolver import DeadlineValue

        return DeadlineValue(
            DeadlineKind(self.kind),
            self.due_date,
            self.due_time,
            self.due_days_after_registration,
        )

    def clean(self) -> None:
        course = self.course
        if course is None:
            return
        _validate_deadline_override(
            self.kind,
            self.due_date,
            self.due_time,
            self.due_days_after_registration,
            self.collection_item,
            course,
        )


class LearnerDeadlineOverride(SiteAwareModel, TimestampedModel):
    """A deadline set for one learner's progress on a course. It beats a cohort override and
    the content default."""

    course_progress = models.ForeignKey(
        CourseProgress,
        on_delete=models.CASCADE,
        related_name="deadline_overrides",
    )
    collection_item = models.ForeignKey(
        ContentCollectionItem,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="+",
    )
    kind = models.CharField(max_length=8, choices=DeadlineKind.choices)
    due_date = models.DateField(
        null=True, blank=True, help_text="Read in the site's time zone."
    )
    due_time = models.TimeField(null=True, blank=True)
    due_days_after_registration = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="days after registration"
    )
    replaced_value = models.CharField(max_length=64, blank=True)
    set_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    reason = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["course_progress", "collection_item"],
                condition=Q(collection_item__isnull=False),
                name="unique_learner_override_per_item",
            ),
            models.UniqueConstraint(
                fields=["course_progress"],
                condition=Q(collection_item__isnull=True),
                name="unique_learner_time_limit_override",
            ),
        ]
        verbose_name = "deadline override"

    @property
    def course(self) -> Course | None:
        # The parent is unset while the admin add page is still being validated.
        return self.course_progress.course if self.course_progress_id else None

    def value(self) -> DeadlineValue:
        from freedom_ls.deadlines.resolver import DeadlineValue

        return DeadlineValue(
            DeadlineKind(self.kind),
            self.due_date,
            self.due_time,
            self.due_days_after_registration,
        )

    def clean(self) -> None:
        course = self.course
        if course is None:
            return
        _validate_deadline_override(
            self.kind,
            self.due_date,
            self.due_time,
            self.due_days_after_registration,
            self.collection_item,
            course,
        )


class DeadlineSwitch(models.TextChoices):
    INHERIT = "inherit", "Inherit"
    ON = "on", "On"
    OFF = "off", "Off"


class AfterAccessEnded(models.TextChoices):
    INHERIT = "inherit", "Inherit"
    OUTLINE_AND_RESULTS = "outline_and_results", "Outline and results"
    NOTHING = "nothing", "Nothing"


SWITCH_FIELDS: tuple[str, ...] = (
    "mark_overdue",
    "close_items",
    "end_course_access",
    "notify_educators",
    "learners_may_pause",
)
LIMIT_FIELDS: tuple[str, ...] = ("max_pauses", "max_pause_days")
CONFIG_FIELDS: tuple[str, ...] = (
    *SWITCH_FIELDS,
    "grace_window",
    "after_access_ended",
    *LIMIT_FIELDS,
)


def _switch_field(help_text: str) -> models.CharField:
    return models.CharField(
        max_length=7,
        choices=DeadlineSwitch,
        default=DeadlineSwitch.INHERIT,
        help_text=f'{help_text} "Inherit" uses the next layer up.',
    )


class DeadlineConfigFields(models.Model):
    """The settings a layer may set. Abstract: each layer keeps its own table."""

    mark_overdue = _switch_field(
        "Show the missed-deadline marker on items past their deadline."
    )
    close_items = _switch_field(
        "Close incomplete items once their deadline and grace window pass."
    )
    end_course_access = _switch_field(
        "End a learner's access to the course once the time limit and grace window pass."
    )
    notify_educators = _switch_field(
        "Record that educators should be told about missed deadlines."
    )
    learners_may_pause = _switch_field("Let learners pause this course themselves.")
    grace_window = models.DurationField(
        null=True,
        blank=True,
        help_text=(
            "Time after a deadline before items close or access ends, as DD HH:MM:SS. "
            "Empty uses the next layer up; zero means no grace."
        ),
    )
    after_access_ended = models.CharField(
        max_length=19,
        choices=AfterAccessEnded,
        default=AfterAccessEnded.INHERIT,
        help_text=(
            "What a learner can still open once their access has ended. "
            '"Inherit" uses the next layer up.'
        ),
    )
    max_pauses = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Empty uses the next layer up; 0 means no limit.",
    )
    max_pause_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Empty uses the next layer up; 0 means no limit.",
    )

    class Meta:
        abstract = True
        constraints = [
            *(
                models.CheckConstraint(
                    condition=Q(**{f"{field}__in": DeadlineSwitch.values}),
                    name=f"%(class)s_{field}_is_a_deadline_switch",
                )
                for field in SWITCH_FIELDS
            ),
            models.CheckConstraint(
                condition=Q(after_access_ended__in=AfterAccessEnded.values),
                name="%(class)s_after_access_ended_is_an_after_access_ended",
            ),
            models.CheckConstraint(
                condition=Q(grace_window__isnull=True)
                | Q(grace_window__gte=timedelta(0)),
                name="%(class)s_grace_window_is_not_negative",
            ),
        ]


class SiteDeadlineConfig(SiteAwareModel, TimestampedModel, DeadlineConfigFields):
    class Meta(DeadlineConfigFields.Meta):
        constraints = [
            *DeadlineConfigFields.Meta.constraints,
            models.UniqueConstraint(
                fields=["site"], name="unique_deadline_config_per_site"
            ),
        ]

    def __str__(self) -> str:
        return f"Deadline config for {self.site.name}"


class OrganisationDeadlineConfig(
    SiteAwareModel, TimestampedModel, DeadlineConfigFields
):
    organisation = models.OneToOneField(
        Organisation, on_delete=models.CASCADE, related_name="deadline_config"
    )

    class Meta(DeadlineConfigFields.Meta):
        pass

    def __str__(self) -> str:
        return f"Deadline config for {self.organisation.name}"


class CourseDeadlineConfig(SiteAwareModel, TimestampedModel, DeadlineConfigFields):
    course = models.OneToOneField(
        Course, on_delete=models.CASCADE, related_name="deadline_config"
    )

    class Meta(DeadlineConfigFields.Meta):
        pass

    def __str__(self) -> str:
        return f"Deadline config for {self.course}"


class CohortDeadlineConfig(SiteAwareModel, TimestampedModel, DeadlineConfigFields):
    cohort = models.OneToOneField(
        Cohort, on_delete=models.CASCADE, related_name="deadline_config"
    )

    class Meta(DeadlineConfigFields.Meta):
        pass

    def __str__(self) -> str:
        return f"Deadline config for {self.cohort.name}"


class CohortCourseRegistrationDeadlineConfig(
    SiteAwareModel, TimestampedModel, DeadlineConfigFields
):
    cohort_registration = models.OneToOneField(
        CohortCourseRegistration,
        on_delete=models.CASCADE,
        related_name="deadline_config",
    )

    class Meta(DeadlineConfigFields.Meta):
        pass

    def __str__(self) -> str:
        return f"Deadline config for {self.cohort_registration}"


class LearnerCourseRegistrationDeadlineConfig(
    SiteAwareModel, TimestampedModel, DeadlineConfigFields
):
    learner_registration = models.OneToOneField(
        LearnerCourseRegistration,
        on_delete=models.CASCADE,
        related_name="deadline_config",
    )

    class Meta(DeadlineConfigFields.Meta):
        pass

    def __str__(self) -> str:
        return f"Deadline config for {self.learner_registration}"


class CoursePauseManager(SiteAwareManager):
    def due_for_announcement(self, now: datetime, site: Site) -> QuerySet[CoursePause]:
        """Pauses of `site` whose planned resume day has begun and that no one has
        announced. Filters by the given site itself: the sweep has no request for the
        manager to read one from."""
        today = now.astimezone(site_time_zone(site)).date()
        return cast(
            QuerySet[CoursePause],
            self.filter(
                site=site,
                resume_announced_at__isnull=True,
                planned_resume_on__isnull=False,
                planned_resume_on__lte=today,
            ),
        )


class CoursePause(SiteAwareModel, TimestampedModel):
    """One pause of one learner's course progress. While it is open the learner's clock is
    stopped, and the days it lasted move every unmet deadline forward."""

    course_progress = models.ForeignKey(
        CourseProgress, on_delete=models.CASCADE, related_name="pauses"
    )
    started_at = models.DateTimeField()
    planned_resume_on = models.DateField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    reason = models.TextField()
    ended_reason = models.TextField(blank=True)
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    ended_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    resume_announced_at = models.DateTimeField(null=True, blank=True)

    objects = CoursePauseManager()

    class Meta:
        ordering = ["-started_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["course_progress"],
                condition=Q(ended_at__isnull=True),
                name="one_unended_pause_per_course_progress",
            ),
            models.CheckConstraint(
                condition=Q(ended_at__isnull=True)
                | Q(ended_at__gte=models.F("started_at")),
                name="course_pause_ends_after_it_starts",
            ),
        ]

    def __str__(self) -> str:
        record = self.course_progress
        return f"{record.learner} on {record.course}, paused {self.started_at:%Y-%m-%d}"

    def planned_resume_instant(self, tz: ZoneInfo) -> datetime | None:
        """Midnight starting the planned resume day, in the site zone."""
        if self.planned_resume_on is None:
            return None
        return datetime.combine(self.planned_resume_on, time.min, tzinfo=tz)

    def planned_resume_day_instant(self, tz: ZoneInfo) -> datetime | None:
        """The planned resume day as a date-only instant: the last microsecond of that day in
        the site zone, which the time formatters write as a date with no time."""
        if self.planned_resume_on is None:
            return None
        return datetime.combine(self.planned_resume_on, time.max, tzinfo=tz)

    def end_instant(self, tz: ZoneInfo) -> datetime | None:
        """The earlier of the recorded end and the planned resume instant. None while
        neither is set."""
        planned = self.planned_resume_instant(tz)
        ends = [i for i in (self.ended_at, planned) if i is not None]
        return min(ends) if ends else None

    def is_open(self, now: datetime, tz: ZoneInfo) -> bool:
        end = self.end_instant(tz)
        return end is None or end > now

    def paused_days(self, now: datetime, tz: ZoneInfo) -> int:
        """Whole days this pause has lasted by `now`; an open pause counts up to `now`."""
        end = self.end_instant(tz)
        return shifts.paused_days(self.started_at, min(end, now) if end else now)


class ExtensionTarget(models.TextChoices):
    COLLECTION_ITEM = "collection_item", "Collection item"
    TIME_LIMIT = "time_limit", "Time limit"
    COURSE = "course", "Whole course"


# Every read adds the days to a date, so an unbounded value would overflow the arithmetic
# on each read of the learner's deadlines.
MAX_EXTENSION_DAYS = 3650


class DeadlineExtension(SiteAwareModel, TimestampedModel):
    """Days added to one learner's deadlines on a course. Rows stack by addition."""

    course_progress = models.ForeignKey(
        CourseProgress, on_delete=models.CASCADE, related_name="deadline_extensions"
    )
    target_kind = models.CharField(max_length=15, choices=ExtensionTarget.choices)
    collection_item = models.ForeignKey(
        ContentCollectionItem,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="+",
    )
    days = models.PositiveIntegerField()
    requested_date = models.DateField(null=True, blank=True)
    reason = models.TextField()
    set_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(target_kind=ExtensionTarget.COLLECTION_ITEM)
                    & Q(collection_item__isnull=False)
                )
                | (
                    ~Q(target_kind=ExtensionTarget.COLLECTION_ITEM)
                    & Q(collection_item__isnull=True)
                ),
                name="deadline_extension_item_only_for_item_target",
            ),
            models.CheckConstraint(
                condition=Q(days__gte=1) & Q(days__lte=MAX_EXTENSION_DAYS),
                name="deadline_extension_days_in_range",
            ),
            models.CheckConstraint(
                condition=~Q(target_kind=ExtensionTarget.COURSE)
                | Q(requested_date__isnull=True),
                name="deadline_extension_course_has_no_requested_date",
            ),
        ]

    def __str__(self) -> str:
        record = self.course_progress
        return (
            f"{record.learner} on {record.course}: +{self.days} days "
            f"({self.target_kind})"
        )

    def clean(self) -> None:
        if not self.course_progress_id or self.collection_item is None:
            return
        if self.collection_item not in (
            self.course_progress.course.viewable_collection_items()
        ):
            raise ValidationError({"collection_item": "Pick an item of this course."})
