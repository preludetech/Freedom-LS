"""Rules that keep a course's registrations in step with who works where.

A rule belongs to one organisation, names one course and says who matches.
Evaluation runs in the background and reconciles the course's registrations
with the current match, so a repeated or stale run changes nothing.
"""

from django.core.exceptions import ValidationError
from django.db import models

from freedom_ls.site_aware_models.models import SiteAwareModel, TimestampedModel

#: (on-or-after bound, before bound, the LearnerHRAttributes date they test).
DATE_BOUND_PAIRS: tuple[tuple[str, str, str], ...] = (
    (
        "organisation_start_on_or_after",
        "organisation_start_before",
        "organisation_start_date",
    ),
    ("job_title_start_on_or_after", "job_title_start_before", "job_title_start_date"),
    (
        "department_start_on_or_after",
        "department_start_before",
        "department_start_date",
    ),
    ("location_start_on_or_after", "location_start_before", "location_start_date"),
)


class RegistrationRule(SiteAwareModel, TimestampedModel):
    class Outcome(models.TextChoices):
        REGISTER = "register", "Register"
        RECOMMEND = "recommend", "Recommend"

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


class RuleRecommendation(SiteAwareModel):
    """A rule that recommends a course to a user. One row per rule, so rules of
    different organisations share a recommendation without reading each other's rows.

    Both CASCADE: a recommendation with no rule left behind it is deleted by the
    rule's own pre_delete, and a deleted recommendation leaves nothing to label.
    """

    recommendation = models.ForeignKey(
        "freedom_ls_course_recommendations.RecommendedCourse",
        on_delete=models.CASCADE,
        related_name="rule_recommendations",
    )
    rule = models.ForeignKey(
        RegistrationRule, on_delete=models.CASCADE, related_name="rule_recommendations"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site", "recommendation", "rule"],
                name="unique_rule_recommendation",
            )
        ]

    def __str__(self) -> str:
        # Not the rule's name: this renders where the viewer may not view rules.
        return "Registration rule"


class AttributeRuleConditions(SiteAwareModel):
    """What an attribute rule asks of a learner.

    AND across the three lists and the dates, OR within a list. An empty list
    or a null bound constrains nothing, so a rule with no conditions matches
    the whole organisation.
    """

    rule = models.OneToOneField(
        RegistrationRule, on_delete=models.CASCADE, related_name="attribute_conditions"
    )
    job_titles = models.ManyToManyField(
        "freedom_ls_hr_attributes.JobTitle",
        blank=True,
        related_name="registration_rule_conditions",
    )
    departments = models.ManyToManyField(
        "freedom_ls_hr_attributes.Department",
        blank=True,
        related_name="registration_rule_conditions",
    )
    locations = models.ManyToManyField(
        "freedom_ls_hr_attributes.Location",
        blank=True,
        related_name="registration_rule_conditions",
    )
    organisation_start_on_or_after = models.DateField(null=True, blank=True)
    organisation_start_before = models.DateField(null=True, blank=True)
    job_title_start_on_or_after = models.DateField(null=True, blank=True)
    job_title_start_before = models.DateField(null=True, blank=True)
    department_start_on_or_after = models.DateField(null=True, blank=True)
    department_start_before = models.DateField(null=True, blank=True)
    location_start_on_or_after = models.DateField(null=True, blank=True)
    location_start_before = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "attribute conditions"
        verbose_name_plural = "attribute conditions"

    def __str__(self) -> str:
        return f"Attribute conditions for {self.rule}"

    def clean(self) -> None:
        super().clean()
        errors: dict[str, ValidationError] = {}
        for on_or_after, before, _ in DATE_BOUND_PAIRS:
            lower, upper = getattr(self, on_or_after), getattr(self, before)
            if lower is not None and upper is not None and upper <= lower:
                errors[before] = ValidationError(
                    "Must be later than the 'on or after' date."
                )
        if errors:
            raise ValidationError(errors)


#: The conditions field that names a list's entries, by the list's model name.
_CONDITIONS_FIELD_BY_LIST: dict[str, str] = {
    "jobtitle": "job_titles",
    "department": "departments",
    "location": "locations",
}


def rules_naming(entry: models.Model) -> models.QuerySet[RegistrationRule]:
    """The rules whose conditions name this job title, department or location.

    Explicit site: a delete can run with no request for the site-aware manager.
    """
    field = _CONDITIONS_FIELD_BY_LIST[entry._meta.model_name or ""]
    return RegistrationRule._base_manager.filter(
        site_id=getattr(entry, "site_id"),  # noqa: B009 - typed as Model
        **{f"attribute_conditions__{field}": entry},
    ).order_by("name")
