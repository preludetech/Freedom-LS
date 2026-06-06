"""Create a minimal educator + cohort so the educator interface shows a c-modal.

Sets up ONE reachable ``c-modal`` trigger for frontend QA of the shared modal
scrim. Specifically it creates an educator who can reach the cohort detail page
and see the ``DeleteAction`` button, which opens the
``panel_framework/partials/delete_confirmation.html`` modal (a ``<c-modal>``).

The educator is granted object-level ``view_cohort`` (so the cohort appears in
the list and the detail page loads) and ``delete_cohort`` (so the Delete action
renders) on the created cohort. A single student member plus a course
registration give the delete-confirmation modal a cascade summary to show.

Idempotent: re-running reuses existing records by email / name.
"""

from typing import cast

import djclick as click
from allauth.account.models import EmailAddress
from guardian.shortcuts import assign_perm

from django.contrib.sites.models import Site

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course
from freedom_ls.student_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
)
from freedom_ls.student_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
)

EDUCATOR_EMAIL = "qa_educator@example.com"
STUDENT_EMAIL = "qa_modal_student@example.com"
COHORT_NAME = "QA Modal Cohort"


def _get_or_create_user(
    site: Site, email: str, first_name: str, last_name: str
) -> User:
    """Create a login-ready user (password == email), or return the existing one."""
    existing: User | None = User.objects.filter(email=email).first()
    if existing is not None:
        existing.is_active = True
        existing.set_password(email)
        existing.save(update_fields=["is_active", "password"])
        return existing
    return cast(
        User,
        UserFactory(
            email=email,
            first_name=first_name,
            last_name=last_name,
            is_active=True,
            password=email,
            site=site,
        ),
    )


def _ensure_verified_email(user: User) -> None:
    """Ensure a verified, primary EmailAddress exists (allauth login requires it)."""
    EmailAddress.objects.update_or_create(
        user=user,
        email=user.email,
        defaults={"verified": True, "primary": True},
    )


@click.command()
@click.argument("site_name")
def command(site_name: str) -> None:
    """Set up ONE reachable c-modal trigger in the educator interface.

    SITE_NAME is the name of the site to create data on (e.g. 'DemoDev').
    """
    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e

    # Educator user, login-ready.
    educator = _get_or_create_user(site, EDUCATOR_EMAIL, "Quinn", "Educator")
    _ensure_verified_email(educator)
    click.secho(f"Educator: {EDUCATOR_EMAIL} (password == email)", fg="green")

    # Cohort the educator manages.
    cohort: Cohort | None = Cohort.objects.filter(name=COHORT_NAME, site=site).first()
    if cohort is None:
        cohort = cast(Cohort, CohortFactory(name=COHORT_NAME, site=site))
        click.secho(f"Created cohort '{COHORT_NAME}'", fg="green")
    else:
        click.secho(f"Reusing cohort '{COHORT_NAME}'", fg="yellow")

    # Object-level perms: view (list + detail page) and delete (renders the modal).
    assign_perm("view_cohort", educator, cohort)
    assign_perm("delete_cohort", educator, cohort)
    click.secho("Assigned view_cohort + delete_cohort on cohort", fg="green")

    # One student member so the cohort is non-empty and the delete modal has a
    # cascade summary to display.
    student = _get_or_create_user(site, STUDENT_EMAIL, "Sam", "Student")
    if not CohortMembership.objects.filter(
        user=student, cohort=cohort, site=site
    ).exists():
        CohortMembershipFactory(user=student, cohort=cohort, site=site)
        click.secho(f"Added student member {STUDENT_EMAIL}", fg="green")
    else:
        click.secho(f"Student {STUDENT_EMAIL} already a member", fg="yellow")

    # Register the cohort for a course (gives the cascade summary an item).
    course = Course.objects.filter(site=site).order_by("title").first()
    if course is not None:
        if not CohortCourseRegistration.objects.filter(
            cohort=cohort, collection=course, site=site
        ).exists():
            CohortCourseRegistrationFactory(cohort=cohort, collection=course, site=site)
            click.secho(f"Registered cohort for '{course.title}'", fg="green")
        else:
            click.secho(f"Already registered for '{course.title}'", fg="yellow")
    else:
        click.secho("No course found on site; skipping registration", fg="yellow")

    click.secho("\n--- Summary ---", fg="cyan", bold=True)
    click.secho(f"Site: {site.name} ({site.domain})", fg="cyan")
    click.secho(
        f"Educator login: {EDUCATOR_EMAIL} / {EDUCATOR_EMAIL}", fg="green", bold=True
    )
    click.secho(f"Cohort: {COHORT_NAME} (pk={cohort.pk})", fg="cyan")
    click.secho(
        f"\nc-modal trigger: visit /educator/cohorts/{cohort.pk}", fg="cyan", bold=True
    )
    click.secho(
        "  Click the red 'Delete' button (top of the page) to open the "
        "delete-confirmation c-modal.",
        fg="cyan",
    )
