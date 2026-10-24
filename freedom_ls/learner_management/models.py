from __future__ import annotations

from collections.abc import Collection

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from freedom_ls.site_aware_models.models import SiteAwareModel, TimestampedModel

User = get_user_model()


def _relations_are_set(instance: models.Model, *field_names: str) -> bool:
    """Whether every named foreign key on ``instance`` resolves.

    An unset one means the form already holds a field-level error for it -- an
    invalid choice in an admin inline, say. Callers return early on False so
    that error surfaces instead of a RelatedObjectDoesNotExist crash out of
    clean().
    """
    try:
        for field_name in field_names:
            getattr(instance, field_name)
    except ObjectDoesNotExist:
        return False
    return True


class Cohort(SiteAwareModel, TimestampedModel):
    organisation = models.ForeignKey(
        "freedom_ls_organisations.Organisation",
        on_delete=models.PROTECT,
    )
    name = models.CharField(_("name"), max_length=150)
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site", "organisation", "name"],
                name="unique_cohort_name_per_organisation",
            )
        ]
        permissions = [("download_cohort_report", "Can download cohort report")]

    def __str__(self):
        return self.name


class Learner(SiteAwareModel):
    """A user's association with an organisation for enrolment purposes.

    A user may hold a Learner row in more than one organisation. Enrolment
    records (CohortMembership, LearnerCourseRegistration) hang off Learner
    rather than User, so an enrolment with no organisation association
    cannot be represented.

    Self-service registration on the default organisation reactivates a
    removed learner rather than refusing it: registering again is treated as
    a live signal of re-association, so ensure_learner overwrites
    is_active=False instead of erroring on it.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    organisation = models.ForeignKey(
        "freedom_ls_organisations.Organisation", on_delete=models.PROTECT
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site", "user", "organisation"],
                name="unique_learner_per_organisation",
            )
        ]
        permissions = [("bulk_manage_learners", "Can bulk manage learners")]

    def __str__(self) -> str:
        return f"{self.user} - {self.organisation}"


class OrganisationMember(SiteAwareModel):
    """A user who helps run an organisation's learners, whether or not they teach.

    The counterpart of Learner, and independent of it: a user may hold both
    an OrganisationMember and a Learner row in the same organisation. This
    is the gate can() checks before an organisation- or cohort-level role
    assignment counts -- deactivating a row here suspends every grant it
    covers without touching the role assignments themselves, and
    reactivating it restores them exactly as they were.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    organisation = models.ForeignKey(
        "freedom_ls_organisations.Organisation", on_delete=models.PROTECT
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site", "user", "organisation"],
                name="unique_member_per_organisation",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user} - {self.organisation}"


class CohortMembership(SiteAwareModel, TimestampedModel):
    cohort = models.ForeignKey(Cohort, on_delete=models.CASCADE)
    learner = models.ForeignKey(Learner, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["learner", "cohort"],
                name="unique_learner_cohort_membership",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if not _relations_are_set(self, "learner", "cohort"):
            return
        if self.learner.organisation_id != self.cohort.organisation_id:
            raise ValidationError(
                "Learner and cohort must belong to the same organisation."
            )

    def __str__(self):
        return f"{self.learner} - {self.cohort}"


class LearnerCourseRegistration(SiteAwareModel):
    """Individual learner registration for a course."""

    course = models.ForeignKey(
        "freedom_ls_content_engine.Course",
        on_delete=models.PROTECT,
        related_name="learner_registrations",
    )
    learner = models.ForeignKey(Learner, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    # False for registrations made before this field existed, whoever made them.
    self_registered = models.BooleanField(
        default=False,
        help_text="The learner registered themselves rather than being registered by staff.",
    )
    registered_at = models.DateTimeField(auto_now_add=True)

    # The `is_active` this instance was loaded with, or None when it was built in
    # memory or loaded with `is_active` deferred. A save compares it with the
    # new value to tell a reactivation from a no-op without a second query.
    loaded_is_active: bool | None = None

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site", "learner", "course"],
                name="unique_learner_course_registration",
            )
        ]

    @classmethod
    def from_db(
        cls,
        db: str | None,
        field_names: Collection[str],
        values: Collection[object],
    ) -> LearnerCourseRegistration:
        instance = super().from_db(db, field_names, values)
        loaded = dict(zip(field_names, values, strict=False))
        if "is_active" in loaded:
            instance.loaded_is_active = bool(loaded["is_active"])
        return instance

    def __str__(self):
        return f"{self.learner} - {self.course}"


class CohortCourseRegistration(SiteAwareModel):
    """Cohort-wide registration for a course."""

    course = models.ForeignKey(
        "freedom_ls_content_engine.Course",
        on_delete=models.PROTECT,
        related_name="cohort_registrations",
    )
    cohort = models.ForeignKey(
        Cohort, on_delete=models.CASCADE, related_name="course_registrations"
    )
    is_active = models.BooleanField(default=True)
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site", "course", "cohort"],
                name="unique_cohort_course_registration",
            )
        ]

    def __str__(self):
        return f"{self.cohort} - {self.course}"
