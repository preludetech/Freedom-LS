"""Create the three QA users the learner account page is tested with.

Creates (or resets) on one site (default: DemoDev):

* ``qa-learner@example.com``: a learner in the site's default organisation.
* ``qa-educator@example.com``: ``organisation_admin`` on one organisation, which
  is what opens the educator interface. Built by ``qa_create_single_org_educator``.
* ``qa-nopassword@example.com``: a learner with an unusable password. Sign in
  as them with ``qa_login_session --email qa-nopassword@example.com``.

Every user is active, not staff, not superuser, has a verified primary
EmailAddress and the site's terms and privacy consents. Registration is
complete as long as the site's signup policy lists no additional registration
forms; the command reports any incomplete forms.

Idempotent. Only these three users' rows are touched.

Usage:
    uv run python manage.py qa_create_account_page_users
    uv run python manage.py qa_create_account_page_users --site DemoDev
"""

from __future__ import annotations

from typing import cast

import djclick as click
from allauth.account.models import EmailAddress

from django.contrib.sites.models import Site
from django.core.management import call_command
from django.db import transaction

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import SiteSignupPolicy, User
from freedom_ls.accounts.registration_forms import get_incomplete_forms
from freedom_ls.accounts.utils import get_effective_additional_registration_forms
from freedom_ls.learner_management.utils import ensure_learner
from freedom_ls.organisations.utils import get_default_organisation
from freedom_ls.qa_helpers.management.commands.qa_create_organisation_scenarios import (
    _pin_current_site,
    _site_context,
)
from freedom_ls.qa_helpers.management.commands.qa_create_single_org_educator import (
    _ensure_consents,
)

PASSWORD = "testpass123"  # noqa: S105  # pragma: allowlist secret  # dev-only QA credential
LEARNER_EMAIL = "qa-learner@example.com"
EDUCATOR_EMAIL = "qa-educator@example.com"
UNUSABLE_LOGIN_EMAIL = "qa-nopassword@example.com"


def _ensure_learner_user(
    site: Site, email: str, first: str, last: str, password: str | None
) -> User:
    """A plain learner. ``password=None`` leaves the password unusable."""
    user: User | None = User._base_manager.filter(email=email).first()
    if user is None:
        user = cast(
            User,
            UserFactory(email=email, first_name=first, last_name=last, site=site),
        )
    user.first_name, user.last_name = first, last
    user.is_active = True
    user.is_staff = False
    user.is_superuser = False
    if password is None:
        user.set_unusable_password()
    else:
        user.set_password(password)
    user.save()
    EmailAddress.objects.filter(user=user).exclude(email=email).update(primary=False)
    EmailAddress.objects.update_or_create(
        user=user, email=email, defaults={"verified": True, "primary": True}
    )
    _ensure_consents(site, user)
    ensure_learner(user, get_default_organisation(site))
    return user


def _incomplete_forms(site: Site, user: User) -> list[str]:
    policy = SiteSignupPolicy._base_manager.filter(site=site).first()
    dotted_paths = get_effective_additional_registration_forms(policy)
    return [cls.__name__ for cls in get_incomplete_forms(user, dotted_paths)]


@click.command()
@click.option("--site", "site_name", default="DemoDev", show_default=True)
@click.option("--organisation-slug", default="demodev", show_default=True)
def command(site_name: str, organisation_slug: str) -> None:
    site = Site.objects.get(name=site_name)
    _pin_current_site(site)
    with _site_context(site), transaction.atomic():
        learner = _ensure_learner_user(
            site, LEARNER_EMAIL, "Quill", "Learner", PASSWORD
        )
        no_password = _ensure_learner_user(
            site, UNUSABLE_LOGIN_EMAIL, "Nova", "Passwordless", None
        )

    call_command(
        "qa_create_single_org_educator",
        site_name=site_name,
        organisation_slug=organisation_slug,
        email=EDUCATOR_EMAIL,
        first_name="Ezra",
        last_name="Educator",
        password=PASSWORD,
    )
    educator = User._base_manager.get(email=EDUCATOR_EMAIL)

    click.echo("")
    click.echo(f"Site: {site.name} ({site.domain}, pk {site.pk})")
    for user, password in (
        (learner, PASSWORD),
        (educator, PASSWORD),
        (no_password, None),
    ):
        incomplete = _incomplete_forms(site, user)
        click.echo(
            f"  {user.email} / {password or '(unusable password)'} | pk {user.pk} | "
            f"usable password: {user.has_usable_password()} | "
            f"incomplete registration forms: {incomplete or 'none'}"
        )
    click.echo(
        f"Sign in as {UNUSABLE_LOGIN_EMAIL}: "
        f"uv run python manage.py qa_login_session --email {UNUSABLE_LOGIN_EMAIL}"
    )
