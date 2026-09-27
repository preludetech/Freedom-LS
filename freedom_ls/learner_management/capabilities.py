"""`can`: the single capability check every permission decision in the
educator interface answers through.

It reads role assignments and the role config, never guardian rows, so a
config change or a fresh grant takes effect immediately, with nothing to
re-sync. `queries.py` reuses the private builders below to build the
queryset twin of each step, so the two can never disagree.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.db.models import CharField, Exists, Model, OuterRef, QuerySet
from django.db.models.functions import Cast

from freedom_ls.learner_management.models import Cohort, CohortMembership, Learner
from freedom_ls.organisations.models import Organisation
from freedom_ls.role_based_permissions.loader import get_role_config
from freedom_ls.role_based_permissions.models import (
    ObjectRoleAssignment,
    SiteRoleAssignment,
)

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser, AnonymousUser

    from freedom_ls.accounts.models import User

    type RequestUser = User | AnonymousUser | AbstractBaseUser


def roles_granting(capability: str, site: Site) -> frozenset[str]:
    """The role keys on `site` whose permissions include `capability`."""
    config = get_role_config(site.name)
    return frozenset(
        key for key, role in config.items() if capability in role.permissions
    )


def _site_of(scope: Model) -> Site:
    """The site a scope object belongs to. A Site is its own site.

    Raises for a scope kind can() has no rule for, matching
    _organisation_of: an unsupported scope is a bug in the caller.
    """
    if isinstance(scope, Site):
        return scope
    if isinstance(scope, (Organisation, Cohort, Learner)):
        return scope.site
    raise TypeError(f"can() has no site rule for {type(scope).__name__}")


def _organisation_of(scope: Model) -> Organisation | None:
    """The organisation a scope object belongs to, or None for a Site.

    Raises for a scope kind can() has no rule for, rather than denying
    silently: an unsupported scope is a bug in the caller, not a request to
    refuse.
    """
    if isinstance(scope, Site):
        return None
    if isinstance(scope, Organisation):
        return scope
    if isinstance(scope, (Cohort, Learner)):
        return scope.organisation
    raise TypeError(f"can() has no organisation rule for {type(scope).__name__}")


def _site_grants(
    user: User, roles: frozenset[str], site: Site
) -> QuerySet[SiteRoleAssignment]:
    """Active site-level grants of any of `roles` on `site`."""
    return SiteRoleAssignment.objects.filter(
        user=user, site=site, role__in=roles, is_active=True
    )


def _active_role_assignments(
    model: type[Model], roles: frozenset[str]
) -> QuerySet[ObjectRoleAssignment]:
    """Active object-level grants of any of `roles` on instances of `model`.

    The one place the assignment-table join is written.
    """
    return ObjectRoleAssignment.objects.filter(
        role__in=roles,
        is_active=True,
        content_type=ContentType.objects.get_for_model(model),
    )


def _grant_exists(model: type[Model], user: User, roles: frozenset[str]) -> Exists:
    """An Exists() matching an active grant of `roles` on the outer row.

    `object_id` is a CharField and every target here has a UUID primary
    key, so the join casts the outer pk to text rather than the other way
    round. Shared by _granted_organisations and _granted_cohorts, which each
    embed this in their own model's queryset -- .objects itself has to stay
    on the concrete model for the ORM to know which table to query.
    """
    return Exists(
        _active_role_assignments(model, roles).filter(
            user=user, object_id=Cast(OuterRef("pk"), output_field=CharField())
        )
    )


def _granted_organisations(user: User, roles: frozenset[str]) -> QuerySet[Organisation]:
    """Organisations `user` holds an active grant of `roles` on."""
    return Organisation.objects.filter(_grant_exists(Organisation, user, roles))


def _granted_cohorts(user: User, roles: frozenset[str]) -> QuerySet[Cohort]:
    """Cohorts `user` holds an active grant of `roles` on."""
    return Cohort.objects.filter(_grant_exists(Cohort, user, roles))


def can(user: RequestUser, capability: str, scope: Model) -> bool:
    """Whether `user` may exercise `capability` on `scope`.

    Resolves in order: superuser, a site-level grant, an organisation-level
    grant, then a cohort-level grant covering `scope` itself or, for a
    Learner, through a CohortMembership. A grant on a container covers
    everything inside it -- nothing is written onto the children it covers,
    so a container built after the grant is covered just the same. `can`
    ignores the scope object's own is_active.
    """
    if not user.is_authenticated or not user.is_active:
        return False
    user = cast("User", user)
    if user.is_superuser:
        return True
    site = _site_of(scope)
    roles = roles_granting(capability, site)
    if not roles:
        return False
    if _site_grants(user, roles, site).exists():
        return True
    organisation = _organisation_of(scope)
    if organisation is None:
        return False
    if _granted_organisations(user, roles).filter(pk=organisation.pk).exists():
        return True
    cohorts = _granted_cohorts(user, roles)
    if isinstance(scope, Cohort):
        return cohorts.filter(pk=scope.pk).exists()
    if isinstance(scope, Learner):
        return CohortMembership.objects.filter(
            learner=scope, cohort__in=cohorts
        ).exists()
    return False
