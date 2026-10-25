"""Seed the recommend-outcome frontend QA scenario (§0.2 of its QA plan).

Idempotent: re-running brings every record back to exactly the state below,
on the Site that ``demodev@email.com`` belongs to, and removes the residue a
previous QA run left behind.

- ``QA Rec Org One`` and ``QA Rec Org Two``, both with registration rules
  switched on. Departments: Org One Finance, Operations; Org Two Finance.
- Courses ``QA Audit Essentials`` and ``QA Second Course`` (published, free,
  one topic each) and ``QA Draft Course`` (hidden).
- Cohort ``QA Rec Cohort`` in QA Rec Org One: active, no members, no courses.
- Learners (password == email, verified email), each with an HR row:
  - QA Rec Org One: qa_rec_finance, qa_rec_second, qa_rec_registered (with a
    staff-made registration for QA Audit Essentials), qa_rec_staffrec (with a
    staff-made recommendation for QA Audit Essentials), all Finance;
    qa_rec_ops in Operations.
  - qa_rec_both: Finance in QA Rec Org One and in QA Rec Org Two.

Deleted on every run, on that Site: every RegistrationRule (with its
conditions, RuleRegistration and RuleRecommendation rows), every
RecommendedCourse, every individual and cohort registration for the three QA
courses, the course progress of qa_rec_* learners, qa_rec_* users and
learners not in the list above, staff users holding nothing but the
registration-rule / recommended-course permissions the plan hands out, and
the notifications of qa_rec_* users. The staff rows are then rebuilt.

Usage:
    uv run python manage.py qa_create_recommend_outcome_scenario
"""

from typing import cast

import djclick as click

from django.contrib.auth.models import Permission
from django.contrib.sites.models import Site
from django.db import transaction

from freedom_ls.accounts.models import User
from freedom_ls.comms.models import Notification
from freedom_ls.content_engine.models import CourseVisibility
from freedom_ls.course_recommendations.factories import RecommendedCourseFactory
from freedom_ls.course_recommendations.models import RecommendedCourse
from freedom_ls.hr_attributes.factories import (
    DepartmentFactory,
    JobTitleFactory,
    LearnerHRAttributesFactory,
    LocationFactory,
    OrganisationHRSettingsFactory,
)
from freedom_ls.hr_attributes.models import (
    Department,
    JobTitle,
    LearnerHRAttributes,
    Location,
    OrganisationHRSettings,
)
from freedom_ls.learner_management.factories import (
    CohortFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.organisations.models import Organisation
from freedom_ls.qa_helpers.management.commands.qa_create_hr_attributes_scenario import (
    ListEntry,
    _ensure_learner_user,
    _ensure_list,
    _ensure_organisation,
)
from freedom_ls.qa_helpers.management.commands.qa_create_registration_rules_scenario import (
    _delete_user,
    _ensure_course,
)
from freedom_ls.registration_rules.models import RegistrationRule, RuleRegistration

ADMIN_EMAIL = "demodev@email.com"
ORG_ONE = "QA Rec Org One"
ORG_TWO = "QA Rec Org Two"
COHORT_NAME = "QA Rec Cohort"
EMAIL_PREFIX = "qa_rec_"
REGISTERED_EMAIL = "qa_rec_registered@email.com"
STAFFREC_EMAIL = "qa_rec_staffrec@email.com"
# The plan's §11 creates staff users holding only these.
PLAN_PERMISSIONS = {
    "view_registrationrule",
    "view_recommendedcourse",
    "change_recommendedcourse",
}

AUDIT = ("QA Audit Essentials", "qa-audit-essentials")
SECOND = ("QA Second Course", "qa-second-course")
DRAFT = ("QA Draft Course", "qa-draft-course")

DEPARTMENTS = {
    ORG_ONE: [("Finance", True), ("Operations", True)],
    ORG_TWO: [("Finance", True)],
}

# email, first, last, [(organisation, department)].
LEARNERS: list[tuple[str, str, str, list[tuple[str, str]]]] = [
    ("qa_rec_finance@email.com", "Farah", "Finance", [(ORG_ONE, "Finance")]),
    ("qa_rec_second@email.com", "Sizwe", "Second", [(ORG_ONE, "Finance")]),
    ("qa_rec_ops@email.com", "Oupa", "Ops", [(ORG_ONE, "Operations")]),
    (REGISTERED_EMAIL, "Refilwe", "Registered", [(ORG_ONE, "Finance")]),
    (STAFFREC_EMAIL, "Sam", "Staffrec", [(ORG_ONE, "Finance")]),
    (
        "qa_rec_both@email.com",
        "Bheki",
        "Both",
        [(ORG_ONE, "Finance"), (ORG_TWO, "Finance")],
    ),
]


def _report(label: str, deleted: tuple[int, dict[str, int]]) -> None:
    click.secho(f"{label} deleted: {deleted}", fg="yellow")


def _plan_staff(site: Site) -> list[User]:
    """Non-superusers whose direct grants are a subset of the plan's permissions."""
    permissions = Permission.objects.filter(codename__in=PLAN_PERMISSIONS)
    found = []
    for user in User._base_manager.filter(
        site=site, is_superuser=False, user_permissions__in=permissions
    ).distinct():
        codenames = set(user.user_permissions.values_list("codename", flat=True))
        if codenames <= PLAN_PERMISSIONS and not user.groups.exists():
            found.append(user)
        else:
            click.secho(
                f"Left staff user {user.email}: holds more ({codenames})", fg="red"
            )
    return found


@click.command()
def command() -> None:
    """Seed the recommend-outcome QA scenario on demodev@email.com's Site."""
    admin = User._base_manager.filter(email=ADMIN_EMAIL).first()
    if admin is None:
        raise click.ClickException(
            f"{ADMIN_EMAIL} not found. Run `uv run python manage.py "
            "create_demo_data --yes` first."
        )
    site = admin.site
    wanted_emails = [email for email, _, _, _ in LEARNERS]

    with transaction.atomic():
        # Rules first, so no learner-side save below evaluates a stale rule.
        # Conditions, RuleRegistration links and RuleRecommendation rows go
        # with them (CASCADE; RuleRegistration.rule is SET_NULL, so delete
        # those links explicitly).
        rules = RegistrationRule._base_manager.filter(site=site)
        for rule in rules:
            click.secho(f"Deleting rule {rule.pk} '{rule}'", fg="yellow")
        _report(
            "RuleRegistration",
            RuleRegistration._base_manager.filter(site=site).delete(),
        )
        _report("RegistrationRule", rules.delete())

        for recommendation in RecommendedCourse._base_manager.filter(
            site=site
        ).select_related("user", "course"):
            click.secho(
                f"Deleting recommendation {recommendation.pk}: {recommendation}",
                fg="yellow",
            )
        _report(
            "RecommendedCourse",
            RecommendedCourse._base_manager.filter(site=site).delete(),
        )

        for user in User._base_manager.filter(email__startswith=EMAIL_PREFIX).exclude(
            email__in=wanted_emails
        ):
            _delete_user(user, "stray qa_rec_ user")
        for user in _plan_staff(site):
            _delete_user(user, "plan staff user")

        organisations: dict[str, Organisation] = {
            ORG_ONE: _ensure_organisation(site, ORG_ONE),
            ORG_TWO: _ensure_organisation(site, ORG_TWO),
        }

        courses = {
            "audit": _ensure_course(
                site,
                title=AUDIT[0],
                slug=AUDIT[1],
                visibility=CourseVisibility.PUBLISHED,
                with_topic=True,
            ),
            "second": _ensure_course(
                site,
                title=SECOND[0],
                slug=SECOND[1],
                visibility=CourseVisibility.PUBLISHED,
                with_topic=True,
            ),
            "draft": _ensure_course(
                site,
                title=DRAFT[0],
                slug=DRAFT[1],
                visibility=CourseVisibility.HIDDEN,
                with_topic=False,
            ),
        }

        cohort = Cohort._base_manager.filter(
            site=site, organisation=organisations[ORG_ONE], name=COHORT_NAME
        ).first()
        if cohort is None:
            cohort = cast(
                Cohort,
                CohortFactory(
                    site=site, organisation=organisations[ORG_ONE], name=COHORT_NAME
                ),
            )
            click.secho(f"Created cohort '{COHORT_NAME}'", fg="green")
        elif not cohort.is_active:
            cohort.is_active = True
            cohort.save(update_fields=["is_active"])
            click.secho(f"Reactivated cohort '{COHORT_NAME}'", fg="yellow")

        # Users and their learners; any learner of a qa_rec_ user in an
        # organisation outside the list goes.
        learners: dict[tuple[str, str], Learner] = {}
        for email, first, last, placements in LEARNERS:
            user = _ensure_learner_user(site, email, first, last)
            wanted_orgs = [organisations[org_name] for org_name, _ in placements]
            for org_name, _ in placements:
                learners[(email, org_name)] = cast(
                    Learner,
                    LearnerFactory(
                        site=site, user=user, organisation=organisations[org_name]
                    ),
                )
            extra = Learner._base_manager.filter(user=user).exclude(
                organisation__in=wanted_orgs
            )
            if extra.exists():
                _report(
                    f"CourseProgress of {email}'s extra learners",
                    CourseProgress._base_manager.filter(learner__in=extra).delete(),
                )
                _report(f"Extra Learner of {email}", extra.delete())

        # Registrations, cohort contents and progress.
        individual = LearnerCourseRegistration._base_manager.filter(
            course__in=courses.values()
        )
        cohort_regs = CohortCourseRegistration._base_manager.filter(
            course__in=courses.values()
        ) | CohortCourseRegistration._base_manager.filter(cohort=cohort)
        progress = (
            CourseProgress._base_manager.filter(
                learner__user__email__startswith=EMAIL_PREFIX
            )
            | CourseProgress._base_manager.filter(learner_registration__in=individual)
            | CourseProgress._base_manager.filter(cohort_registration__in=cohort_regs)
        )
        _report("CourseProgress", progress.delete())
        for registration in individual.select_related("learner__user", "course"):
            click.secho(
                f"Deleting registration {registration.pk}: "
                f"{registration.learner.user.email} / {registration.course.title}",
                fg="yellow",
            )
        _report("LearnerCourseRegistration", individual.delete())
        for cohort_registration in cohort_regs.select_related("cohort", "course"):
            click.secho(
                f"Deleting cohort registration {cohort_registration.pk}: "
                f"{cohort_registration.cohort.name} / "
                f"{cohort_registration.course.title}",
                fg="yellow",
            )
        _report("CohortCourseRegistration", cohort_regs.delete())
        _report(
            f"CohortMembership of '{COHORT_NAME}'",
            CohortMembership._base_manager.filter(cohort=cohort).delete(),
        )

        # HR rows are rebuilt, so they never pin a list entry being reconciled.
        _report(
            "LearnerHRAttributes",
            LearnerHRAttributes._base_manager.filter(
                learner__in=learners.values()
            ).delete(),
        )
        departments: dict[str, dict[str, ListEntry]] = {}
        for org_name, organisation in organisations.items():
            departments[org_name] = _ensure_list(
                site, organisation, Department, DepartmentFactory, DEPARTMENTS[org_name]
            )
            _ensure_list(site, organisation, JobTitle, JobTitleFactory, [])
            _ensure_list(site, organisation, Location, LocationFactory, [])

        for email, _, _, placements in LEARNERS:
            for org_name, department in placements:
                LearnerHRAttributesFactory(
                    site=site,
                    learner=learners[(email, org_name)],
                    job_title=None,
                    department=departments[org_name][department],
                    location=None,
                )

        for organisation in organisations.values():
            settings_row = OrganisationHRSettings._base_manager.filter(
                organisation=organisation
            ).first()
            if settings_row is None:
                OrganisationHRSettingsFactory(
                    site=site,
                    organisation=organisation,
                    registration_rules_enabled=True,
                )
            elif not settings_row.registration_rules_enabled:
                settings_row.registration_rules_enabled = True
                settings_row.save(update_fields=["registration_rules_enabled"])

        staff_registration = cast(
            LearnerCourseRegistration,
            LearnerCourseRegistrationFactory(
                site=site,
                learner=learners[(REGISTERED_EMAIL, ORG_ONE)],
                course=courses["audit"],
                is_active=True,
                self_registered=False,
            ),
        )
        staff_recommendation = cast(
            RecommendedCourse,
            RecommendedCourseFactory(
                site=site,
                user=learners[(STAFFREC_EMAIL, ORG_ONE)].user,
                course=courses["audit"],
            ),
        )

    # Outside the transaction: the registration's on-commit hook announces it.
    _report(
        "Notification",
        Notification._base_manager.filter(
            user__email__startswith=EMAIL_PREFIX
        ).delete(),
    )

    click.secho(f"\nSite: {site.name} ({site.domain}) pk {site.pk}", bold=True)
    click.echo(f"Superuser {ADMIN_EMAIL}: user {admin.pk}")
    for org_name, organisation in organisations.items():
        click.secho(f"{org_name}: {organisation.pk}", bold=True)
        for entry in departments[org_name].values():
            click.echo(f"  department {entry} -> {entry.pk}")
    for course in courses.values():
        click.echo(f"Course {course.title}: {course.pk} ({course.visibility})")
    click.echo(f"Cohort {cohort.name}: {cohort.pk}")
    for (email, org_name), learner in learners.items():
        click.echo(
            f"Learner {email} in {org_name}: learner {learner.pk}, "
            f"user {learner.user_id}"
        )
    click.echo(f"Staff registration: {staff_registration.pk}")
    click.echo(f"Staff recommendation: {staff_recommendation.pk}")
