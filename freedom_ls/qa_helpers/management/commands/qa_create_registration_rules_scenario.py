"""Seed the registration rules frontend QA scenario (§0.2 of its QA plan).

Idempotent: re-running brings every record back to exactly the state below,
on the Site that ``demodev@email.com`` belongs to, and removes the residue a
previous QA run left behind.

- ``QA Org One`` (registration rules switched on) and ``QA Org Two`` (no
  OrganisationHRSettings row).
- QA Org One: departments Finance, Operations, Audit (inactive); locations
  Cape Town, Durban; job title Analyst. QA Org Two: department Finance.
- Courses ``QA Budgeting Basics`` (published, free, one topic) and
  ``QA Hidden Course`` (hidden).
- Learners (password == email, verified email):
  - QA Org One: qa_rule_finance, qa_rule_newhire, qa_rule_ops,
    qa_rule_durban, qa_rule_audit, qa_rule_staff (holding a staff-made
    registration for QA Budgeting Basics), qa_rule_blank (no HR row).
  - QA Org Two: qa_rule_other.

Deleted on every run: every RegistrationRule (with its conditions and
RuleRegistration rows), the qa_rule_joiner@email.com user, every other
registration for the two QA courses, all course progress of qa_rule_*
learners, staff users holding nothing but "Can view registration rule", and
the notifications of qa_rule_* users.

Usage:
    uv run python manage.py qa_create_registration_rules_scenario
"""

from datetime import date
from typing import cast

import djclick as click

from django.contrib.auth.models import Permission
from django.contrib.sites.models import Site
from django.db import transaction

from freedom_ls.accounts.models import User
from freedom_ls.comms.models import Notification
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course, CourseVisibility
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
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import Learner, LearnerCourseRegistration
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.qa_helpers.management.commands.qa_create_hr_attributes_scenario import (
    ListEntry,
    _ensure_learner_user,
    _ensure_list,
    _ensure_organisation,
)
from freedom_ls.registration_rules.models import (
    AttributeRuleConditions,
    RegistrationRule,
    RuleRegistration,
)

ADMIN_EMAIL = "demodev@email.com"
ORG_ONE = "QA Org One"
ORG_TWO = "QA Org Two"
EMAIL_PREFIX = "qa_rule_"
JOINER_EMAIL = "qa_rule_joiner@email.com"
STAFF_LEARNER_EMAIL = "qa_rule_staff@email.com"
VIEW_PERMISSION = "view_registrationrule"

BUDGETING_TITLE = "QA Budgeting Basics"
BUDGETING_SLUG = "qa-budgeting-basics"
HIDDEN_TITLE = "QA Hidden Course"
HIDDEN_SLUG = "qa-hidden-course"

JOB_TITLES: dict[str, list[tuple[str, bool]]] = {
    ORG_ONE: [("Analyst", True)],
    ORG_TWO: [],
}
DEPARTMENTS = {
    ORG_ONE: [("Finance", True), ("Operations", True), ("Audit", False)],
    ORG_TWO: [("Finance", True)],
}
LOCATIONS: dict[str, list[tuple[str, bool]]] = {
    ORG_ONE: [("Cape Town", True), ("Durban", True)],
    ORG_TWO: [],
}

# email, first, last, organisation, HR row (department, location, start) or None.
LEARNERS: list[
    tuple[str, str, str, str, tuple[str, str | None, date | None] | None]
] = [
    (
        "qa_rule_finance@email.com",
        "Fiona",
        "Finance",
        ORG_ONE,
        ("Finance", "Cape Town", date(2022, 1, 15)),
    ),
    (
        "qa_rule_newhire@email.com",
        "Nandi",
        "Newhire",
        ORG_ONE,
        ("Finance", "Cape Town", date(2026, 9, 1)),
    ),
    (
        "qa_rule_ops@email.com",
        "Olwethu",
        "Ops",
        ORG_ONE,
        ("Operations", "Cape Town", None),
    ),
    (
        "qa_rule_durban@email.com",
        "Dumisani",
        "Durban",
        ORG_ONE,
        ("Finance", "Durban", None),
    ),
    (
        "qa_rule_audit@email.com",
        "Aisha",
        "Audit",
        ORG_ONE,
        ("Audit", "Cape Town", None),
    ),
    (
        "qa_rule_staff@email.com",
        "Sipho",
        "Staff",
        ORG_ONE,
        ("Finance", "Cape Town", None),
    ),
    ("qa_rule_blank@email.com", "Busi", "Blank", ORG_ONE, None),
    ("qa_rule_other@email.com", "Olivia", "Other", ORG_TWO, ("Finance", None, None)),
]


def _ensure_course(
    site: Site, *, title: str, slug: str, visibility: str, with_topic: bool
) -> Course:
    course = Course._base_manager.filter(site=site, slug=slug).first()
    if course is None:
        course = cast(
            Course,
            CourseFactory(
                site=site,
                title=title,
                slug=slug,
                visibility=visibility,
                access_config={"access_type": "free"},
            ),
        )
        click.secho(f"Created course '{title}'", fg="green")
    else:
        course.title = title
        course.visibility = visibility
        course.access_config = {"access_type": "free"}
        course.save(update_fields=["title", "visibility", "access_config"])
    if with_topic and not course.viewable_items():
        topic = TopicFactory(
            site=site,
            title=f"{title} - Introduction",
            content="# Welcome\n\nA QA topic so the course can be opened.",
        )
        ContentCollectionItemFactory(
            site=site, collection_object=course, child_object=topic
        )
        click.secho(f"Added a topic to '{title}'", fg="green")
    return course


def _delete_rules() -> None:
    click.secho(
        f"RuleRegistration deleted: {RuleRegistration._base_manager.all().delete()}",
        fg="yellow",
    )
    click.secho(
        "AttributeRuleConditions deleted: "
        f"{AttributeRuleConditions._base_manager.all().delete()}",
        fg="yellow",
    )
    for rule in RegistrationRule._base_manager.all():
        click.secho(f"Deleting rule {rule.pk} '{rule}'", fg="yellow")
    click.secho(
        f"RegistrationRule deleted: {RegistrationRule._base_manager.all().delete()}",
        fg="yellow",
    )


def _delete_user(user: User, reason: str) -> None:
    """Delete a user, clearing the PROTECTed course progress of its learners first."""
    progress = CourseProgress._base_manager.filter(learner__user=user).delete()
    click.secho(
        f"Deleting {reason} {user.pk} '{user.email}': progress {progress}, "
        f"user {user.delete()}",
        fg="yellow",
    )


def _view_only_staff() -> list[User]:
    """Non-superusers whose only grant is the direct "view registration rule"."""
    permission = Permission.objects.get(codename=VIEW_PERMISSION)
    found = []
    for user in User._base_manager.filter(
        is_superuser=False, user_permissions=permission
    ).distinct():
        codenames = set(user.user_permissions.values_list("codename", flat=True))
        if codenames == {VIEW_PERMISSION} and not user.groups.exists():
            found.append(user)
        else:
            click.secho(
                f"Left staff user {user.email}: holds more than view rule ({codenames})",
                fg="red",
            )
    return found


@click.command()
def command() -> None:
    """Seed the registration rules QA scenario on demodev@email.com's Site."""
    admin = User._base_manager.filter(email=ADMIN_EMAIL).first()
    if admin is None:
        raise click.ClickException(
            f"{ADMIN_EMAIL} not found. Run `uv run python manage.py "
            "create_demo_data --yes` first."
        )
    site = admin.site

    with transaction.atomic():
        # Rules first: a rule naming a list entry would block reconciling it,
        # and no learner-side save below should evaluate a stale rule.
        _delete_rules()

        for user in User._base_manager.filter(email=JOINER_EMAIL):
            _delete_user(user, "joiner user")
        for user in _view_only_staff():
            _delete_user(user, "view-only staff user")

        org_one = _ensure_organisation(site, ORG_ONE)
        org_two = _ensure_organisation(site, ORG_TWO)
        organisations = {ORG_ONE: org_one, ORG_TWO: org_two}

        budgeting = _ensure_course(
            site,
            title=BUDGETING_TITLE,
            slug=BUDGETING_SLUG,
            visibility=CourseVisibility.PUBLISHED,
            with_topic=True,
        )
        hidden = _ensure_course(
            site,
            title=HIDDEN_TITLE,
            slug=HIDDEN_SLUG,
            visibility=CourseVisibility.HIDDEN,
            with_topic=False,
        )

        learners: dict[str, Learner] = {}
        for email, first, last, org_name, _ in LEARNERS:
            user = _ensure_learner_user(site, email, first, last)
            learners[email] = cast(
                Learner,
                LearnerFactory(
                    site=site, user=user, organisation=organisations[org_name]
                ),
            )

        # Registrations and progress: every registration for the QA courses
        # goes (the staff learner's is rebuilt below), and so does every
        # progress record of a qa_rule_* learner.
        registrations = LearnerCourseRegistration._base_manager.filter(
            course__in=[budgeting, hidden]
        )
        progress = CourseProgress._base_manager.filter(
            learner__user__email__startswith=EMAIL_PREFIX
        ) | CourseProgress._base_manager.filter(learner_registration__in=registrations)
        click.secho(f"CourseProgress deleted: {progress.delete()}", fg="yellow")
        for registration in registrations.select_related("learner__user", "course"):
            click.secho(
                f"Deleting registration {registration.pk}: "
                f"{registration.learner.user.email} / {registration.course.title}",
                fg="yellow",
            )
        click.secho(
            f"LearnerCourseRegistration deleted: {registrations.delete()}", fg="yellow"
        )

        click.secho(
            "LearnerHRAttributes deleted: "
            f"{LearnerHRAttributes._base_manager.filter(learner__in=learners.values()).delete()}",
            fg="yellow",
        )

        lists: dict[str, dict[str, dict[str, ListEntry]]] = {}
        for org_name, organisation in organisations.items():
            lists[org_name] = {
                "job_titles": _ensure_list(
                    site, organisation, JobTitle, JobTitleFactory, JOB_TITLES[org_name]
                ),
                "departments": _ensure_list(
                    site,
                    organisation,
                    Department,
                    DepartmentFactory,
                    DEPARTMENTS[org_name],
                ),
                "locations": _ensure_list(
                    site, organisation, Location, LocationFactory, LOCATIONS[org_name]
                ),
            }

        for email, _, _, org_name, hr in LEARNERS:
            if hr is None:
                continue
            department, location, start = hr
            org_lists = lists[org_name]
            LearnerHRAttributesFactory(
                site=site,
                learner=learners[email],
                job_title=None,
                department=org_lists["departments"][department],
                location=org_lists["locations"][location] if location else None,
                organisation_start_date=start,
            )

        click.secho(
            "OrganisationHRSettings (QA Org Two) deleted: "
            f"{OrganisationHRSettings._base_manager.filter(organisation=org_two).delete()}",
            fg="yellow",
        )
        settings_row = OrganisationHRSettings._base_manager.filter(
            organisation=org_one
        ).first()
        if settings_row is None:
            OrganisationHRSettingsFactory(
                site=site, organisation=org_one, registration_rules_enabled=True
            )
        elif not settings_row.registration_rules_enabled:
            settings_row.registration_rules_enabled = True
            settings_row.save(update_fields=["registration_rules_enabled"])

        staff_registration = cast(
            LearnerCourseRegistration,
            LearnerCourseRegistrationFactory(
                site=site,
                learner=learners[STAFF_LEARNER_EMAIL],
                course=budgeting,
                is_active=True,
                self_registered=False,
            ),
        )

    # Outside the transaction: the registration's on-commit hook announces it.
    click.secho(
        "Notification deleted: "
        f"{Notification._base_manager.filter(user__email__startswith=EMAIL_PREFIX).delete()}",
        fg="yellow",
    )

    click.secho(f"\nSite: {site.name} ({site.domain})", bold=True)
    for org_name, organisation in organisations.items():
        click.secho(f"{org_name}: {organisation.pk}", bold=True)
        for list_name, entries in lists[org_name].items():
            for entry in entries.values():
                click.echo(f"  {list_name}: {entry} -> {entry.pk}")
    click.echo(f"Course {budgeting.title}: {budgeting.pk}")
    click.echo(f"Course {hidden.title}: {hidden.pk}")
    click.echo(f"Staff registration: {staff_registration.pk}")
    for email, learner in learners.items():
        click.echo(f"Learner {email}: learner {learner.pk}, user {learner.user_id}")
