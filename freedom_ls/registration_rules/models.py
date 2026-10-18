"""Rules that keep a course's registrations in step with who works where.

A rule belongs to one organisation, names one course and says who matches.
Evaluation runs in the background and reconciles the course's registrations
with the current match, so a repeated or stale run changes nothing.
"""

from django.db import models

from freedom_ls.site_aware_models.models import SiteAwareModel, TimestampedModel


class RegistrationRule(SiteAwareModel, TimestampedModel):
    class Outcome(models.TextChoices):
        REGISTER = "register", "Register"

    # Both PROTECT: a rule explains registrations that may outlive the people
    # who wrote it, and neither side is deleted while one exists.
    organisation = models.ForeignKey(
        "freedom_ls_organisations.Organisation",
        on_delete=models.PROTECT,
        related_name="registration_rules",
    )
    course = models.ForeignKey(
        "freedom_ls_content_engine.Course",
        on_delete=models.PROTECT,
        related_name="registration_rules",
    )
    name = models.CharField(max_length=200)
    # A key of REGISTRATION_RULE_KINDS. Validated by the loader, not by choices,
    # so a project can add a kind without a migration.
    kind = models.CharField(max_length=50, default="attribute")
    outcome = models.CharField(
        max_length=20, choices=Outcome.choices, default=Outcome.REGISTER
    )
    # Off at creation: conditions are added on the change page, and enabling
    # is what first registers anyone.
    is_enabled = models.BooleanField(default=False)
    # Written with QuerySet.update() when a run of the whole rule finishes, so
    # it never moves updated_at. Null or older than updated_at means a change
    # that no run has applied yet.
    last_evaluated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
