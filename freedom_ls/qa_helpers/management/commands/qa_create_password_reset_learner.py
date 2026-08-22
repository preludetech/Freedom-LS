"""Create a single login-ready learner for QA of the password-reset email.

The only requirement for a password reset at /accounts/password/reset/ to send
an email is that an active user with that email address exists. No course
enrolment or progress is needed, so this command creates nothing beyond the
User (and, for convenience, a verified+primary allauth EmailAddress so the
account is also usable for a normal login if the tester wants one).

Idempotent: re-running reuses the existing user, re-activates it, and resets
the password to the DemoDev convention (password == email address).

Usage:
    uv run python manage.py qa_create_password_reset_learner
    uv run python manage.py qa_create_password_reset_learner --site-name DemoDev
"""

from typing import cast

import djclick as click
from allauth.account.models import EmailAddress

from django.contrib.sites.models import Site

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User

LEARNER_EMAIL = "demodev_s1@email.com"


def _get_or_create_learner(site: Site) -> tuple[User, bool]:
    """Create the QA learner (password == email), or reuse the existing one.

    Returns (user, was_created). Email is globally unique on the User model, so
    we match on email alone and ensure the account is active and login-ready.
    """
    existing: User | None = User.objects.filter(email=LEARNER_EMAIL).first()
    if existing is not None:
        existing.is_active = True
        existing.set_password(LEARNER_EMAIL)
        existing.save(update_fields=["is_active", "password"])
        return existing, False

    user = cast(
        User,
        UserFactory(
            email=LEARNER_EMAIL,
            first_name="DemoDev",
            last_name="Learner One",
            is_active=True,
            password=LEARNER_EMAIL,
            site=site,
        ),
    )
    return user, True


def _ensure_verified_email(user: User) -> None:
    """Ensure a verified, primary allauth EmailAddress exists for the user."""
    EmailAddress.objects.update_or_create(
        user=user,
        email=user.email,
        defaults={"verified": True, "primary": True},
    )


@click.command()
@click.option(
    "--site-name",
    default="DemoDev",
    help="Site name to attach the user to (default: 'DemoDev').",
)
def command(site_name: str) -> None:
    """Create a login-ready learner for password-reset email QA."""
    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e

    learner, created = _get_or_create_learner(site)
    _ensure_verified_email(learner)

    click.secho("--- Password-reset QA learner ---", fg="cyan", bold=True)
    click.secho(
        f"{'Created' if created else 'Reused'}: {learner.email}",
        fg="green" if created else "yellow",
    )
    click.echo(f"  Email      : {learner.email}")
    click.echo(f"  Password   : {learner.email}")
    click.echo(f"  Active     : {learner.is_active}")
    click.echo(f"  Site       : {learner.site.name} ({learner.site.domain})")
    click.echo(f"  Reset page : http://{site.domain}/accounts/password/reset/")
