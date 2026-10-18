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


class RuleRegistration(SiteAwareModel):
    """The rule that made a registration. Exists only for rows a rule created.

    Kept here, in the optional app, rather than as a column on the
    registration: the core app must stay installable without rules.
    """

    registration = models.OneToOneField(
        "freedom_ls_learner_management.LearnerCourseRegistration",
        on_delete=models.CASCADE,
        related_name="rule_registration",
    )
    # SET_NULL with the name snapshotted below: a registration still reads as
    # rule-made after its rule is deleted.
    rule = models.ForeignKey(
        RegistrationRule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rule_registrations",
    )
    rule_name = models.CharField(max_length=200)
    # True while the rule has the registration deactivated because the learner
    # stopped matching. A deactivation anyone else makes detaches the row.
    is_retracted = models.BooleanField(default=False)

    def __str__(self) -> str:
        return self.rule_name
