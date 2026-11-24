"""Seed one learner whose Overview > Registrations panel shows every row kind.

The educator learner Overview tab's Registrations panel
(``LearnerRegistrationsPanel``, ``freedom_ls/educator_interface/panels/learner/data_table_panels.py``)
renders three kinds of row, and this command gives one learner one of each:

1. an active individual ``LearnerCourseRegistration`` -- shows Deactivate;
2. an inactive individual ``LearnerCourseRegistration`` on a course available
   to the learner's organisation (``available_to_organisation_expression``),
   which is what ``RegistrationRow.can_reactivate`` needs -- shows Reactivate;
3. a ``CohortCourseRegistration`` through an active cohort the learner belongs
   to -- shows "via <cohort>" with no button.

The cohort is a dedicated one, so adding its course registration touches no
other learner. Courses come from ``demo_content`` (load it with
``content_save demo_content <site>``) and must have no owning organisation, so
they are available to the default organisation.

Idempotent: the user is matched on email, the cohort on name, registrations on
``(learner, course)``. Re-running restores each registration's ``is_active``.

Usage:
    uv run python manage.py qa_create_learner_registrations_panel
    uv run python manage.py qa_create_learner_registrations_panel DemoDev \
        --email qa_registrations@example.com
"""

from typing import cast

import djclick as click

from django.contrib.sites.models import Site

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course
from freedom_ls.learner_management.factories import CohortMembershipFactory
from freedom_ls.learner_management.models import (
    Cohort,
    CohortMembership,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.learner_management.queries import (
    available_to_organisation_expression,
)
from freedom_ls.learner_management.utils import ensure_learner
from freedom_ls.organisations.utils import get_default_organisation
from freedom_ls.qa_helpers.management.commands.qa_create_cohort_administration_scenario import (
    _ensure_cohort,
    _ensure_cohort_registration,
)
from freedom_ls.qa_helpers.management.commands.qa_create_dashboard_paging_fixtures import (
    _get_course,
    _get_or_create_user,
    _get_site,
    _register,
)

DEFAULT_EMAIL = "qa_registrations@example.com"
FIRST_NAME = "Registrations"
LAST_NAME = "QA"
COHORT_NAME = "QA Registrations Cohort"
ACTIVE_COURSE_SLUG = "functionality-demo-show-end-with-topic"
INACTIVE_COURSE_SLUG = "functionality-demo-show-end-with-quiz"
COHORT_COURSE_SLUG = "standard-markdown-demo-finance"


def _ensure_membership(
    site: Site, cohort: Cohort, learner: Learner
) -> CohortMembership:
    existing: CohortMembership | None = CohortMembership._base_manager.filter(
        cohort=cohort, learner=learner
    ).first()
    if existing is not None:
        return existing
    return cast(
        CohortMembership,
        CohortMembershipFactory(site=site, cohort=cohort, learner=learner),
    )


def _individual(
    user: User, course: Course, site: Site, is_active: bool
) -> LearnerCourseRegistration:
    """The learner's individual registration on ``course``, set to ``is_active``."""
    _register(user, course, site)
    registration: LearnerCourseRegistration = (
        LearnerCourseRegistration._base_manager.get(
            learner__user=user, course=course, site=site
        )
    )
    if registration.is_active != is_active:
        registration.is_active = is_active
        registration.save(update_fields=["is_active"])
    return registration


@click.command()
@click.argument("site_name", default="DemoDev")
@click.option("--email", default=DEFAULT_EMAIL, show_default=True)
def command(site_name: str, email: str) -> None:
    """Create the Registrations-panel learner on SITE_NAME (default: DemoDev)."""
    site = _get_site(site_name)
    organisation = get_default_organisation(site)
    courses = {
        slug: _get_course(site, slug)
        for slug in (ACTIVE_COURSE_SLUG, INACTIVE_COURSE_SLUG, COHORT_COURSE_SLUG)
    }
    unavailable = set(courses) - set(
        Course._base_manager.filter(pk__in=[c.pk for c in courses.values()])
        .filter(available_to_organisation_expression(organisation))
        .values_list("slug", flat=True)
    )
    if unavailable:
        raise click.ClickException(
            f"Not available to {organisation.slug}: {sorted(unavailable)}"
        )

    user = _get_or_create_user(site, email, FIRST_NAME, LAST_NAME)
    learner = ensure_learner(user, organisation)
    active = _individual(user, courses[ACTIVE_COURSE_SLUG], site, is_active=True)
    inactive = _individual(user, courses[INACTIVE_COURSE_SLUG], site, is_active=False)
    cohort = _ensure_cohort(site, organisation, COHORT_NAME)
    membership = _ensure_membership(site, cohort, learner)
    cohort_registration = _ensure_cohort_registration(
        site, cohort, courses[COHORT_COURSE_SLUG]
    )

    click.secho("\n--- Registrations panel learner ---", fg="cyan", bold=True)
    click.echo(f"Site:          {site.name} [id {site.pk}]")
    click.echo(f"Organisation:  {organisation.name} ({organisation.slug})")
    click.echo(f"Login:         {email} / {email}")
    click.echo(f"User:          {user.pk}")
    click.echo(f"Learner:       {learner.pk}")
    click.echo(f"Active reg:    {active.pk} -> {courses[ACTIVE_COURSE_SLUG].title}")
    click.echo(f"Inactive reg:  {inactive.pk} -> {courses[INACTIVE_COURSE_SLUG].title}")
    click.echo(f"Cohort:        {cohort.pk} {cohort.name}")
    click.echo(f"Membership:    {membership.pk}")
    click.echo(
        f"Cohort reg:    {cohort_registration.pk} -> "
        f"{courses[COHORT_COURSE_SLUG].title}"
    )
    click.echo(
        f"Overview:      /educator/organisations/{organisation.slug}"
        f"/learners/{learner.pk}/"
    )
