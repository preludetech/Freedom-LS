"""Create (or reset) the two throwaway users a user-erasure QA run needs.

* ``qa_erase_blocked@email.com`` holds exactly one completed, answered
  ``FormProgress`` (a standalone sitting of an existing form), so erasing the
  account has a form sitting in its way.
* ``qa_erase_clean@email.com`` is a bare user: no ``FormProgress``, no
  ``Learner``, no registrations, cohort memberships or course progress.

Both are plain, verified, non-staff accounts whose password is the email
address (the DemoDev convention). A QA run may delete either user, so every run
recreates a missing one.

Re-running is idempotent AND destructive for these two accounts: it resets the
password and flags and strips every application, sitting, registration,
membership and (for the clean user) learner row they hold before rebuilding
the stated shape. It touches no other account.

Usage:
    uv run python manage.py qa_create_erase_users
    uv run python manage.py qa_create_erase_users \
        --site-name DemoDev --form-slug knowledge-check
"""

import djclick as click

from django.contrib.sites.models import Site
from django.db import transaction

from freedom_ls.accounts.models import User
from freedom_ls.form_engine.models import FormProgress, QuestionAnswer
from freedom_ls.learner_management.models import Learner
from freedom_ls.qa_helpers.management.commands.qa_create_clean_applicant import (
    _describe,
    _ensure_user,
    _ensure_verified_email,
    _get_site,
    _purge_course_data,
)
from freedom_ls.qa_helpers.management.commands.qa_create_standalone_form_sitting import (
    _get_form,
    _sit_standalone,
)

BLOCKED_EMAIL = "qa_erase_blocked@email.com"
CLEAN_EMAIL = "qa_erase_clean@email.com"
DEFAULT_SITE_NAME = "DemoDev"
DEFAULT_FORM_SLUG = "knowledge-check"


def _purge_learners(user: User) -> list[str]:
    """Delete the user's Learner rows, which `_purge_course_data` leaves behind.

    Runs after `_purge_course_data`, so the CourseProgress rows that PROTECT a
    Learner are already gone.
    """
    learners = Learner._base_manager.filter(user=user)
    lines = [f"Learner {learner.pk} (site={learner.site_id})" for learner in learners]
    if lines:
        lines.append(f"  -> deleted: {learners.delete()}")
    return lines


def _report(label: str, user: User, created: bool, removed: list[str]) -> None:
    verb = "Created" if created else "Reset"
    click.secho(f"\n== {label}: {verb} {user.email} ==", fg="cyan", bold=True)
    if removed:
        click.secho("Removed:", fg="red", bold=True)
        for line in removed:
            click.secho(f"  {line}", fg="red")
    else:
        click.secho("Removed: nothing (account held no QA residue).", fg="green")
    user.refresh_from_db()
    click.echo(f"  {_describe(user)}")
    click.echo(f"  learners={Learner._base_manager.filter(user=user).count()}")


@click.command()
@click.option(
    "--site-name",
    default=DEFAULT_SITE_NAME,
    help=f"Site the users live on (default: '{DEFAULT_SITE_NAME}').",
)
@click.option(
    "--form-slug",
    default=DEFAULT_FORM_SLUG,
    help=f"Form the blocked user has sat (default: '{DEFAULT_FORM_SLUG}').",
)
def command(site_name: str, form_slug: str) -> None:
    """Create or reset the erase-blocked and erase-clean QA users."""
    site: Site = _get_site(site_name)
    form = _get_form(form_slug, site)

    with transaction.atomic():
        blocked, blocked_created = _ensure_user(BLOCKED_EMAIL, site)
        _ensure_verified_email(blocked)
        blocked_removed = _purge_course_data(blocked)
        sitting = _sit_standalone(blocked, form, site)

        clean, clean_created = _ensure_user(CLEAN_EMAIL, site)
        _ensure_verified_email(clean)
        clean_removed = _purge_course_data(clean) + _purge_learners(clean)

    click.secho(f"\nSite: {site.name} ({site.domain}) [id {site.pk}]", fg="cyan")

    _report("Erase blocked", blocked, blocked_created, blocked_removed)
    answers = QuestionAnswer._base_manager.filter(form_progress=sitting).count()
    click.echo(
        f"  FormProgress pk={sitting.pk} form={form.title!r} [slug: {form.slug}] "
        f"completed={sitting.completed_time} answers={answers}"
    )

    _report("Erase clean", clean, clean_created, clean_removed)
    click.echo(
        f"  form_sittings={FormProgress._base_manager.filter(user=clean).count()}"
    )

    click.secho("\n== Login (password = email) ==", fg="cyan", bold=True)
    click.echo(f"  {BLOCKED_EMAIL} / {BLOCKED_EMAIL}")
    click.echo(f"  {CLEAN_EMAIL} / {CLEAN_EMAIL}")
