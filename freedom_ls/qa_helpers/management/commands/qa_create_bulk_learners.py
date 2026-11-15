"""Add N cohort-less learners to one organisation, to push it past BULK_BACKGROUND_THRESHOLD.

Each learner is a user on the organisation's site with a verified primary
EmailAddress and a Learner row; no cohort, no course registration, no email
sent. With --pending (the default) the user is made the way an import makes
one (unusable password, never logged in), so the learners table shows them as
Pending; with --active they get the password testpass123.

Idempotent: an existing address is reused and put back into the asked state.

Usage:
    uv run python manage.py qa_create_bulk_learners --count 90
    uv run python manage.py qa_create_bulk_learners --count 90 --prefix qa.bg \
        --name "Bg Learner" --org demodev --site-name DemoDev
"""

from __future__ import annotations

import djclick as click
from allauth.account.models import EmailAddress

from django.contrib.auth.hashers import make_password
from django.contrib.sites.models import Site
from django.db import transaction

from freedom_ls.accounts.account_setup import match_or_create_user
from freedom_ls.accounts.models import User
from freedom_ls.learner_management.models import Learner
from freedom_ls.learner_management.queries import LearnerStatus, learner_status_q
from freedom_ls.learner_management.utils import ensure_learner
from freedom_ls.organisations.models import Organisation

PASSWORD = "testpass123"  # noqa: S105  # pragma: allowlist secret  # dev-only QA credential


def _put_in_state(user: User, name: str, pending: bool, pw_hash: str) -> None:
    if pending:
        user.set_unusable_password()
        user.last_login = None
    else:
        user.password = pw_hash
    user.first_name = name
    user.last_name = ""
    user.is_active = True
    user.save(
        update_fields=["password", "last_login", "first_name", "last_name", "is_active"]
    )
    EmailAddress.objects.update_or_create(
        user=user, email=user.email, defaults={"verified": True, "primary": True}
    )


@click.command()
@click.option("--count", type=int, required=True, help="How many learners.")
@click.option("--prefix", default="qa.bg", help="Email local-part prefix.")
@click.option("--name", default="Bg Learner", help="First-name prefix.")
@click.option("--org", "org_slug", default="demodev", help="Organisation slug.")
@click.option("--site-name", default="DemoDev", help="Site name.")
@click.option("--pending/--active", default=True, help="Pending (default) or active.")
def command(
    count: int, prefix: str, name: str, org_slug: str, site_name: str, pending: bool
) -> None:
    """Create COUNT cohort-less learners prefixNNN@email.com in an organisation."""
    try:
        site = Site.objects.get(name=site_name)
        org = Organisation._base_manager.get(site=site, slug=org_slug)
    except (Site.DoesNotExist, Organisation.DoesNotExist) as e:
        raise click.ClickException(str(e)) from e
    pw_hash = make_password(PASSWORD)
    created = 0
    with transaction.atomic():
        for n in range(1, count + 1):
            email = f"{prefix}{n:03d}@email.com"
            full_name = f"{name} {n:03d}"
            user, was_created = match_or_create_user(site, email, full_name, "")
            created += was_created
            _put_in_state(user, full_name, pending, pw_hash)
            ensure_learner(user, org)
    learners = Learner._base_manager.filter(organisation=org)
    ours = learners.filter(
        user__email__startswith=prefix, user__email__endswith="@email.com"
    )
    shown = learners.filter(
        learner_status_q(LearnerStatus.ACTIVE) | learner_status_q(LearnerStatus.PENDING)
    )
    state = "pending" if pending else f"active, password {PASSWORD}"
    click.echo(f"users created this run: {created} ({state})")
    click.echo(
        f"{prefix}NNN learners: {ours.count()} "
        f"pending={ours.filter(learner_status_q(LearnerStatus.PENDING)).count()} "
        f"with cohort={ours.filter(cohortmembership__isnull=False).count()}"
    )
    click.echo(
        f"{org.slug} learners shown by default (Active+Pending): {shown.count()}"
    )
