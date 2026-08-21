"""Seed the full browser-QA data set for the Organisations feature.

Covers the prerequisites table in
``spec_dd/2. in progress/schools/3. frontend_qa.md`` §0.4: three organisations,
four cohorts (including the same cohort name in two organisations, which is
what proves the narrowed uniqueness constraint), and the seven personas.

Everything is created on ONE site (default: DemoDev — the site
``FORCE_SITE_NAME`` pins the dev server to, whatever port it listens on).

Notable behaviours:

* The organisation formerly seeded as "Northside Academy" (slug
  ``northside-academy``) is replaced by one named exactly ``Northside`` with
  slug ``northside``. A slug is assigned once, at creation, and a later rename
  in the admin must NOT change it — §7.5 renames Northside to "Northside
  Academy" and asserts the monogram flips from "NO" to "NA", so the fixture
  has to start from the short name. The old row is deleted when nothing
  references it, and renamed to "Northside Old" when something does.
* ``organisation_staff`` is an object-scoped role assigned on the Organisation
  itself; the per-cohort legacy grant is the object-scoped ``instructor`` role
  on a single Cohort. Both go through
  ``role_based_permissions.utils.assign_object_role``, which syncs guardian
  object permissions (``view_organisation`` / ``view_cohort`` respectively).
* The site's ``SiteSignupPolicy.additional_registration_forms`` is emptied if
  set: ``RegistrationCompletionMiddleware`` would otherwise bounce every one of
  these non-superuser personas to the "complete registration" page on login.
  Re-run ``qa_create_incomplete_registration_learner`` to put it back.

Usage:
    uv run python manage.py qa_create_organisation_scenarios
    uv run python manage.py qa_create_organisation_scenarios --site-name DemoDev
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import cast

import djclick as click
from allauth.account.models import EmailAddress
from guardian.models import UserObjectPermission

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.files import File
from django.http import HttpRequest

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import SiteSignupPolicy, User
from freedom_ls.content_engine.models import Course
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.role_based_permissions.models import ObjectRoleAssignment
from freedom_ls.role_based_permissions.utils import assign_object_role
from freedom_ls.site_aware_models.models import _thread_locals
from freedom_ls.student_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    UserCourseRegistrationFactory,
)
from freedom_ls.student_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
    UserCourseRegistration,
)

# Byte-identical to `spec_dd/2. in progress/schools/RT-logo.webp` (same md5);
# the in-repo copy is used so the fixture survives the spec directory moving.
LOGO_PATH = Path(__file__).resolve().parent.parent.parent / "fixtures" / "RT-logo.webp"

RPAS_NAME, RPAS_SLUG = "RPAS Training", "rpas-training"
NORTHSIDE_NAME, NORTHSIDE_SLUG = "Northside", "northside"
SOUTHGATE_NAME, SOUTHGATE_SLUG = "Southgate", "southgate"
STALE_NORTHSIDE_SLUG = "northside-academy"

YEAR_9_MATHS = "Year 9 Maths"
RPAS_OTHER_COHORT = "Year 10 Science"
SOUTHGATE_COHORT = "Southgate Only"

# The cohort course: 18 viewable items across course parts, so the player's
# next/previous sweep (§7.2) has somewhere to go.
COHORT_COURSE_SLUG = "functionality-demo-course-parts"
# The solo learner's course. Deliberately a different one, so a course page
# never carries both a cohort and an individual registration for one person.
SOLO_COURSE_SLUG = "functionality-demo-show-end-with-topic"

PASSWORD = "demodev@email.com"  # noqa: S105  # pragma: allowlist secret  # dev-only QA credential


def _pin_current_site(site: Site) -> None:
    """Make ``Site.objects.get_current()`` resolve to ``site`` in this process.

    ``assign_object_role`` loads its role config through
    ``Site.objects.get_current()``, which needs ``SITE_ID``. This project sets
    none — the web path resolves the site from the request/``FORCE_SITE_NAME``,
    but a management command has no request. Pinning it here is what makes the
    site's own role config (rather than a fallback) the one that is loaded.
    """
    settings.SITE_ID = site.pk
    Site.objects.clear_cache()


class _SiteContextRequest(HttpRequest):
    """A request that already knows its site.

    ``_cached_site`` is the attribute ``get_cached_site`` reads before doing
    any host lookup; declaring it here keeps the assignment below typed.
    """

    _cached_site: Site


@contextmanager
def _site_context(site: Site) -> Iterator[None]:
    """Publish ``site`` on the thread local the way CurrentSiteMiddleware does.

    ``SiteAwareModelBase.save`` fills a blank ``site`` from the thread-local
    request, and models created indirectly — ``ObjectRoleAssignment``, written
    by ``assign_object_role`` — have no ``site=`` argument to pass, so without
    this the insert fails on a NOT NULL ``site_id``. ``_cached_site`` is the
    same attribute ``get_cached_site`` writes, so the site is returned straight
    from the request without any host lookup.
    """
    request = _SiteContextRequest()
    request._cached_site = site
    had_request = hasattr(_thread_locals, "request")
    previous = getattr(_thread_locals, "request", None)
    _thread_locals.request = request
    try:
        yield
    finally:
        if had_request:
            _thread_locals.request = previous
        else:
            delattr(_thread_locals, "request")


def _get_course(site: Site, slug: str) -> Course:
    try:
        return cast(Course, Course.objects.get(slug=slug, site=site))
    except Course.DoesNotExist as e:
        available = list(
            Course.objects.filter(site=site).values_list("slug", flat=True)
        )
        raise click.ClickException(
            f"Course '{slug}' not found on site '{site.name}'. Available: {available}"
        ) from e


def _ensure_organisation(site: Site, name: str, slug: str) -> Organisation:
    """Get-or-create by (site, slug); the slug is the stable identity here."""
    organisation: Organisation | None = Organisation._base_manager.filter(
        site=site, slug=slug
    ).first()
    if organisation is None:
        return cast(Organisation, OrganisationFactory(site=site, name=name, slug=slug))
    if organisation.name != name:
        organisation.name = name
        organisation.save(update_fields=["name"])
    return organisation


def _ensure_logo(organisation: Organisation) -> None:
    """Attach the logo through the ImageField so upload_to/validators run."""
    if organisation.logo:
        return
    with LOGO_PATH.open("rb") as fh:
        organisation.logo.save(LOGO_PATH.name, File(fh), save=True)


def _clear_logo(organisation: Organisation) -> None:
    """§7.5 needs Northside/Southgate to fall back to a monogram."""
    if organisation.logo:
        organisation.logo.delete(save=True)


def _retire_stale_northside(site: Site) -> str | None:
    """Get "Northside Academy" (slug ``northside-academy``) out of the way.

    Deleted when nothing points at it; renamed otherwise, because an
    Organisation is PROTECTed by cohorts and registrations and there is no
    supported delete path for one that is in use. Returns a description of
    what happened, or None if there was nothing to do.
    """
    stale: Organisation | None = Organisation._base_manager.filter(
        site=site, slug=STALE_NORTHSIDE_SLUG
    ).first()
    if stale is None:
        return None

    references = (
        Cohort.objects.filter(organisation=stale).count()
        + UserCourseRegistration.objects.filter(organisation=stale).count()
        + ObjectRoleAssignment.objects.filter(object_id=str(stale.pk)).count()
        + UserObjectPermission.objects.filter(object_pk=str(stale.pk)).count()
    )
    if references == 0:
        stale.delete()
        return f"deleted unreferenced '{stale.name}' (slug {STALE_NORTHSIDE_SLUG})"

    stale.name = "Northside Old"
    stale.save(update_fields=["name"])
    return (
        f"renamed to 'Northside Old' (slug {STALE_NORTHSIDE_SLUG}) — "
        f"{references} reference(s) block deletion"
    )


def _ensure_cohort(site: Site, organisation: Organisation, name: str) -> Cohort:
    cohort: Cohort | None = Cohort.objects.filter(
        site=site, organisation=organisation, name=name
    ).first()
    if cohort is not None:
        return cohort
    return cast(Cohort, CohortFactory(site=site, organisation=organisation, name=name))


def _ensure_user(site: Site, email: str, first_name: str, last_name: str) -> User:
    """A login-ready, non-privileged persona. Idempotent on re-runs."""
    user: User | None = User.objects.filter(email=email).first()
    if user is None:
        user = cast(
            User,
            UserFactory(
                email=email,
                first_name=first_name,
                last_name=last_name,
                is_active=True,
                is_staff=False,
                password=PASSWORD,
                site=site,
            ),
        )
    else:
        user.first_name = first_name
        user.last_name = last_name
        user.is_active = True
        user.is_staff = False
        user.is_superuser = False
        user.set_password(PASSWORD)
        user.save(
            update_fields=[
                "first_name",
                "last_name",
                "is_active",
                "is_staff",
                "is_superuser",
                "password",
            ]
        )
    # allauth bounces an unverified address to /accounts/confirm-email/.
    EmailAddress.objects.update_or_create(
        user=user, email=user.email, defaults={"verified": True, "primary": True}
    )
    return user


def _ensure_membership(site: Site, cohort: Cohort, user: User) -> None:
    if not CohortMembership.objects.filter(cohort=cohort, user=user).exists():
        CohortMembershipFactory(site=site, cohort=cohort, user=user)


def _ensure_cohort_registration(site: Site, cohort: Cohort, course: Course) -> None:
    if not CohortCourseRegistration.objects.filter(
        cohort=cohort, collection=course
    ).exists():
        CohortCourseRegistrationFactory(site=site, cohort=cohort, collection=course)


def _ensure_user_registration(
    site: Site, organisation: Organisation, user: User, course: Course
) -> None:
    if not UserCourseRegistration.objects.filter(
        organisation=organisation, user=user, collection=course
    ).exists():
        UserCourseRegistrationFactory(
            site=site, organisation=organisation, user=user, collection=course
        )


def _clear_registration_gate(site: Site) -> str | None:
    """Empty additional_registration_forms so the personas can browse.

    RegistrationCompletionMiddleware redirects every authenticated
    non-superuser with an incomplete form to the completion page, on every
    non-exempt URL — which would be all of the educator and player pages this
    data set exists to exercise.
    """
    policy: SiteSignupPolicy | None = SiteSignupPolicy.objects.filter(site=site).first()
    if policy is None or not policy.additional_registration_forms:
        return None
    previous = list(policy.additional_registration_forms)
    policy.additional_registration_forms = []
    policy.save(update_fields=["additional_registration_forms"])
    return f"cleared SiteSignupPolicy.additional_registration_forms {previous}"


def _seed(site: Site) -> None:
    """Create every organisation, cohort, membership and persona."""
    cohort_course = _get_course(site, COHORT_COURSE_SLUG)
    solo_course = _get_course(site, SOLO_COURSE_SLUG)

    # --- Organisations -------------------------------------------------
    retired = _retire_stale_northside(site)
    rpas = _ensure_organisation(site, RPAS_NAME, RPAS_SLUG)
    _ensure_logo(rpas)
    northside = _ensure_organisation(site, NORTHSIDE_NAME, NORTHSIDE_SLUG)
    _clear_logo(northside)
    southgate = _ensure_organisation(site, SOUTHGATE_NAME, SOUTHGATE_SLUG)
    _clear_logo(southgate)

    # --- Cohorts -------------------------------------------------------
    rpas_maths = _ensure_cohort(site, rpas, YEAR_9_MATHS)
    rpas_other = _ensure_cohort(site, rpas, RPAS_OTHER_COHORT)
    northside_maths = _ensure_cohort(site, northside, YEAR_9_MATHS)
    southgate_only = _ensure_cohort(site, southgate, SOUTHGATE_COHORT)
    _ensure_cohort_registration(site, rpas_maths, cohort_course)

    # --- Personas ------------------------------------------------------
    org_educator = _ensure_user(site, "org.educator@example.com", "Olive", "Educator")
    assign_object_role(org_educator, rpas, "organisation_staff")
    assign_object_role(org_educator, northside, "organisation_staff")

    single_org = _ensure_user(site, "single.org@example.com", "Sam", "Singleton")
    assign_object_role(single_org, rpas, "organisation_staff")

    # No organisation role at all: guardian view_cohort on ONE cohort, which is
    # what the object-scoped instructor role syncs onto a Cohort (its
    # view_student permission is filtered out — wrong content type).
    legacy_educator = _ensure_user(
        site, "legacy.educator@example.com", "Lena", "Legacy"
    )
    assign_object_role(legacy_educator, rpas_maths, "instructor")

    _ensure_user(site, "no.access@example.com", "Noah", "Access")

    cohort_learner = _ensure_user(site, "cohort.learner@example.com", "Cara", "Learner")
    _ensure_membership(site, rpas_maths, cohort_learner)
    for email, first, last in [
        ("y9.student2@example.com", "Priya", "Naidoo"),
        ("y9.student3@example.com", "Tom", "Fischer"),
    ]:
        _ensure_membership(site, rpas_maths, _ensure_user(site, email, first, last))

    # A member the legacy educator holds no grant on, so §5's "other cohort
    # 404s" and "users list is limited to Year 9 Maths" checks can distinguish.
    _ensure_membership(
        site, rpas_other, _ensure_user(site, "y10.student@example.com", "Ada", "Kruger")
    )

    # Northside-only learners: they must never surface in an RPAS Training list.
    for email, first, last in [
        ("northside.student1@example.com", "Nina", "Botha"),
        ("northside.student2@example.com", "Neo", "Dlamini"),
    ]:
        _ensure_membership(
            site, northside_maths, _ensure_user(site, email, first, last)
        )

    _ensure_membership(
        site,
        southgate_only,
        _ensure_user(site, "southgate.student@example.com", "Sipho", "Gate"),
    )

    solo_learner = _ensure_user(site, "solo.learner@example.com", "Sol", "Individual")
    _ensure_user_registration(site, northside, solo_learner, solo_course)

    _ensure_user(site, "no.reg.learner@example.com", "Nell", "Unregistered")

    gate = _clear_registration_gate(site)

    # --- Report ---------------------------------------------------------
    click.secho("\n--- Organisations QA data ---", fg="cyan", bold=True)
    click.secho(f"Site: {site.name} ({site.domain})", fg="cyan")
    if retired:
        click.secho(f"Stale Northside Academy: {retired}", fg="yellow")
    if gate:
        click.secho(f"Registration gate: {gate}", fg="yellow")

    for organisation in (rpas, northside, southgate):
        click.secho(
            f"ORG  {organisation.name!r} slug={organisation.slug} "
            f"logo={'yes' if organisation.logo else 'no'} id={organisation.pk}",
            fg="green",
        )
    for cohort in (rpas_maths, rpas_other, northside_maths, southgate_only):
        click.secho(
            f"COHORT {cohort.name!r} org={cohort.organisation.name} "
            f"members={CohortMembership.objects.filter(cohort=cohort).count()} "
            f"id={cohort.pk}",
            fg="green",
        )
    click.secho(
        f"Cohort course: /courses/{cohort_course.slug}/  "
        f"Solo-learner course: /courses/{solo_course.slug}/",
        fg="green",
    )
    click.secho(f"All persona passwords: {PASSWORD}", fg="cyan", bold=True)


@click.command()
@click.option("--site-name", default="DemoDev", help="Site to seed (default: DemoDev).")
def command(site_name: str) -> None:
    """Seed organisations, cohorts and personas for the Organisations QA pass."""
    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e
    _pin_current_site(site)
    with _site_context(site):
        _seed(site)
