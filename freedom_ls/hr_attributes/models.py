"""Job titles, departments, locations and start dates recorded against a learner.

Each organisation keeps its own lists. A learner holds at most one entry from
each list and four dates that stand alone: a date may be set while its entry
is empty, lie in the future, or fall before another, because rehires and
acquisitions produce real data any ordering rule would reject.
"""

from django.db import models
from django.db.models.functions import Lower, Trim

from freedom_ls.site_aware_models.models import SiteAwareModel


class JobTitle(SiteAwareModel):
    organisation = models.ForeignKey(
        "freedom_ls_organisations.Organisation",
        on_delete=models.PROTECT,
        related_name="job_titles",
    )
    name = models.CharField(max_length=200)
    # Deactivating is how an entry is withdrawn. A learner may still hold it,
    # so it is never deleted.
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            # Trimmed and case-folded, so "Finance" and " finance " are one
            # entry. Trim removes spaces only; the form and clean() strip all
            # surrounding whitespace before a name gets this far.
            models.UniqueConstraint(
                Lower(Trim("name")),
                "site",
                "organisation",
                name="unique_job_title_name_per_organisation",
            )
        ]

    def clean(self) -> None:
        super().clean()
        # Surrounding whitespace goes; the case stays as typed, so "IT" is not "It".
        self.name = self.name.strip()

    def __str__(self) -> str:
        # The suffix is what tells a reader of the learner page that a held
        # entry has since been deactivated.
        return self.name if self.is_active else f"{self.name} (inactive)"


class Department(SiteAwareModel):
    organisation = models.ForeignKey(
        "freedom_ls_organisations.Organisation",
        on_delete=models.PROTECT,
        related_name="departments",
    )
    name = models.CharField(max_length=200)
    # Deactivating is how an entry is withdrawn. A learner may still hold it,
    # so it is never deleted.
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            # Trimmed and case-folded, so "Finance" and " finance " are one
            # entry. Trim removes spaces only; the form and clean() strip all
            # surrounding whitespace before a name gets this far.
            models.UniqueConstraint(
                Lower(Trim("name")),
                "site",
                "organisation",
                name="unique_department_name_per_organisation",
            )
        ]

    def clean(self) -> None:
        super().clean()
        # Surrounding whitespace goes; the case stays as typed, so "IT" is not "It".
        self.name = self.name.strip()

    def __str__(self) -> str:
        # The suffix is what tells a reader of the learner page that a held
        # entry has since been deactivated.
        return self.name if self.is_active else f"{self.name} (inactive)"


class Location(SiteAwareModel):
    organisation = models.ForeignKey(
        "freedom_ls_organisations.Organisation",
        on_delete=models.PROTECT,
        related_name="locations",
    )
    name = models.CharField(max_length=200)
    # Deactivating is how an entry is withdrawn. A learner may still hold it,
    # so it is never deleted.
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            # Trimmed and case-folded, so "Finance" and " finance " are one
            # entry. Trim removes spaces only; the form and clean() strip all
            # surrounding whitespace before a name gets this far.
            models.UniqueConstraint(
                Lower(Trim("name")),
                "site",
                "organisation",
                name="unique_location_name_per_organisation",
            )
        ]

    def clean(self) -> None:
        super().clean()
        # Surrounding whitespace goes; the case stays as typed, so "IT" is not "It".
        self.name = self.name.strip()

    def __str__(self) -> str:
        # The suffix is what tells a reader of the learner page that a held
        # entry has since been deactivated.
        return self.name if self.is_active else f"{self.name} (inactive)"


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
