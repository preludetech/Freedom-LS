"""Create the three edge-case accounts for the admin CSV export QA run.

Seeds (or resets to a known state) three accounts on the given site:

- ``qa_nobody@email.com``    -- ``is_staff`` bystander with no permissions, no
  groups and ``last_login`` NULL (never logged in). Verified+primary
  allauth ``EmailAddress``.
- ``unverified@example.com`` -- plain learner whose allauth ``EmailAddress``
  is ``verified=False``.
- ``Mixed.Case@example.com`` -- plain learner whose ``User.email`` keeps its
  capitalisation while the allauth ``EmailAddress`` is lowercase
  ``mixed.case@example.com`` (verified+primary).

DemoDev-only convention: each password equals the account's own email address.

Re-running is idempotent: users are looked up case-insensitively by email and
reset (flags, password, permissions, groups; ``last_login`` for the bystander),
and the named ``EmailAddress`` rows are update-or-created. Nothing is deleted.

Usage:
    uv run python manage.py qa_create_export_edge_users
    uv run python manage.py qa_create_export_edge_users --site-name DemoDev
"""

from typing import cast

import djclick as click
from allauth.account.models import EmailAddress

from django.contrib.sites.models import Site
from django.db import transaction

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.learner_management.factories import LearnerFactory
from freedom_ls.organisations.utils import get_default_organisation

NOBODY_EMAIL = "qa_nobody@email.com"
UNVERIFIED_EMAIL = "unverified@example.com"
MIXED_CASE_EMAIL = "Mixed.Case@example.com"
MIXED_CASE_ALLAUTH_EMAIL = "mixed.case@example.com"


def _ensure_user(email: str, site: Site, *, is_staff: bool) -> tuple[User, bool]:
    """Create or reset a User on the site. Returns (user, was_created).

    Case-insensitive lookup through _base_manager: outside a request there is
    no ambient site, and a differently-cased row would otherwise produce a
    second account instead of a reset.
    """
    user = User._base_manager.filter(email__iexact=email).first()
    if user is None:
        created_user = cast(
            User,
            UserFactory(
                email=email,
                is_active=True,
                is_staff=is_staff,
                is_superuser=False,
                password=email,
                site=site,
            ),
        )
        return created_user, True

    user.email = email
    user.site = site
    user.is_active = True
    user.is_staff = is_staff
    user.is_superuser = False
    user.set_password(email)
    user.save()
    return user, False


def _ensure_email_address(
    user: User, email: str, *, verified: bool, primary: bool
) -> None:
    EmailAddress.objects.update_or_create(
        user=user,
        email=email,
        defaults={"verified": verified, "primary": primary},
    )


def _describe(user: User) -> str:
    addresses = [
        f"({a.email}, verified={a.verified}, primary={a.primary})"
        for a in EmailAddress.objects.filter(user=user).order_by("email")
    ]
    perms = list(user.user_permissions.values_list("codename", flat=True))
    groups = list(user.groups.values_list("name", flat=True))
    return (
        f"pk={user.pk} email={user.email!r} site={user.site.name} "
        f"is_staff={user.is_staff} is_superuser={user.is_superuser} "
        f"is_active={user.is_active} last_login={user.last_login}\n"
        f"      permissions={perms or 'none'} groups={groups or 'none'}\n"
        f"      EmailAddress rows: {', '.join(addresses) or 'none'}"
    )


@click.command()
@click.option("--site-name", default="DemoDev", help="Site name (default: 'DemoDev')")
def command(site_name: str) -> None:
    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        raise click.ClickException(f"Site with name '{site_name}' not found.") from e

    organisation = get_default_organisation(site)
    click.secho(f"Site: {site.name} (id={site.pk}, {site.domain})", fg="cyan")

    with transaction.atomic():
        nobody, created = _ensure_user(NOBODY_EMAIL, site, is_staff=True)
        nobody.last_login = None
        nobody.save(update_fields=["last_login"])
        nobody.user_permissions.clear()
        nobody.groups.clear()
        _ensure_email_address(nobody, NOBODY_EMAIL, verified=True, primary=True)
        click.echo(f"  {'Created' if created else 'Reset'} {NOBODY_EMAIL}")

        for email, address, verified in (
            (UNVERIFIED_EMAIL, UNVERIFIED_EMAIL, False),
            (MIXED_CASE_EMAIL, MIXED_CASE_ALLAUTH_EMAIL, True),
        ):
            user, created = _ensure_user(email, site, is_staff=False)
            user.user_permissions.clear()
            user.groups.clear()
            _ensure_email_address(user, address, verified=verified, primary=True)
            LearnerFactory(user=user, organisation=organisation, site=site)
            click.echo(f"  {'Created' if created else 'Reset'} {email}")

    click.echo("")
    click.secho("== Final state ==", fg="cyan", bold=True)
    for email in (NOBODY_EMAIL, UNVERIFIED_EMAIL, MIXED_CASE_EMAIL):
        user = User._base_manager.select_related("site").get(email__iexact=email)
        click.echo(f"  {_describe(user)}")

    click.echo("")
    click.echo(f"  Site     : http://{site.domain}/")
    click.echo("  Password : same as the email address (DemoDev convention)")
