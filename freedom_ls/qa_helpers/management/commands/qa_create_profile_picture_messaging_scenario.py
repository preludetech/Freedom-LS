"""Seed a learner who has messaged the QA admin, for profile-picture QA.

On one site (default DemoDev, the site local browsing resolves to):

* The QA admin (demodev@email.com, made by ``create_demo_data``) gets an
  active StaffMember row in the site's default organisation, plus site_admin
  and organisation_admin grants. Existing grants are kept.
* Lena Learner (qa-learner@email.com, password == email, verified primary
  EmailAddress, active) is created or reused. A reused user has her names
  and password reset and any profile picture removed.
* Lena gets an active Learner row in the organisation and joins a cohort the
  admin is cohort_admin on: the first such cohort in the organisation, or
  "QA Profile Picture Cohort", created and granted when there is none.
* Eddie Educator (qa-educator@email.com, password == email, verified, active,
  no profile picture) is an active StaffMember of the organisation and
  cohort_admin on that cohort.
* Lena sends the admin one message and Eddie sends Lena one, both through
  ``send_message``, so the messaging policy has to allow them. Eddie's
  conversation is an "other educator" conversation from the admin's view of
  Lena. Re-runs reuse both messages (fixed client_keys).

Usage:
    uv run python manage.py qa_create_profile_picture_messaging_scenario
    uv run python manage.py qa_create_profile_picture_messaging_scenario --site-name DemoDev
"""

from __future__ import annotations

import uuid
from typing import cast

import djclick as click
from allauth.account.models import EmailAddress

from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.comms.messaging import send_message
from freedom_ls.comms.messaging_loader import get_messaging_policy
from freedom_ls.comms.models import Conversation
from freedom_ls.learner_management.factories import LearnerFactory
from freedom_ls.learner_management.models import Cohort, Learner, StaffMember
from freedom_ls.organisations.models import Organisation
from freedom_ls.organisations.utils import get_default_organisation
from freedom_ls.qa_helpers.management.commands.qa_create_cohort_administration_scenario import (
    _ensure_cohort,
    _ensure_member,
)
from freedom_ls.qa_helpers.management.commands.qa_create_organisation_scenarios import (
    _pin_current_site,
    _site_context,
)
from freedom_ls.role_based_permissions.models import ObjectRoleAssignment
from freedom_ls.role_based_permissions.utils import (
    assign_object_role,
    assign_site_role,
)

ADMIN_EMAIL = "demodev@email.com"
LEARNER_EMAIL = "qa-learner@email.com"
COHORT_NAME = "QA Profile Picture Cohort"
MESSAGE_KEY = uuid.UUID("3d7f5c1e-8a42-4b8e-9f61-5a0c2e9d7b14")
MESSAGE_BODY = "Hi! Quick question about my course, when you have a moment."
EDUCATOR_EMAIL = "qa-educator@email.com"
EDUCATOR_MESSAGE_KEY = uuid.UUID("9b2e4f71-6c3d-4a85-b0e2-7d1f8c5a3e96")
EDUCATOR_MESSAGE_BODY = "Hi Lena, just checking in on how the course is going."


def _ensure_admin_staff(site: Site, admin: User, org: Organisation) -> None:
    staff, _ = StaffMember._base_manager.update_or_create(
        site=site, user=admin, organisation=org, defaults={"is_active": True}
    )
    assign_site_role(admin, "site_admin", assigned_by=admin, site=site)
    assign_object_role(admin, org, "organisation_admin", assigned_by=admin)
    click.echo(f"Admin StaffMember pk={staff.pk} in '{org.name}' (active)")


def _ensure_user(site: Site, email: str, first_name: str, last_name: str) -> User:
    """Create or reset a login-ready user: password == email, verified, active,
    no profile picture."""
    user: User | None = User._base_manager.filter(site=site, email=email).first()
    if user is None:
        user = cast(
            User,
            UserFactory(
                site=site,
                email=email,
                password=email,
                first_name=first_name,
                last_name=last_name,
            ),
        )
        click.echo(f"Created user {email} pk={user.pk}")
    else:
        if user.profile_picture:
            click.echo(f"Removing profile picture {user.profile_picture.name}")
            user.profile_picture.delete(save=False)
        user.profile_picture = None
        user.first_name = first_name
        user.last_name = last_name
        user.is_active = True
        user.set_password(email)
        user.save()
        click.echo(f"Reused user {email} pk={user.pk} (password and picture reset)")
    EmailAddress.objects.update_or_create(
        user=user, email=email, defaults={"verified": True, "primary": True}
    )
    return user


def _send(
    site: Site, sender: User, recipient: User, body: str, key: uuid.UUID
) -> Conversation:
    """Send through the real service so the messaging policy is checked."""
    result = send_message(
        sender=sender, body=body, client_key=key, site=site, recipient=recipient
    )
    if result.message is None or result.conversation is None:
        raise click.ClickException(
            f"{sender.email} -> {recipient.email} refused: "
            f"{result.refusal} {result.body_error or ''}"
        )
    return result.conversation


def _admin_cohort(site: Site, admin: User, org: Organisation) -> Cohort:
    granted_ids = ObjectRoleAssignment._base_manager.filter(
        site=site,
        user=admin,
        role="cohort_admin",
        is_active=True,
        content_type=ContentType.objects.get_for_model(Cohort),
    ).values_list("object_id", flat=True)
    existing = (
        Cohort._base_manager.filter(
            site=site, organisation=org, pk__in=list(granted_ids)
        )
        .order_by("name")
        .first()
    )
    if existing is not None:
        click.echo(f"Reusing cohort '{existing.name}' pk={existing.pk}")
        return existing
    cohort = _ensure_cohort(site, org, COHORT_NAME)
    assign_object_role(admin, cohort, "cohort_admin", assigned_by=admin)
    click.echo(f"Cohort '{cohort.name}' pk={cohort.pk}, admin granted cohort_admin")
    return cohort


@click.command()
@click.option("--site-name", default="DemoDev", help="Site to seed (default: DemoDev).")
def command(site_name: str) -> None:
    """Seed Lena Learner, her cohort with the QA admin and Eddie, and two messages."""
    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        raise click.ClickException(f"Site '{site_name}' not found.") from e
    _pin_current_site(site)
    admin: User | None = User._base_manager.filter(site=site, email=ADMIN_EMAIL).first()
    if admin is None:
        raise click.ClickException(
            f"{ADMIN_EMAIL} not found on {site_name}; run create_demo_data --yes."
        )
    org = get_default_organisation(site)
    with _site_context(site):
        _ensure_admin_staff(site, admin, org)
        lena = _ensure_user(site, LEARNER_EMAIL, "Lena", "Learner")
        learner = cast(Learner, LearnerFactory(site=site, user=lena, organisation=org))
        cohort = _admin_cohort(site, admin, org)
        _ensure_member(site, cohort, lena)
        eddie = _ensure_user(site, EDUCATOR_EMAIL, "Eddie", "Educator")
        StaffMember._base_manager.update_or_create(
            site=site, user=eddie, organisation=org, defaults={"is_active": True}
        )
        assign_object_role(eddie, cohort, "cohort_admin", assigned_by=admin)
        policy = get_messaging_policy()
        for sender, recipient in (
            (lena, admin),
            (admin, lena),
            (eddie, lena),
            (lena, eddie),
        ):
            decision = policy.can_start(sender=sender, recipient=recipient, site=site)
            click.echo(
                f"can_start {sender.email} -> {recipient.email}: "
                f"{decision.allowed} {decision.reason or ''}"
            )
        admin_conversation = _send(site, lena, admin, MESSAGE_BODY, MESSAGE_KEY)
        eddie_conversation = _send(
            site, eddie, lena, EDUCATOR_MESSAGE_BODY, EDUCATOR_MESSAGE_KEY
        )
    click.echo(f"Admin pk={admin.pk} '{admin.display_name}' initials={admin.initials}")
    click.echo(
        f"Lena user pk={lena.pk}, Learner pk={learner.pk}, org '{org.name}' ({org.slug})"
    )
    click.echo(f"Eddie user pk={eddie.pk}, cohort_admin on '{cohort.name}'")
    click.echo(f"Cohort '{cohort.name}' pk={cohort.pk}")
    click.echo(
        f"Lena <-> admin conversation pk={admin_conversation.pk} "
        f"-> /messages/{admin_conversation.pk}/"
    )
    click.echo(
        f"Eddie <-> Lena conversation pk={eddie_conversation.pk} "
        f"-> /messages/{eddie_conversation.pk}/"
    )
