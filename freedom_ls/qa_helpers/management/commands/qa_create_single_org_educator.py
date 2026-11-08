"""Create an educator who can reach exactly one organisation.

Creates (or resets) a login-ready user on the given site with a verified
primary email, the site's terms and privacy consents, and an
``organisation_admin`` object role on a single organisation. With
``--cohort-name`` the grant is instead ``cohort_admin`` on that one cohort of
the organisation (a cohort-scoped staff member). Any other active
role grant this user holds is deactivated, so the educator interface's
organisation switcher offers that organisation alone.

Idempotent. Only the named user's own rows are touched.

Usage:
    uv run python manage.py qa_create_single_org_educator
    uv run python manage.py qa_create_single_org_educator --site DemoDev \
        --organisation-slug demodev --email qa.single.org.educator@example.com \
        --password testpass123
    uv run python manage.py qa_create_single_org_educator \
        --email qa.cohort.admin@example.com --cohort-name "Cohort 2025.04.06"
"""

from __future__ import annotations

from typing import cast

import djclick as click
from allauth.account.models import EmailAddress

from django.contrib.sites.models import Site
from django.db import transaction

from freedom_ls.accounts.factories import LegalConsentFactory, UserFactory
from freedom_ls.accounts.legal_docs import get_legal_doc
from freedom_ls.accounts.models import LegalConsent, User
from freedom_ls.learner_management.models import Cohort
from freedom_ls.organisations.models import Organisation
from freedom_ls.qa_helpers.management.commands.qa_create_organisation_scenarios import (
    _pin_current_site,
    _site_context,
)
from freedom_ls.role_based_permissions.models import (
    ObjectRoleAssignment,
    SiteRoleAssignment,
    SystemRoleAssignment,
)
from freedom_ls.role_based_permissions.utils import (
    assign_object_role,
    deactivate_site_role,
    sync_user_object_permissions,
)

ROLE = "organisation_admin"
COHORT_ROLE = "cohort_admin"
PASSWORD = "testpass123"  # noqa: S105  # pragma: allowlist secret  # dev-only QA credential


def _ensure_user(site: Site, email: str, first: str, last: str, password: str) -> User:
    user: User | None = User.objects.filter(email=email).first()
    if user is None:
        user = cast(
            User,
            UserFactory(
                email=email,
                first_name=first,
                last_name=last,
                password=password,
                site=site,
            ),
        )
    else:
        user.first_name, user.last_name = first, last
        user.is_active = True
        user.is_staff = False
        user.is_superuser = False
        user.set_password(password)
        user.save()
        user.user_permissions.clear()
    EmailAddress.objects.update_or_create(
        user=user, email=email, defaults={"verified": True, "primary": True}
    )
    return user


def _ensure_consents(site: Site, user: User) -> list[str]:
    """LegalConsent rows are append-only: add one per missing document type."""
    added: list[str] = []
    for doc_type in ("terms", "privacy"):
        if LegalConsent._base_manager.filter(
            user=user, site=site, document_type=doc_type
        ).exists():
            continue
        doc = get_legal_doc(site, doc_type)
        LegalConsentFactory(
            site=site,
            user=user,
            document_type=doc_type,
            document_version=doc.version if doc else "1.0",
            git_hash=doc.git_hash if doc else "qa",
        )
        added.append(doc_type)
    return added


def _drop_other_grants(
    user: User, target_object: Organisation | Cohort, role: str
) -> list[str]:
    """Deactivate every active grant except the one this command makes."""
    dropped: list[str] = []
    for assignment in ObjectRoleAssignment._base_manager.filter(
        user=user, is_active=True
    ).select_related("content_type"):
        is_target = (
            assignment.role == role
            and assignment.content_type.model_class() is type(target_object)
            and assignment.object_id == str(target_object.pk)
        )
        if is_target:
            continue
        assignment.is_active = False
        assignment.save(update_fields=["is_active", "updated_at"])
        target = assignment.content_type.get_object_for_this_type(
            pk=assignment.object_id
        )
        sync_user_object_permissions(user, target)
        dropped.append(f"object {assignment.role} on {target}")
    for site_assignment in SiteRoleAssignment._base_manager.filter(
        user=user, is_active=True
    ).select_related("site"):
        deactivate_site_role(user, site_assignment.role, site=site_assignment.site)
        dropped.append(f"site {site_assignment.role} on {site_assignment.site}")
    for system_assignment in SystemRoleAssignment.objects.filter(
        user=user, is_active=True
    ):
        system_assignment.is_active = False
        system_assignment.save(update_fields=["is_active", "updated_at"])
        dropped.append(f"system {system_assignment.role}")
    return dropped


@click.command()
@click.option("--site", "site_name", default="DemoDev", show_default=True)
@click.option("--organisation-slug", default="demodev", show_default=True)
@click.option(
    "--email", default="qa.single.org.educator@example.com", show_default=True
)
@click.option("--first-name", default="Quinn", show_default=True)
@click.option("--last-name", default="Okafor", show_default=True)
@click.option("--password", default=PASSWORD, show_default=True)
@click.option(
    "--cohort-name",
    default=None,
    help="Grant cohort_admin on this cohort of the organisation instead.",
)
def command(
    site_name: str,
    organisation_slug: str,
    email: str,
    first_name: str,
    last_name: str,
    password: str,
    cohort_name: str | None,
) -> None:
    site = Site.objects.get(name=site_name)
    organisation = Organisation._base_manager.get(site=site, slug=organisation_slug)
    target_object: Organisation | Cohort = organisation
    role = ROLE
    if cohort_name is not None:
        target_object = Cohort._base_manager.get(
            site=site, organisation=organisation, name=cohort_name
        )
        role = COHORT_ROLE
    _pin_current_site(site)
    with _site_context(site), transaction.atomic():
        user = _ensure_user(site, email, first_name, last_name, password)
        consents = _ensure_consents(site, user)
        dropped = _drop_other_grants(user, target_object, role)
        assign_object_role(user, target_object, role)

    click.echo(f"User: {email} / {password} ({first_name} {last_name}) on {site}")
    click.echo(f"Consents added: {consents or 'none (already present)'}")
    click.echo(f"Other grants deactivated: {dropped or 'none'}")
    click.echo(
        f"Grant: {role} on {type(target_object).__name__} {target_object!s} "
        f"(organisation {organisation.slug}, pk {target_object.pk})"
    )
    click.echo(f"URL: /educator/organisations/{organisation.slug}/cohorts")
