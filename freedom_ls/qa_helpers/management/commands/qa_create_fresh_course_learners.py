"""Create (or reset) login-ready learners registered on courses, with no form attempts.

For QA of a course's quizzes from a clean start: each learner is active, has a
verified primary email (allauth), is registered individually on every given
course in the site's default organisation, and owns no ``FormProgress`` for any
form in those courses. Re-running resets an existing learner to that state:
their password is set again and their attempts on those courses' forms are
deleted (printed first, with the cascade counts). Nothing outside the given
courses is touched.

The password is a development-only value, never a real credential.

Usage:
    uv run python manage.py qa_create_fresh_course_learners DemoDev \
        --email qa-learner-a@example.com --email qa-learner-b@example.com \
        --course-slug functionality-demo-shuffled-quiz \
        --course-slug functionality-demo-show-end-with-quiz
"""

from typing import cast

import djclick as click
from allauth.account.models import EmailAddress

from django.contrib.sites.models import Site

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course
from freedom_ls.form_engine.models import Form, FormProgress
from freedom_ls.qa_helpers.management.commands.qa_create_dashboard_paging_fixtures import (
    _get_course,
    _get_site,
    _register,
)

DEV_PASSWORD = "testpass123"  # noqa: S105  # pragma: allowlist secret  # dev-only QA credential


def _ensure_user(site: Site, email: str, password: str) -> User:
    """The learner, created or refreshed to active with the given password."""
    existing: User | None = User.objects.filter(email=email).first()
    if existing is not None:
        if existing.site_id != site.pk:
            raise click.ClickException(
                f"User '{email}' exists on site id {existing.site_id}, "
                f"not '{site.name}'."
            )
        existing.is_active = True
        existing.set_password(password)
        existing.save(update_fields=["is_active", "password"])
        user = existing
    else:
        local = email.split("@", 1)[0]
        user = cast(
            User,
            UserFactory(
                email=email,
                first_name="QA",
                last_name=local,
                is_active=True,
                password=password,
                site=site,
            ),
        )
    EmailAddress.objects.update_or_create(
        user=user,
        email=user.email,
        defaults={"verified": True, "primary": True},
    )
    return user


def _course_forms(courses: list[Course]) -> list[Form]:
    return [
        item
        for course in courses
        for item in course.viewable_items()
        if isinstance(item, Form)
    ]


def _clear_form_progress(user: User, forms: list[Form]) -> None:
    """Print, delete and confirm the user's FormProgress rows on these forms."""
    rows = FormProgress.objects.filter(user=user, form__in=forms).select_related("form")
    found = list(rows)
    click.echo(f"  FormProgress rows found: {len(found)}")
    for row in found:
        click.echo(
            f"    removing {row.pk} form={row.form.slug} "
            f"completed={row.completed_time} site_id={row.site_id}"
        )
    if found:
        total, per_model = rows.delete()
        click.echo(f"    deleted {total} row(s): {per_model}")
    remaining = FormProgress.objects.filter(user=user, form__in=forms).count()
    click.echo(f"  FormProgress rows remaining: {remaining}")


@click.command()
@click.argument("site_name", default="DemoDev")
@click.option("--email", "emails", multiple=True, required=True, help="Repeatable.")
@click.option(
    "--course-slug", "course_slugs", multiple=True, required=True, help="Repeatable."
)
@click.option("--password", default=DEV_PASSWORD, show_default=True)
def command(
    site_name: str,
    emails: tuple[str, ...],
    course_slugs: tuple[str, ...],
    password: str,
) -> None:
    """Create or reset learners registered on courses with no form attempts."""
    site = _get_site(site_name)
    courses = [_get_course(site, slug) for slug in course_slugs]
    forms = _course_forms(courses)
    click.secho(f"Site: {site.name} ({site.domain})", fg="cyan", bold=True)
    click.echo("Forms in scope: " + ", ".join(form.slug for form in forms))

    for email in emails:
        user = _ensure_user(site, email, password)
        click.secho(f"\nLearner {email} (pk {user.pk})", fg="green", bold=True)
        for course in courses:
            _register(user, course, site)
            click.echo(f"  registered on {course.title} ({course.slug})")
        _clear_form_progress(user, forms)
