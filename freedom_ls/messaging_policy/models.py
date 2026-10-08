from __future__ import annotations

from django.db import models
from django.db.models import Q

from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.organisations.models import Organisation
from freedom_ls.site_aware_models.models import SiteAwareModel, TimestampedModel


class MessagingFlag(models.TextChoices):
    INHERIT = "inherit"
    OPEN = "open"
    CLOSED = "closed"


FLAG_NAMES: tuple[str, ...] = (
    "learner_to_educator",
    "learner_to_cohort_peer",
    "learner_to_course_peer",
)


def _flag_field() -> models.CharField:
    return models.CharField(
        max_length=7,
        choices=MessagingFlag,
        default=MessagingFlag.INHERIT,
        help_text='"Inherit" uses the next level up.',
    )


class MessagingFlags(models.Model):
    """The three flags a level may set. Abstract: each level has its own table so
    a reverse OneToOne LEFT JOIN resolves the chain inside one queryset."""

    learner_to_educator = _flag_field()
    learner_to_cohort_peer = _flag_field()
    learner_to_course_peer = _flag_field()

    class Meta:
        abstract = True
        constraints = [
            models.CheckConstraint(
                condition=Q(**{f"{flag}__in": MessagingFlag.values}),
                name=f"%(class)s_{flag}_is_a_messaging_flag",
            )
            for flag in FLAG_NAMES
        ]


class SiteMessagingConfig(SiteAwareModel, TimestampedModel, MessagingFlags):
    class Meta(MessagingFlags.Meta):
        constraints = [
            *MessagingFlags.Meta.constraints,
            models.UniqueConstraint(
                fields=["site"], name="unique_messaging_config_per_site"
            ),
        ]

    def __str__(self) -> str:
        return f"Messaging config for {self.site.name}"


class OrganisationMessagingConfig(SiteAwareModel, TimestampedModel, MessagingFlags):
    organisation = models.OneToOneField(
        Organisation, on_delete=models.CASCADE, related_name="messaging_config"
    )

    class Meta(MessagingFlags.Meta):
        pass

    def __str__(self) -> str:
        return f"Messaging config for {self.organisation.name}"


class CohortMessagingConfig(SiteAwareModel, TimestampedModel, MessagingFlags):
    cohort = models.OneToOneField(
        Cohort, on_delete=models.CASCADE, related_name="messaging_config"
    )

    class Meta(MessagingFlags.Meta):
        pass

    def __str__(self) -> str:
        return f"Messaging config for {self.cohort.name}"


class LearnerMessagingConfig(SiteAwareModel, TimestampedModel, MessagingFlags):
    learner = models.OneToOneField(
        Learner, on_delete=models.CASCADE, related_name="messaging_config"
    )

    class Meta(MessagingFlags.Meta):
        pass

    def __str__(self) -> str:
        return f"Messaging config for {self.learner}"


class LearnerCourseRegistrationMessagingConfig(SiteAwareModel, TimestampedModel):
    # A registration carries only the course-peer flag: no role is scoped to a
    # course, so no other candidate passes through it.
    registration = models.OneToOneField(
        LearnerCourseRegistration,
        on_delete=models.CASCADE,
        related_name="messaging_config",
    )
    learner_to_course_peer = _flag_field()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(learner_to_course_peer__in=MessagingFlag.values),
                name="learner_course_registration_messaging_config_flag_is_a_messaging_flag",
            )
        ]

    def __str__(self) -> str:
        return f"Messaging config for {self.registration}"


class CohortCourseRegistrationMessagingConfig(SiteAwareModel, TimestampedModel):
    registration = models.OneToOneField(
        CohortCourseRegistration,
        on_delete=models.CASCADE,
        related_name="messaging_config",
    )
    learner_to_course_peer = _flag_field()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(learner_to_course_peer__in=MessagingFlag.values),
                name="cohort_course_registration_messaging_config_flag_is_a_messaging_flag",
            )
        ]

    def __str__(self) -> str:
        return f"Messaging config for {self.registration}"
