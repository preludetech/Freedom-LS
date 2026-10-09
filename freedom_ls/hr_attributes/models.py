"""Job titles, departments, locations and start dates recorded against a learner.

Each organisation keeps its own lists. A learner holds at most one entry from
each list and four dates that stand alone: a date may be set while its entry
is empty, lie in the future, or fall before another, because rehires and
acquisitions produce real data any ordering rule would reject.
"""

from typing import TYPE_CHECKING, Self, cast
from uuid import UUID

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower, Trim

from freedom_ls.site_aware_models.models import SiteAwareManager, SiteAwareModel


class ListEntryQuerySet(models.QuerySet):
    def for_picker(self, organisation_id: UUID, current_pk: UUID | None) -> Self:
        """Active entries of the organisation, plus the one currently held.

        A deactivated entry leaves every picker but stays valid where it is
        already chosen, so a learner holding one can still be saved.
        """
        return self.filter(organisation_id=organisation_id).filter(
            Q(is_active=True) | Q(pk=current_pk)
        )


class ListEntryManager(SiteAwareManager):
    # Hand-written pass-through, the way ArticleManager does it, because
    # SiteAwareManager.from_queryset() is not a base mypy can resolve.
    _queryset_class = ListEntryQuerySet

    def for_picker(
        self, organisation_id: UUID, current_pk: UUID | None
    ) -> ListEntryQuerySet:
        return cast("ListEntryQuerySet", self.get_queryset()).for_picker(
            organisation_id, current_pk
        )


def _unique_name_per_organisation(name: str) -> models.UniqueConstraint:
    # Trimmed and case-folded, so "Finance" and " finance " are one entry. Trim
    # removes spaces only; the form and clean() strip all surrounding
    # whitespace before a name gets this far.
    return models.UniqueConstraint(
        Lower(Trim("name")), "site", "organisation", name=name
    )


if TYPE_CHECKING:
    # The type checker is handed Model as the base so super().clean()
    # resolves. At runtime the base is object, and the concrete model's MRO
    # carries super() on to Model.
    _ListEntryBase = models.Model
else:
    _ListEntryBase = object


class ListEntryMixin(_ListEntryBase):
    """Behaviour shared by JobTitle, Department and Location.

    A plain class rather than an abstract model: each list declares its own
    fields, and this only supplies the methods that read them.
    """

    name: str
    is_active: bool

    def clean(self) -> None:
        super().clean()
        # Surrounding whitespace goes; the case stays as typed, so "IT" is not "It".
        self.name = self.name.strip()

    def __str__(self) -> str:
        # The suffix is what tells a reader of the learner page that a held
        # entry has since been deactivated.
        return self.name if self.is_active else f"{self.name} (inactive)"


class JobTitle(ListEntryMixin, SiteAwareModel):
    organisation = models.ForeignKey(
        "freedom_ls_organisations.Organisation",
        on_delete=models.PROTECT,
        related_name="job_titles",
    )
    name = models.CharField(max_length=200)
    # Deactivating is how an entry is withdrawn. A learner may still hold it,
    # so it is never deleted.
    is_active = models.BooleanField(default=True)

    objects = ListEntryManager()

    class Meta:
        ordering = ["name"]
        constraints = [
            _unique_name_per_organisation("unique_job_title_name_per_organisation")
        ]


class Department(ListEntryMixin, SiteAwareModel):
    organisation = models.ForeignKey(
        "freedom_ls_organisations.Organisation",
        on_delete=models.PROTECT,
        related_name="departments",
    )
    name = models.CharField(max_length=200)
    # Deactivating is how an entry is withdrawn. A learner may still hold it,
    # so it is never deleted.
    is_active = models.BooleanField(default=True)

    objects = ListEntryManager()

    class Meta:
        ordering = ["name"]
        constraints = [
            _unique_name_per_organisation("unique_department_name_per_organisation")
        ]


class Location(ListEntryMixin, SiteAwareModel):
    organisation = models.ForeignKey(
        "freedom_ls_organisations.Organisation",
        on_delete=models.PROTECT,
        related_name="locations",
    )
    name = models.CharField(max_length=200)
    # Deactivating is how an entry is withdrawn. A learner may still hold it,
    # so it is never deleted.
    is_active = models.BooleanField(default=True)

    objects = ListEntryManager()

    class Meta:
        ordering = ["name"]
        constraints = [
            _unique_name_per_organisation("unique_location_name_per_organisation")
        ]


class LearnerHRAttributes(SiteAwareModel):
    learner = models.OneToOneField(
        "freedom_ls_learner_management.Learner",
        on_delete=models.CASCADE,
        related_name="hr_attributes",
    )
    job_title = models.ForeignKey(
        JobTitle,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="learner_hr_attributes",
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="learner_hr_attributes",
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="learner_hr_attributes",
    )
    # The hire date. This is when the learner started at the organisation, not
    # at a course.
    organisation_start_date = models.DateField(null=True, blank=True)
    job_title_start_date = models.DateField(null=True, blank=True)
    department_start_date = models.DateField(null=True, blank=True)
    location_start_date = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "HR attributes"
        verbose_name_plural = "HR attributes"

    def clean(self) -> None:
        """Refuse a list entry that belongs to another organisation than the learner's.

        A deactivated entry is not refused, so a learner who holds one can
        still be saved. Nothing here compares or orders the dates.
        """
        super().clean()
        try:
            learner = self.learner
        except ObjectDoesNotExist:
            # Unset means the form already holds a field error for it; let
            # that surface rather than crash here.
            return
        errors: dict[str, ValidationError] = {}
        for field_name, label, entry in (
            ("job_title", "job title", self.job_title),
            ("department", "department", self.department),
            ("location", "location", self.location),
        ):
            if entry is not None and entry.organisation_id != learner.organisation_id:
                errors[field_name] = ValidationError(
                    f"Choose a {label} from this learner's organisation."
                )
        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"HR attributes for {self.learner}"


class OrganisationHRSettings(SiteAwareModel):
    organisation = models.OneToOneField(
        "freedom_ls_organisations.Organisation",
        on_delete=models.CASCADE,
        related_name="hr_settings",
    )
    # Off until the organisation opts in. No row at all also means off.
    registration_rules_enabled = models.BooleanField(default=False)

    class Meta:
        verbose_name = "HR settings"
        verbose_name_plural = "HR settings"

    def __str__(self) -> str:
        return f"HR settings for {self.organisation}"
