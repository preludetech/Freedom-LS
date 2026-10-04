"""Seed an educator-interface browsing data set on one site.

Run ``create_demo_data`` (Sites + admin) and ``content_save demo_content
<site>`` (courses) first. This command then builds, idempotently:

First organisation (the site's default organisation):
* 32 learners with realistic full names (``first.last@example.com``), so the
  learners table paginates past 25 rows. Password: ``testpass123``.
* "Educator QA Cohort Alpha" — 20 of those learners, registered on a course.
* "Educator QA Cohort Beta" — 8 learners (overlapping Alpha by 2), registered
  on a second course.
* 6 learners left in no cohort; 10 learners with a direct course registration.

Second organisation ("Northside Training"):
* 1 cohort with 5 learners, so the organisation switcher has a real target.

Usage:
    uv run python manage.py qa_create_educator_interface_seed
    uv run python manage.py qa_create_educator_interface_seed --site-name DemoDev
"""

from typing import cast

import djclick as click
from faker import Faker

from django.contrib.sites.models import Site

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
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
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.organisations.utils import get_default_organisation

PASSWORD = "testpass123"  # noqa: S105  # pragma: allowlist secret  # dev-only QA credential
NUM_LEARNERS = 32
ALPHA_NAME = "Educator QA Cohort Alpha"
BETA_NAME = "Educator QA Cohort Beta"
SECOND_ORG_NAME = "Northside Training"
SECOND_ORG_COHORT_NAME = "Northside Intake 2026"
ALPHA_COURSE_SLUG = "functionality-demo-course-parts"
BETA_COURSE_SLUG = "standard-markdown-demo-finance"
DIRECT_COURSE_SLUG = "functionality-demo-show-end-with-topic"


def _ensure_user(site: Site, first_name: str, last_name: str, email: str) -> User:
    user = User._base_manager.filter(site=site, email=email).first()
    if user is None:
        user = cast(
            User,
            UserFactory(
                site=site,
                email=email,
                first_name=first_name,
                last_name=last_name,
                password=PASSWORD,
            ),
        )
    return user


def _ensure_learners(
    site: Site, organisation: Organisation, prefix: str, count: int, seed: int
) -> list[Learner]:
    fake = Faker()
    Faker.seed(seed)
    learners: list[Learner] = []
    for i in range(1, count + 1):
        first, last = fake.first_name(), fake.last_name()
        email = f"{prefix}{i:02d}.{first}.{last}@example.com".lower()
        existing = User._base_manager.filter(
            site=site, email__startswith=f"{prefix}{i:02d}.".lower()
        ).first()
        user = existing or _ensure_user(site, first, last, email)
        learners.append(
            cast(
                Learner,
                LearnerFactory(site=site, user=user, organisation=organisation),
            )
        )
    return learners


def _ensure_cohort(site: Site, organisation: Organisation, name: str) -> Cohort:
    cohort = Cohort._base_manager.filter(
        site=site, organisation=organisation, name=name
    ).first()
    return cohort or cast(
        Cohort, CohortFactory(site=site, organisation=organisation, name=name)
    )


def _ensure_members(site: Site, cohort: Cohort, learners: list[Learner]) -> None:
    for learner in learners:
        if not CohortMembership._base_manager.filter(
            cohort=cohort, learner=learner
        ).exists():
            CohortMembershipFactory(site=site, cohort=cohort, learner=learner)


def _ensure_cohort_course(site: Site, cohort: Cohort, course: Course) -> None:
    if not CohortCourseRegistration._base_manager.filter(
        cohort=cohort, course=course
    ).exists():
        CohortCourseRegistrationFactory(site=site, cohort=cohort, course=course)


def _get_course(site: Site, slug: str) -> Course:
    course = Course._base_manager.filter(site=site, slug=slug).first()
    if course is None:
        raise click.ClickException(
            f"Course '{slug}' not found on site '{site.name}'. Run "
            f"`content_save demo_content {site.name}` first."
        )
    return course


@click.command()
@click.option("--site-name", default="DemoDev", help="Site name (default: DemoDev)")
def command(site_name: str) -> None:
    """Seed learners, cohorts and registrations for the educator interface."""
    site = Site.objects.filter(name=site_name).first()
    if site is None:
        raise click.ClickException(f"Site '{site_name}' not found.")

    alpha_course = _get_course(site, ALPHA_COURSE_SLUG)
    beta_course = _get_course(site, BETA_COURSE_SLUG)
    direct_course = _get_course(site, DIRECT_COURSE_SLUG)

    org = get_default_organisation(site)
    learners = _ensure_learners(site, org, "edqa", NUM_LEARNERS, seed=4242)

    alpha = _ensure_cohort(site, org, ALPHA_NAME)
    _ensure_members(site, alpha, learners[:20])
    _ensure_cohort_course(site, alpha, alpha_course)

    beta = _ensure_cohort(site, org, BETA_NAME)
    _ensure_members(site, beta, learners[18:26])
    _ensure_cohort_course(site, beta, beta_course)

    for learner in learners[:5] + learners[20:25]:
        if not LearnerCourseRegistration._base_manager.filter(
            learner=learner, course=direct_course
        ).exists():
            LearnerCourseRegistrationFactory(
                site=site, learner=learner, course=direct_course
            )

    second_org = Organisation._base_manager.filter(
        site=site, name=SECOND_ORG_NAME
    ).first() or cast(
        Organisation, OrganisationFactory(site=site, name=SECOND_ORG_NAME)
    )
    second_learners = _ensure_learners(site, second_org, "nsqa", 5, seed=99)
    second_cohort = _ensure_cohort(site, second_org, SECOND_ORG_COHORT_NAME)
    _ensure_members(site, second_cohort, second_learners)
    _ensure_cohort_course(site, second_cohort, alpha_course)

    click.secho(f"Site: {site.name} ({site.domain})", fg="green")
    for organisation, cohorts in (
        (org, [alpha, beta]),
        (second_org, [second_cohort]),
    ):
        click.secho(f"Organisation '{organisation.name}' slug={organisation.slug}")
        for cohort in cohorts:
            members = CohortMembership._base_manager.filter(cohort=cohort).count()
            click.secho(f"  cohort pk={cohort.pk} '{cohort.name}' members={members}")
    click.secho(
        f"Sample learner in Alpha: pk={learners[0].pk} {learners[0].user.email}"
    )
    click.secho(f"Learner password: {PASSWORD}")
