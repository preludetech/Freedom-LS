"""Register an existing user for a course *through a named Organisation*.

A Course has no Organisation FK of its own. The organisation a learner is
studying a course through is resolved by
``learner_management.queries.organisation_for_learner_course``:

1. an active ``CohortCourseRegistration`` whose Cohort the learner belongs to
   (the cohort's organisation wins), else
2. the latest ``LearnerCourseRegistration`` -> ``Learner.organisation``.

So "a course belonging to RPAS Training" means "this user holds a registration
for this course through a Learner row in RPAS Training". That is what this
command builds, which is also what makes the co-branding chip in the course
table-of-contents header (``learner_interface/partials/course_toc_header.html``,
rendered in the course-player sidebar) show that organisation's logo/monogram.

Registering also exempts the user from ``coming_soon`` / ``hidden`` visibility
(``VisibilityEnforcingBackend``), so the player is reachable either way.

Idempotent: re-running reactivates the existing Learner / registration.

Usage:
    uv run python manage.py qa_register_org_course \
        --learner-email demodev@email.com \
        --organisation "RPAS Training" \
        --course-slug content-widgets-demo-reference
"""

import djclick as click

from django.contrib.sites.models import Site

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course
from freedom_ls.learner_management.factories import (
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import LearnerCourseRegistration
from freedom_ls.organisations.models import Organisation


@click.command()
@click.option("--site-name", default="DemoDev", help="Site the data belongs to.")
@click.option("--learner-email", required=True, help="Email of an existing user.")
@click.option("--organisation", "organisation_name", required=True, help="Org name.")
@click.option("--course-slug", required=True, help="Slug of an existing course.")
def command(
    site_name: str, learner_email: str, organisation_name: str, course_slug: str
) -> None:
    """Register LEARNER_EMAIL for COURSE_SLUG through ORGANISATION."""
    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e

    try:
        user = User.objects.get(email=learner_email, site=site)
    except User.DoesNotExist as e:
        raise click.ClickException(
            f"User '{learner_email}' not found on site '{site_name}'."
        ) from e

    try:
        organisation = Organisation.objects.get(name=organisation_name, site=site)
    except Organisation.DoesNotExist as e:
        available = list(
            Organisation.objects.filter(site=site).values_list("name", flat=True)
        )
        raise click.ClickException(
            f"Organisation '{organisation_name}' not found on site "
            f"'{site_name}'. Available: {available}"
        ) from e

    try:
        course = Course.objects.get(slug=course_slug, site=site)
    except Course.DoesNotExist as e:
        raise click.ClickException(
            f"Course '{course_slug}' not found on site '{site_name}'."
        ) from e

    learner = LearnerFactory(user=user, organisation=organisation, site=site)

    registration = LearnerCourseRegistration.objects.filter(
        learner=learner, course=course
    ).first()
    if registration is None:
        LearnerCourseRegistrationFactory(
            learner=learner, course=course, site=site, is_active=True
        )
        verb = "Registered"
    else:
        if not registration.is_active:
            registration.is_active = True
            registration.save(update_fields=["is_active"])
        verb = "Reused registration for"

    click.secho(
        f"{verb} {user.email} on '{course.title}' ({course.slug}) "
        f"through organisation '{organisation.name}'.",
        fg="green",
    )
    click.secho(f"  Player URL: /courses/{course.slug}/1/", fg="cyan")
