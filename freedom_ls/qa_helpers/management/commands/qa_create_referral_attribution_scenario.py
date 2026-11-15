"""Seed the referral-attribution-over-time browser QA scenario.

Reuses existing demo-content courses rather than building new ones, and checks
that each still has the shape the QA plan needs:

* a published, free (self-registration) course;
* a published, application-gated course with an application form, which takes
  both a signed-in application and an anonymous one (claimed by email);
* a coming-soon course offering "Express interest".

It makes sure referral codes ``PARTNERA`` and ``PARTNERB`` exist and are active,
then creates or resets three login-ready learners and one staff user who can
reach /admin/ but holds no permissions at all.

Re-running is idempotent AND destructive for the named QA accounts: their
passwords and flags are reset, and every application, sitting, registration,
course interest, attribution touch, conversion and signup attribution they hold
is deleted (printed with pks and cascade counts). Nothing else is touched.

Usage:
    uv run python manage.py qa_create_referral_attribution_scenario
"""

from typing import cast

import djclick as click

from django.contrib.sites.models import Site
from django.db import transaction

from freedom_ls.accounts.factories import LegalConsentFactory
from freedom_ls.accounts.legal_docs import get_legal_doc
from freedom_ls.accounts.models import LegalConsent, User
from freedom_ls.content_engine.models import Course, CourseVisibility
from freedom_ls.course_interest.models import CourseInterest
from freedom_ls.learner_management.factories import LearnerFactory
from freedom_ls.organisations.utils import get_default_organisation
from freedom_ls.qa_helpers.management.commands.qa_create_clean_applicant import (
    _ensure_user,
    _ensure_verified_email,
    _get_site,
    _purge_course_data,
)
from freedom_ls.referral_tracking.factories import ReferralCodeFactory
from freedom_ls.referral_tracking.models import (
    AttributionTouch,
    Conversion,
    ReferralCode,
    SignupAttribution,
)

PASSWORD = "QaPass!2026x"  # noqa: S105  # pragma: allowlist secret  # dev-only QA credential
LEARNER_EMAILS = (
    "qa.live@example.com",
    "qa.login@example.com",
    "qa.selfreg@example.com",
)
STAFF_EMAIL = "qa.staffnoperm@example.com"

SELF_REG_SLUG = "functionality-demo-show-end-with-topic"
GATED_SLUG = "functionality-demo-application-gated-course"
COMING_SOON_SLUG = "content-widgets-demo-reference"

CODES = {
    "PARTNERA": ("QA Partner A", "/courses/functionality-demo-course-parts/detail/"),
    "PARTNERB": (
        "QA Partner B",
        "/courses/functionality-demo-application-gated-course/detail/",
    ),
}


def _course(site: Site, slug: str) -> Course:
    course = Course._base_manager.filter(site=site, slug=slug).first()
    if course is None:
        raise click.ClickException(
            f"No course '{slug}' on {site.name}: run `content_save demo_content "
            f"{site.name}` first."
        )
    return course


def _check_courses(site: Site) -> dict[str, Course]:
    """Fail loudly if a reused demo course no longer has the shape QA needs."""
    free = _course(site, SELF_REG_SLUG)
    gated = _course(site, GATED_SLUG)
    soon = _course(site, COMING_SOON_SLUG)
    problems = []
    if free.visibility != CourseVisibility.PUBLISHED or (
        free.access_config.get("access_type", "free") != "free"
    ):
        problems.append(f"{SELF_REG_SLUG} is not published + free")
    if (
        gated.visibility != CourseVisibility.PUBLISHED
        or gated.access_config.get("access_type") != "application_gated"
        or gated.application_form is None
    ):
        problems.append(f"{GATED_SLUG} is not published + gated with a form")
    if soon.visibility != CourseVisibility.COMING_SOON:
        problems.append(f"{COMING_SOON_SLUG} is not coming_soon")
    if problems:
        raise click.ClickException("; ".join(problems))
    return {"free": free, "gated": gated, "soon": soon}


def _ensure_codes(site: Site) -> list[ReferralCode]:
    codes = []
    for text, (label, destination) in CODES.items():
        code = ReferralCode._base_manager.filter(site=site, code__iexact=text).first()
        if code is None:
            code = cast(
                ReferralCode,
                ReferralCodeFactory(
                    code=text, label=label, destination=destination, site=site
                ),
            )
            click.secho(f"  Created referral code {text}", fg="green")
        elif not code.is_active:
            ReferralCode._base_manager.filter(pk=code.pk).update(is_active=True)
            click.secho(f"  Re-activated referral code {text}", fg="yellow")
        codes.append(ReferralCode._base_manager.get(pk=code.pk))
    return codes


def _purge_attribution(user: User) -> list[str]:
    """Conversions before touches: Conversion.first/last_touch is RESTRICT."""
    lines: list[str] = []
    for model in (Conversion, AttributionTouch, SignupAttribution, CourseInterest):
        rows = model._base_manager.filter(user=user)
        for row in rows:
            lines.append(f"{model.__name__} {row.pk} ({row})")
        if rows.exists():
            lines.append(f"  -> deleted: {rows.delete()}")
    return lines


def _ensure_consents(user: User, site: Site) -> None:
    """Mirror the signup clickwrap: one consent per legal document the site has."""
    for doc_type in ("terms", "privacy"):
        if LegalConsent._base_manager.filter(
            user=user, document_type=doc_type
        ).exists():
            continue
        doc = get_legal_doc(site, doc_type)
        if doc is None:
            continue
        LegalConsentFactory(
            user=user,
            document_type=doc_type,
            document_version=doc.version,
            git_hash=doc.git_hash,
            site=site,
        )


def _ensure_staff(site: Site) -> User:
    user, _ = _ensure_user(STAFF_EMAIL, site, password=PASSWORD)
    user.is_staff = True
    user.is_superuser = False
    user.save()
    user.groups.clear()
    user.user_permissions.clear()
    _ensure_verified_email(user)
    return user


@click.command()
@click.option("--site-name", default="DemoDev", help="Site name (default DemoDev).")
def command(site_name: str) -> None:
    """Seed the referral attribution QA courses, codes and accounts."""
    site = _get_site(site_name)
    organisation = get_default_organisation(site)
    courses = _check_courses(site)

    with transaction.atomic():
        codes = _ensure_codes(site)
        learners = []
        for email in LEARNER_EMAILS:
            user, created = _ensure_user(email, site, password=PASSWORD)
            _ensure_verified_email(user)
            LearnerFactory(user=user, organisation=organisation, site=site)
            _ensure_consents(user, site)
            removed = _purge_course_data(user) + _purge_attribution(user)
            click.secho(
                f"  {'Created' if created else 'Reset'} {email}",
                fg="green" if created else "yellow",
            )
            for line in removed:
                click.secho(f"      removed {line}", fg="red")
            learners.append(user)
        staff = _ensure_staff(site)

    click.secho("\n== Courses ==", fg="cyan", bold=True)
    for key, course in courses.items():
        click.echo(f"  {key:5} {course.title!r}  /courses/{course.slug}/detail/")
    click.secho("== Referral codes ==", fg="cyan", bold=True)
    for code in codes:
        click.echo(f"  {code.code} pk={code.pk} active={code.is_active}")
    click.secho("== Accounts (password: QaPass!2026x) ==", fg="cyan", bold=True)
    for user in [*learners, staff]:
        perms = user.user_permissions.count() + user.groups.count()
        click.echo(
            f"  {user.email} pk={user.pk} staff={user.is_staff} "
            f"superuser={user.is_superuser} perms+groups={perms} "
            f"consents={LegalConsent._base_manager.filter(user=user).count()}"
        )
